from pathlib import Path
from typing import Any, Dict, List

import pandas as pd
import streamlit as st

from executor import run_pipeline
from sql_generator import decompose_question


APP_ROOT = Path(__file__).resolve().parent
QUESTIONS_ONLY_PATH = APP_ROOT / 'questions_only.csv'
QUESTIONS_WITH_ANSWERS_PATH = APP_ROOT / 'questions_and_answers.csv'


def _load_questions(path: Path) -> pd.DataFrame:
	data = pd.read_csv(path)
	if 'question' not in data.columns:
		raise ValueError('CSV must include a question column')
	data['question'] = data['question'].astype(str).str.strip()
	data = data[data['question'].str.len() > 0]
	return data


def _format_value(value: Any) -> str:
	if value is None:
		return ''
	if isinstance(value, list):
		return ', '.join(str(item) for item in value if item is not None)
	return str(value)


def _flatten_decomposition(decomp: Dict[str, Any]) -> Dict[str, str]:
	return {
		'intent': _format_value(decomp.get('Intent') or decomp.get('intent')),
		'tables': _format_value(decomp.get('Tables') or decomp.get('tables')),
		'columns': _format_value(decomp.get('Columns') or decomp.get('columns')),
		'filters': _format_value(decomp.get('Filters') or decomp.get('filters')),
		'joins': _format_value(decomp.get('Joins') or decomp.get('joins')),
	}


def _decompose_questions(questions: List[str]) -> pd.DataFrame:
	rows: List[Dict[str, str]] = []
	for question in questions:
		entry: Dict[str, str] = {'question': question}
		try:
			decomp = decompose_question(question)
			entry.update(_flatten_decomposition(decomp))
			exception_message = ''
		except Exception as exc:
			exception_message = str(exc)
			entry.update({'intent': '', 'tables': '', 'columns': '', 'filters': '', 'joins': ''})
		entry['error'] = exception_message
		rows.append(entry)
	return pd.DataFrame(rows)


st.set_page_config(page_title='Text-to-SQL Pipeline', layout='wide')

st.title('Text-to-SQL Pipeline')

if 'messages' not in st.session_state:
	st.session_state.messages = []

for message in st.session_state.messages:
	with st.chat_message(message['role']):
		st.markdown(message['content'])
		if message.get('sql'):
			st.code(message['sql'], language='sql')
		if message.get('result') is not None:
			df = pd.DataFrame(message['result'])
			st.dataframe(df, use_container_width=True)
		if message.get('status'):
			st.caption(f"Status: {message['status']} | Retry used: {message.get('retry_used', False)}")

question = st.chat_input('Ask a question about the database')
if question:
	st.session_state.messages.append({'role': 'user', 'content': question})
	with st.chat_message('assistant'):
		with st.spinner('Running prompt chain...'):
			response = run_pipeline(question)
		st.markdown('Here is the result:')
		st.code(response.get('sql', ''), language='sql')
		if response.get('result') is not None:
			df = pd.DataFrame(response.get('result', []))
			st.dataframe(df, use_container_width=True)
		st.caption(f"Status: {response.get('status')} | Retry used: {response.get('retry_used', False)}")

	st.session_state.messages.append(
		{
			'role': 'assistant',
			'content': 'Response generated.',
			'sql': response.get('sql', ''),
			'result': response.get('result', []),
			'status': response.get('status', 'failed'),
			'retry_used': response.get('retry_used', False),
		}
	)

st.divider()
st.header('Batch decomposition (CSV)')
st.caption('Runs Gemini decomposition for each question in the selected CSV.')

dataset_options: List[Dict[str, object]] = []
if QUESTIONS_ONLY_PATH.exists():
	dataset_options.append({'label': 'questions_only.csv', 'path': QUESTIONS_ONLY_PATH})
if QUESTIONS_WITH_ANSWERS_PATH.exists():
	dataset_options.append({'label': 'questions_and_answers.csv', 'path': QUESTIONS_WITH_ANSWERS_PATH})

if not dataset_options:
	st.warning('No questions CSV files were found in the project root.')
else:
	labels = [option['label'] for option in dataset_options]
	selected_label = st.selectbox('Choose a dataset', labels, index=0)
	selected_option = next(option for option in dataset_options if option['label'] == selected_label)

	try:
		df_questions = _load_questions(selected_option['path'])
	except Exception as exc:
		st.error(f'Failed to load questions: {exc}')
		df_questions = pd.DataFrame()

	max_rows = len(df_questions) if not df_questions.empty else 0
	limit = st.number_input('Max questions', min_value=1, max_value=max_rows or 1, value=min(20, max_rows or 1), step=1)

	if 'batch_decomposition' not in st.session_state:
		st.session_state.batch_decomposition = None
	if 'batch_key' not in st.session_state:
		st.session_state.batch_key = None

	if st.button('Run batch decomposition') and not df_questions.empty:
		with st.spinner('Running Gemini decomposition for selected questions...'):
			questions = df_questions['question'].head(int(limit)).tolist()
			results = _decompose_questions(questions)
			if 'answer' in df_questions.columns:
				answers = df_questions['answer'].head(int(limit)).tolist()
				results.insert(1, 'expected_sql', answers)
			st.session_state.batch_decomposition = results
			st.session_state.batch_key = f"{selected_label}:{limit}"

	if st.session_state.batch_decomposition is not None:
		st.subheader('Decomposition results')
		st.dataframe(st.session_state.batch_decomposition, use_container_width=True)
