from __future__ import annotations

from html import escape
from typing import Dict, List

from fastapi import APIRouter, Query, Request
from fastapi.responses import HTMLResponse

from app.core.schema import DEFAULT_SCHEMA_PATH, load_schema
from app.decompose import decompose_question


router = APIRouter()


def _load_backend_schema() -> Dict[str, List[str]]:
	try:
		return load_schema(DEFAULT_SCHEMA_PATH)
	except Exception:
		return {}


BACKEND_SCHEMA = _load_backend_schema()


def _render_schema_table(schema: Dict[str, List[str]]) -> str:
	rows = []
	for table_name, columns in schema.items():
		rows.append(
			f"<tr><td>{escape(table_name)}</td><td>{escape(', '.join(columns) or 'None')}</td></tr>"
		)
	return ''.join(rows) or '<tr><td colspan="2">No schema loaded</td></tr>'


def _render_result(result: Dict[str, object]) -> str:
	filters = result.get('Filters') or []
	joins = result.get('Joins') or []
	return f'''
	<ul>
	  <li><strong>Intent:</strong> {escape(str(result.get('Intent', 'Unknown')))}</li>
	  <li><strong>Tables:</strong> {escape(', '.join(result.get('Tables', [])) or 'None')}</li>
	  <li><strong>Columns:</strong> {escape(', '.join(result.get('Columns', [])) or 'None')}</li>
	  <li><strong>Filters:</strong> {escape(', '.join(filters) or 'None')}</li>
	  <li><strong>Joins:</strong> {escape(', '.join(joins) or 'None')}</li>
	</ul>
	<pre>{escape(str(result))}</pre>
	'''


@router.get('/health')
def health() -> Dict[str, str]:
	return {'status': 'ok'}


@router.get('/')
def home() -> HTMLResponse:
	schema_html = _render_schema_table(BACKEND_SCHEMA)
	return HTMLResponse(
		f'''
<!doctype html>
<html>
	<head>
		<meta charset="utf-8" />
		<meta name="viewport" content="width=device-width, initial-scale=1" />
		<title>Text-to-SQL Decomposition</title>
		<style>
			body {{ font-family: Arial, sans-serif; margin: 2rem; background: #0b1220; color: #e6edf7; }}
			.card {{ background: #111827; border: 1px solid #334155; border-radius: 12px; padding: 1rem; margin-bottom: 1rem; }}
			textarea, input {{ width: 100%; padding: 0.75rem; border-radius: 8px; border: 1px solid #475569; background: #0f172a; color: #e6edf7; }}
			button {{ padding: 0.75rem 1rem; border: 0; border-radius: 8px; background: #2563eb; color: white; font-weight: 600; cursor: pointer; }}
			table {{ width: 100%; border-collapse: collapse; }}
			th, td {{ border: 1px solid #334155; padding: 0.5rem; text-align: left; vertical-align: top; }}
			pre {{ white-space: pre-wrap; word-break: break-word; background: #0f172a; padding: 1rem; border-radius: 8px; }}
			a {{ color: #93c5fd; }}
		</style>
	</head>
	<body>
		<h1>Text-to-SQL Decomposition</h1>
		<div class="card">
			<h2>Question</h2>
			<form method="post" action="/decompose">
				<textarea name="question" rows="4">How many customers are from the USA?</textarea>
				<div style="margin-top: 1rem;"><button type="submit">Decompose</button></div>
			</form>
		</div>
		<div class="card">
			<h2>Schema</h2>
			<table>
				<thead><tr><th>Table</th><th>Columns</th></tr></thead>
				<tbody>{schema_html}</tbody>
			</table>
			<p><a href="/schema">View schema JSON</a> | <a href="/health">Health</a></p>
		</div>
	</body>
</html>
		''',
	)


@router.get('/schema')
def schema() -> Dict[str, object]:
	return {
		'schemaFile': str(DEFAULT_SCHEMA_PATH),
		'tables': BACKEND_SCHEMA,
	}


@router.get('/decompose')
def decompose_api(question: str = Query(..., min_length=1)) -> Dict[str, object]:
	return decompose_question(question, schema=BACKEND_SCHEMA, schema_path=str(DEFAULT_SCHEMA_PATH))


@router.post('/decompose')
async def decompose_form(request: Request):
	content_type = request.headers.get('content-type', '')
	if 'application/json' in content_type:
		payload = await request.json()
		question = str(payload.get('question', '')).strip()
		return decompose_question(question, schema=BACKEND_SCHEMA, schema_path=str(DEFAULT_SCHEMA_PATH))

	form = await request.form()
	question = str(form.get('question', '')).strip()
	result = decompose_question(question, schema=BACKEND_SCHEMA, schema_path=str(DEFAULT_SCHEMA_PATH))
	return HTMLResponse(
		f'''
<!doctype html>
<html>
	<head>
		<meta charset="utf-8" />
		<meta name="viewport" content="width=device-width, initial-scale=1" />
		<title>Decomposition Result</title>
		<style>
			body {{ font-family: Arial, sans-serif; margin: 2rem; background: #0b1220; color: #e6edf7; }}
			.card {{ background: #111827; border: 1px solid #334155; border-radius: 12px; padding: 1rem; margin-bottom: 1rem; }}
			pre {{ white-space: pre-wrap; word-break: break-word; background: #0f172a; padding: 1rem; border-radius: 8px; }}
			a {{ color: #93c5fd; }}
		</style>
	</head>
	<body>
		<h1>Decomposition Result</h1>
		<div class="card">
			<p><a href="/">Back</a></p>
			{_render_result(result)}
		</div>
	</body>
</html>
		'''
	)
