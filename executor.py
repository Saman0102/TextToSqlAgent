import json
import time
from pathlib import Path
from typing import Any, Dict, List, Optional

from database import execute_query
from sql_generator import decompose_question, fix_sql, generate_sql
from validator import validate_sql
from config_loader import get_config_value

LOG_PATH = Path('logs') / 'query_logs.json'


def _ensure_log_file() -> None:
	LOG_PATH.parent.mkdir(parents=True, exist_ok=True)
	if not LOG_PATH.exists():
		LOG_PATH.write_text('[]', encoding='utf-8')


def _append_log(entry: Dict[str, Any]) -> None:
	_ensure_log_file()
	data = json.loads(LOG_PATH.read_text(encoding='utf-8'))
	data.append(entry)
	LOG_PATH.write_text(json.dumps(data, indent=2), encoding='utf-8')


def run_pipeline(question: str, database_url: Optional[str] = None) -> Dict[str, Any]:
	start_time = time.time()
	retry_used = False
	status = 'failed'
	result: List[Dict[str, Any]] = []
	sql = ''
	error_message = ''
	response: Dict[str, Any] = {}

	try:
		decomposition = decompose_question(question)
		# if no database_url provided, read from config
		if not database_url:
			database_url = get_config_value('DATABASE_URL')
			if not database_url:
				raise ValueError('DATABASE_URL not set in config/.secrets.yaml and no override provided')
		sql = generate_sql(decomposition)
		is_valid, message = validate_sql(sql)
		if not is_valid:
			error_message = message
			response = {
				'question': question,
				'sql': sql,
				'result': result,
				'status': status,
				'retry_used': retry_used,
				'error': error_message,
			}
			return response

		result = execute_query(sql, database_url=database_url)
		status = 'success'
		response = {
			'question': question,
			'sql': sql,
			'result': result,
			'status': status,
			'retry_used': retry_used,
		}
		return response
	except Exception as exc:
		error_message = str(exc)
		if sql:
			retry_used = True
			fixed_sql = fix_sql(question, sql, error_message)
			is_valid, message = validate_sql(fixed_sql)
			if not is_valid:
				error_message = message
				sql = fixed_sql
				response = {
					'question': question,
					'sql': sql,
					'result': result,
					'status': status,
					'retry_used': retry_used,
					'error': error_message,
				}
				return response
			result = execute_query(fixed_sql, database_url=database_url)
			sql = fixed_sql
			status = 'success'
			response = {
				'question': question,
				'sql': sql,
				'result': result,
				'status': status,
				'retry_used': retry_used,
			}
			return response
		response = {
			'question': question,
			'sql': sql,
			'result': result,
			'status': status,
			'retry_used': retry_used,
			'error': error_message,
		}
		return response
	finally:
		duration = round(time.time() - start_time, 3)
		log_entry = {
			'timestamp': time.strftime('%Y-%m-%dT%H:%M:%SZ', time.gmtime()),
			'question': question,
			'sql': sql,
			'status': status,
			'retry_used': retry_used,
			'error': error_message,
			'duration_seconds': duration,
			'row_count': len(result),
		}
		_append_log(log_entry)

	return response or {
		'question': question,
		'sql': sql,
		'result': result,
		'status': status,
		'retry_used': retry_used,
		'error': error_message,
	}
