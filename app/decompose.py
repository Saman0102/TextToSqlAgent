#!/usr/bin/env python3
"""
Text-to-SQL decomposition CLI

Usage:
  python main.py --question "How many customers are from the USA?"
  python main.py --question-file questions.txt --schema sample_schema.json

This tool follows the decomposition rules defined in TEXT_TO_SQL_DECOMPOSITION_PROMPT.md
and produces a structured breakdown (Intent, Tables, Columns, Filters, Joins).
If a JSON schema is provided, table/column matching will be attempted; otherwise
the tool will return best-effort candidates and mark unknowns.
"""

import argparse
import json
import re
import sys
from pathlib import Path
from typing import Dict, List, Optional, Sequence, Tuple

import uvicorn

from app.core.schema import DEFAULT_SCHEMA_PATH, load_schema



STOPWORDS = {
	'the', 'a', 'an', 'of', 'in', 'from', 'to', 'for', 'by', 'on', 'with', 'and',
	'how', 'many', 'what', 'which', 'is', 'are', 'show', 'list', 'find'
}

DEFAULT_COUNT_COLUMNS = {
	'customers': 'customerNumber',
	'orders': 'orderNumber',
	'orderdetails': 'orderNumber',
	'employees': 'employeeNumber',
	'offices': 'officeCode',
	'products': 'productCode',
	'productlines': 'productLine',
	'payments': 'checkNumber',
}

def normalize_token(t: str) -> str:
	return re.sub(r"[^a-z0-9_]", '', t.lower())


def guess_nouns(question: str) -> List[str]:
	# Very small heuristic: split on non-word and pick tokens that are not stopwords
	tokens = re.findall(r"\w+", question.lower())
	candidates = [t for t in tokens if t not in STOPWORDS and not t.isdigit()]
	# return unique in order
	seen = set()
	out = []
	for t in candidates:
		if t not in seen:
			seen.add(t)
			out.append(t)
	return out


def detect_intent(question: str) -> str:
	q = question.lower()
	if re.search(r"\bhow many\b|\bcount\b|\bnumber of\b", q):
		return "Count" + (" (aggregate)" if "per" not in q else " (grouped count)")
	if re.search(r"\b(total|sum|average|avg|mean|max|min)\b", q):
		m = re.search(r"\b(total|sum|average|avg|mean|max|min)\b", q)
		return m.group(1).capitalize()
	if re.search(r"\b(list|show|get|find)\b", q):
		return "Retrieve rows"
	if re.search(r"\btop\b|\bmost\b|\bfewest\b", q):
		return "Top-K / ranking"
	return "Unknown intent"


def extract_filters(
	question: str,
	schema: Optional[Dict[str, List[str]]] = None,
	tables: Optional[List[str]] = None,
) -> Optional[List[str]]:
	q = question
	filters = []
	# country filters
	m = re.search(r"country\s*=\s*'?(\w[\w\s-]*)'?", q, re.IGNORECASE)
	if m:
		filters.append(f"country = '{m.group(1).strip()}'")

	# from X (e.g., from the USA)
	m2 = re.search(r"from\s+the\s+([A-Za-z0-9\s-]+)", q, re.IGNORECASE)
	if m2:
		val = m2.group(1).strip()
		# Prefer a schema-aware country filter when possible.
		if schema and any('country' in [normalize_token(column) for column in columns] for columns in schema.values()):
			filters.append(f"country = '{val}'")
		else:
			filters.append(f"location/country = '{val}'")

	# after/before years
	m3 = re.search(r"after\s+(\d{4})", q)
	if m3:
		filters.append(f"date > '{m3.group(1)}-01-01'")
	m4 = re.search(r"before\s+(\d{4})", q)
	if m4:
		filters.append(f"date < '{m4.group(1)}-01-01'")

	return filters if filters else None


def find_tables_and_columns(question: str, schema: Optional[Dict[str, List[str]]]) -> Tuple[List[str], List[str]]:
	nouns = guess_nouns(question)
	tables = []
	columns = []
	if schema:
		# try to match nouns to table names or column names
		norm_schema = {normalize_token(t): (t, cols) for t, cols in schema.items()}
		for n in nouns:
			key = normalize_token(n)
			if key in norm_schema:
				tables.append(norm_schema[key][0])
			else:
				# try to match columns
				for t, cols in schema.items():
					for c in cols:
						if key == normalize_token(c) or (key and key in normalize_token(c) and key not in STOPWORDS):
							columns.append(c)
							if t not in tables:
								tables.append(t)
	else:
		# best-effort candidates
		# assume plural noun tokens refer to tables
		for n in nouns:
			if n.endswith('s'):
				tables.append(n)
			else:
				columns.append(n)
		# No schema means we should not invent table or column names.
		return [], []

	# dedupe
	tables = list(dict.fromkeys(tables))
	columns = list(dict.fromkeys(columns))
	return tables, columns


def choose_default_count_columns(
	tables: List[str],
	schema: Optional[Dict[str, List[str]]],
) -> List[str]:
	columns: List[str] = []
	for table in tables:
		if table == 'unknown':
			continue
		default_column = DEFAULT_COUNT_COLUMNS.get(table)
		if schema and table in schema:
			table_columns = schema[table]
			if default_column and default_column in table_columns:
				columns.append(default_column)
			elif table_columns:
				columns.append(table_columns[0])
		elif default_column:
			columns.append(default_column)

	return list(dict.fromkeys(columns))


def decompose_question(
	question: str,
	schema_path: Optional[str] = None,
	schema: Optional[Dict[str, List[str]]] = None,
) -> Dict[str, Optional[List[str]]]:
	if schema is None:
		schema_path = schema_path or str(DEFAULT_SCHEMA_PATH)
	if schema is None and schema_path:
		try:
			schema = load_schema(schema_path)
		except Exception:
			schema = None

	intent = detect_intent(question)
	tables, columns = find_tables_and_columns(question, schema)
	filters = extract_filters(question, schema=schema, tables=tables)

	joins = None
	# crude join detection: if multiple tables found, indicate possible join
	if len(tables) > 1:
		joins = [f"{tables[i]} JOIN {tables[j]} ON <join-condition>" for i in range(len(tables)) for j in range(i+1, len(tables))]

	# When no clear tables/columns, mark unknown instead of inventing.
	if not tables:
		tables = ["unknown"]
	if not columns and intent.startswith('Count'):
		columns = choose_default_count_columns(tables, schema)
	if not columns:
		columns = ["unknown"]

	return {
		'Intent': intent,
		'Tables': tables,
		'Columns': columns,
		'Filters': filters or None,
		'Joins': joins or None,
	}


def pretty_print(decomp: Dict[str, Optional[List[str]]]) -> None:
	print(f"- Intent: {decomp['Intent']}")
	print(f"- Tables: {', '.join(decomp['Tables']) if decomp['Tables'] else 'None'}")
	print(f"- Columns: {', '.join(decomp['Columns']) if decomp['Columns'] else 'None'}")
	if decomp['Filters']:
		print(f"- Filters: {', '.join(decomp['Filters'])}")
	else:
		print(f"- Filters: None")
	if decomp['Joins']:
		print(f"- Joins: {', '.join(decomp['Joins'])}")
	else:
		print(f"- Joins: None")


def _build_parser() -> argparse.ArgumentParser:
	parser = argparse.ArgumentParser(description='Text-to-SQL decomposition runner')
	subparsers = parser.add_subparsers(dest='command')

	decompose_parser = subparsers.add_parser('decompose', help='Decompose a question')
	decompose_group = decompose_parser.add_mutually_exclusive_group(required=True)
	decompose_group.add_argument('--question', '-q', help='Question to decompose')
	decompose_group.add_argument('--question-file', '-f', help='File containing a question')
	decompose_parser.add_argument('--schema', '-s', default=str(DEFAULT_SCHEMA_PATH), help='Optional SQL or JSON schema file')

	serve_parser = subparsers.add_parser('serve', help='Start the FastAPI server')
	serve_parser.add_argument('--host', default='0.0.0.0', help='Host interface to bind')
	serve_parser.add_argument('--port', type=int, default=8000, help='Port to bind')
	serve_parser.add_argument('--reload', action='store_true', help='Enable auto-reload')

	return parser


def _run_decompose(args: argparse.Namespace) -> int:
	if args.question_file:
		with open(args.question_file, 'r', encoding='utf-8') as fh:
			question = fh.read().strip()
	else:
		question = args.question

	decomp = decompose_question(question, schema_path=args.schema)
	pretty_print(decomp)
	return 0


def _run_server(args: argparse.Namespace) -> int:
	uvicorn.run('app:app', host=args.host, port=args.port, reload=args.reload)
	return 0


def main(argv: Optional[Sequence[str]] = None) -> int:
	parser = _build_parser()
	argv = list(sys.argv[1:] if argv is None else argv)
	if not argv:
		parser.print_help()
		return 2
	if argv[0] not in {'decompose', 'serve'}:
		argv = ['decompose', *argv]
	args = parser.parse_args(argv)

	if args.command == 'serve':
		return _run_server(args)
	return _run_decompose(args)


if __name__ == '__main__':
	raise SystemExit(main())

