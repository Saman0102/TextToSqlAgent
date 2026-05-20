"""Schema introspection and query-aware schema ranking.

This module loads the SQL schema, extracts tables/columns/foreign keys, and
builds a compact schema slice ranked by relevance to the current question and
recent conversation context.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Dict, Iterable, List, Sequence

from schema import DEFAULT_SCHEMA_PATH, load_schema


@dataclass(frozen=True)
class ForeignKeyRelation:
	source_table: str
	source_column: str
	target_table: str
	target_column: str


@dataclass(frozen=True)
class SchemaMetadata:
	tables: Dict[str, List[str]]
	relations: List[ForeignKeyRelation] = field(default_factory=list)


def _normalize_token(value: str) -> str:
	return re.sub(r"[^a-z0-9]+", "", value.lower())


def _tokenize(text: str) -> List[str]:
	return re.findall(r"[a-z0-9]+", text.lower())


def _singularize(token: str) -> str:
	if token.endswith("ies") and len(token) > 3:
		return token[:-3] + "y"
	if token.endswith("ses") and len(token) > 3:
		return token[:-2]
	if token.endswith("s") and len(token) > 3:
		return token[:-1]
	return token


def _split_name(name: str) -> List[str]:
	parts = re.split(r"[^A-Za-z0-9]+", name)
	if len(parts) > 1:
		return [part.lower() for part in parts if part]
	camel_parts = re.findall(r"[A-Z]?[a-z]+|[0-9]+", name)
	if camel_parts:
		return [part.lower() for part in camel_parts if part]
	return [name.lower()]


def _read_sql_text(path: Path) -> str:
	return path.read_text(encoding="utf-8")


def load_schema_metadata(path: str | Path = DEFAULT_SCHEMA_PATH) -> SchemaMetadata:
	file_path = Path(path)
	if file_path.suffix.lower() == ".json":
		tables = load_schema(file_path)
		return SchemaMetadata(tables=tables)

	text = _read_sql_text(file_path)
	tables = load_schema(file_path)
	relations = _extract_relations(text)
	return SchemaMetadata(tables=tables, relations=relations)


def _extract_relations(sql_text: str) -> List[ForeignKeyRelation]:
	relations: List[ForeignKeyRelation] = []
	table_pattern = re.compile(
		r"CREATE\s+TABLE\s+([A-Za-z_][A-Za-z0-9_]*)\s*\((.*?)\);",
		re.IGNORECASE | re.DOTALL,
	)
	fk_pattern = re.compile(
		r"FOREIGN\s+KEY\s*\(\s*\"?([A-Za-z_][A-Za-z0-9_]*)\"?\s*\)\s*REFERENCES\s+([A-Za-z_][A-Za-z0-9_]*)\s*\(\s*\"?([A-Za-z_][A-Za-z0-9_]*)\"?\s*\)",
		re.IGNORECASE,
	)

	for table_match in table_pattern.finditer(sql_text):
		source_table = table_match.group(1)
		body = table_match.group(2)
		for fk_match in fk_pattern.finditer(body):
			relations.append(
				ForeignKeyRelation(
					source_table=source_table,
					source_column=fk_match.group(1),
					target_table=fk_match.group(2),
					target_column=fk_match.group(3),
				)
			)

	return relations


def _score_table(table_name: str, columns: Sequence[str], tokens: Sequence[str]) -> int:
	score = 0
	table_tokens = _split_name(table_name)
	normalized_table = _normalize_token(table_name)
	token_set = set(tokens)

	for token in tokens:
		normalized_token = _normalize_token(token)
		if not normalized_token:
			continue
		if normalized_token == normalized_table:
			score += 12
		elif normalized_token == _singularize(normalized_table) or _singularize(normalized_token) == normalized_table:
			score += 10
		elif normalized_token in normalized_table or normalized_table in normalized_token:
			score += 5
		elif any(normalized_token == part or normalized_token == _singularize(part) for part in table_tokens):
			score += 8

	for column in columns:
		column_tokens = _split_name(column)
		normalized_column = _normalize_token(column)
		for token in token_set:
			normalized_token = _normalize_token(token)
			if not normalized_token:
				continue
			if normalized_token == normalized_column:
				score += 10
			elif normalized_token == _singularize(normalized_column) or _singularize(normalized_token) == normalized_column:
				score += 8
			elif normalized_token in normalized_column or normalized_column in normalized_token:
				score += 4
			elif any(normalized_token == part or normalized_token == _singularize(part) for part in column_tokens):
				score += 6

	return score


def _collect_related_tables(selected_tables: Sequence[str], relations: Sequence[ForeignKeyRelation]) -> List[str]:
	related: List[str] = []
	selected = set(selected_tables)
	for relation in relations:
		if relation.source_table in selected and relation.target_table not in selected:
			related.append(relation.target_table)
		elif relation.target_table in selected and relation.source_table not in selected:
			related.append(relation.source_table)
	return list(dict.fromkeys(related))


def rank_schema_tables(
	question: str,
	conversation_context: str,
	metadata: SchemaMetadata,
	max_tables: int = 5,
	max_columns_per_table: int = 6,
) -> Dict[str, List[str]]:
	text = f"{conversation_context}\n{question}".strip()
	tokens = _tokenize(text)
	if not tokens:
		tokens = []

	table_scores = []
	for table_name, columns in metadata.tables.items():
		table_scores.append((
			_score_table(table_name, columns, tokens),
			table_name,
			columns,
		))

	table_scores.sort(key=lambda item: (-item[0], item[1]))
	selected_tables = [table_name for score, table_name, _ in table_scores if score > 0][:max_tables]
	if not selected_tables:
		selected_tables = [table_name for _, table_name, _ in table_scores[:max_tables]]

	selected_tables.extend(_collect_related_tables(selected_tables, metadata.relations))
	selected_tables = list(dict.fromkeys(selected_tables))[:max_tables]

	ranked_schema: Dict[str, List[str]] = {}
	for table_name in selected_tables:
		columns = metadata.tables.get(table_name, [])
		scored_columns = []
		for column in columns:
			column_score = _score_table(column, [column], tokens)
			column_score += _score_table(table_name, [column], tokens) // 2
			scored_columns.append((column_score, column))
		scored_columns.sort(key=lambda item: (-item[0], item[1]))
		ranked_schema[table_name] = [column for _, column in scored_columns[:max_columns_per_table]]

	return ranked_schema


def build_ranked_schema_context(
	question: str,
	conversation_context: str,
	metadata: SchemaMetadata,
	max_tables: int = 5,
	max_columns_per_table: int = 6,
) -> str:
	ranked_schema = rank_schema_tables(
		question=question,
		conversation_context=conversation_context,
		metadata=metadata,
		max_tables=max_tables,
		max_columns_per_table=max_columns_per_table,
	)

	lines = ["Ranked schema context:"]
	for table_name, columns in ranked_schema.items():
		column_list = ", ".join(columns) if columns else "(no columns matched)"
		lines.append(f"- {table_name}: {column_list}")

	related_hints = []
	for relation in metadata.relations:
		if relation.source_table in ranked_schema or relation.target_table in ranked_schema:
			related_hints.append(
				f"- {relation.source_table}.{relation.source_column} -> {relation.target_table}.{relation.target_column}"
			)

	if related_hints:
		lines.append("Join hints:")
		lines.extend(list(dict.fromkeys(related_hints)))

	return "\n".join(lines)