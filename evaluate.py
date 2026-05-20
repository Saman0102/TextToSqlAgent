import argparse
import re
from typing import Dict, List

from executor import run_pipeline


BENCHMARK_DATA: List[Dict[str, str]] = [
	{
		'question': 'How many customers are from the USA?',
		'expected_sql': 'SELECT COUNT(customerNumber) FROM customers WHERE country = \'USA\';',
	},
	{
		'question': 'List the product names and buy prices for products in the Classic Cars line.',
		'expected_sql': 'SELECT productName, buyPrice FROM products WHERE productLine = \'Classic Cars\';',
	},
]


def _normalize_sql(sql: str) -> str:
	return re.sub(r"\s+", " ", sql.strip().rstrip(';').lower())


def evaluate(database_url: str | None = None) -> int:
	report_rows = []
	success_count = 0
	retry_success_count = 0

	for entry in BENCHMARK_DATA:
		question = entry['question']
		expected_sql = entry['expected_sql']
		result = run_pipeline(question, database_url=database_url)
		generated_sql = result.get('sql', '')
		status = result.get('status', 'failed')
		retry_used = result.get('retry_used', False)

		executed_successfully = status == 'success'
		correct_result = _normalize_sql(generated_sql) == _normalize_sql(expected_sql)
		final_status = 'success' if executed_successfully else 'failed'

		if executed_successfully:
			success_count += 1
			if retry_used:
				retry_success_count += 1

		report_rows.append(
			{
				'Question': question,
				'Generated SQL': generated_sql,
				'Executed Successfully': str(executed_successfully),
				'Correct Result': str(correct_result),
				'Retry Needed': str(retry_used),
				'Final Status': final_status,
			}
		)

	total = len(BENCHMARK_DATA)
	failed_total = total - success_count
	retry_rate = (retry_success_count / success_count * 100.0) if success_count else 0.0
	success_rate = (success_count / total * 100.0) if total else 0.0

	print('Question | Generated SQL | Executed Successfully | Correct Result | Retry Needed | Final Status')
	for row in report_rows:
		print(
			f"{row['Question']} | {row['Generated SQL']} | {row['Executed Successfully']} | "
			f"{row['Correct Result']} | {row['Retry Needed']} | {row['Final Status']}"
		)

	print('\nMetrics')
	print(f"SQL execution success rate: {success_rate:.1f}%")
	print(f"Retry success rate: {retry_rate:.1f}%")
	print(f"Total failed queries: {failed_total}")
	return 0


def main() -> int:
	parser = argparse.ArgumentParser(description='Evaluate the text-to-SQL pipeline')
	parser.add_argument('--database-url', help='Database URL override')
	args = parser.parse_args()
	return evaluate(database_url=args.database_url)


if __name__ == '__main__':
	raise SystemExit(main())
