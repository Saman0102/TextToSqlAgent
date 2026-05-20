from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Dict, List


PROJECT_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_SCHEMA_PATH = PROJECT_ROOT / 'schema.sql'


def load_schema(path: str | Path = DEFAULT_SCHEMA_PATH) -> Dict[str, List[str]]:
	file_path = Path(path)
	if file_path.suffix.lower() == '.json':
		with file_path.open('r', encoding='utf-8') as handle:
			return json.load(handle)
	return load_schema_from_sql(file_path)


def load_schema_from_sql(path: Path) -> Dict[str, List[str]]:
	text = path.read_text(encoding='utf-8')
	tables: Dict[str, List[str]] = {}
	create_table_pattern = re.compile(
		r'CREATE\s+TABLE\s+([A-Za-z_][A-Za-z0-9_]*)\s*\((.*?)\);',
		re.IGNORECASE | re.DOTALL,
	)

	for table_match in create_table_pattern.finditer(text):
		table_name = table_match.group(1)
		body = table_match.group(2)
		columns: List[str] = []
		for line in body.splitlines():
			entry = line.strip().rstrip(',')
			if not entry or entry.upper().startswith(('PRIMARY KEY', 'FOREIGN KEY', 'CONSTRAINT')):
				continue
			column_match = re.match(r'"?([A-Za-z_][A-Za-z0-9_]*)"?\s+[A-Za-z]', entry)
			if column_match:
				columns.append(column_match.group(1))
		tables[table_name] = columns

	return tables
