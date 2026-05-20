import re
from typing import Tuple

DISALLOWED_KEYWORDS = {
	'delete',
	'drop',
	'update',
	'insert',
	'alter',
	'truncate',
}


def validate_sql(sql: str) -> Tuple[bool, str]:
	statement = sql.strip().rstrip(';')
	if not statement:
		return False, 'Empty SQL statement'
	lowered = statement.lower()
	if not lowered.startswith('select'):
		return False, 'Only SELECT statements are allowed'
	if re.search(r"\b(" + '|'.join(DISALLOWED_KEYWORDS) + r")\b", lowered):
		return False, 'Disallowed SQL keyword detected'
	return True, ''
