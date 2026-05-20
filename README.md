# Text-to-SQL Agent (Intent & Usage)

## Goal

Build a small agentic Text-to-SQL system that "thinks, acts, and corrects itself":

- Understand the user's natural language question; identify intent and relevant tables/columns.
- Generate a safe SELECT SQL statement.
- Execute the SQL against PostgreSQL.
- If execution fails, read the error, iteratively fix the SQL, and retry (up to 3 attempts).
- Return the raw SQL, execution result, and a natural-language summary.

## API (required)

Create a FastAPI endpoint to serve the agent:

- POST /agent/sql
- Request body example:

```json
{ "question": "How many shipped orders are from USA customers?" }
```

- Expected response example:

```json
{
  "sql": "SELECT COUNT(*) FROM orders o JOIN customers c ON o.customer_id=c.id WHERE c.country='USA' AND o.status='shipped'",
  "result": 42,
  "summary": "There are 42 shipped orders from customers in USA.",
  "status": "success"
}
```

## Required Agent Flow

The agent must implement the following steps (this README documents the intended design and how to run the system):

1. Understand Query
   - Identify user intent (aggregation, filters, joins, time ranges, etc.).
   - Detect relevant tables and columns from the schema (ranked schema context).

2. Generate SQL
   - Use an LLM-guided generator to produce a parameterized SELECT statement and parameters.

3. Execute Query
   - Run the SQL against PostgreSQL using SQLAlchemy (safe, parameterized execution).

4. Error Handling (IMPORTANT)
   - If execution fails, read the DB error message, prompt the LLM to fix the SQL, then re-validate and retry.
   - Allow up to 3 total execution attempts (initial + up to 2 fixes), log each attempt and outcome.

5. Final Output
   - Return the executed SQL, the numeric/result payload, and a natural-language summary produced by the summarizer.

## Rules / Safety

- Only SELECT queries are allowed; `app.agents.SQLValidator` performs static checks to block destructive SQL.
- All queries must be validated before execution.
- Log (append-only) the decomposition, SQL generation, execution time, and errors (no secrets).
- Provide a clear fallback response (status: "failed" or similar) if all retries are exhausted.

## What you will learn

- How AI agents decompose tasks and use LLM feedback loops.
- How to implement self-correction and retry logic.
- Safe parameterized query execution and simple audit logging.

## Implementation notes (mapping to this repo)

- Planner (intent & decomposition): `app.agents.PlannerAgent` — builds a plan and logs the prompt.
- Schema ranking / detection: `app.core.schema_context.build_ranked_schema_context` — returns ranked tables/columns and join hints.
- SQL generation: `app.agents.SQLGeneratorAgent` — returns `{sql, params}` and robustly parses LLM output.
- SQL validation: `app.agents.SQLValidator` — enforces SELECT-only, strips literals/comments, blocks banned keywords.
- Execution: `app.agents.ExecutorAgent` → `app.tools.db_tools.execute_readonly_query` (SQLAlchemy engine, respects `settings.max_rows`).
- Orchestration: `app.graph.workflow.run_workflow` — wires planner→generator→validator→executor→summarizer, emits `audit_id`, and writes audit JSONL events.
- Audit/logging: `app.core.audit` writes append-only JSONL entries for prompts, generation, validation, execution, and summarization.

## Current behavior vs. requirement

- The orchestration performs the planner→generator→validator generation retry loop up to `max_attempts` (default 3).
- Execution is performed and audited. On execution exceptions, `run_workflow()` currently logs the error and returns a failure rather than performing an LLM-driven fix+retry loop.
- A legacy script (`executor.py` at repository root) implements a single fix+retry cycle using `fix_sql()`. To fully satisfy the requirement you can either:
  - (A) Extend `run_workflow()` to implement the execution-error → LLM-fix → validate → retry loop (recommended), or
  - (B) Reuse the legacy `executor.py` flow and adapt it into the agent pipeline, increasing retries to 3 and adding audit records.

## Running the service (example)

Install dependencies into a Python 3.10+ virtualenv:

```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

Run the FastAPI app (if `app.main` provides the FastAPI app):

```bash
uvicorn app.main:app --host 0.0.0.0 --port 8000
```

Or run the Streamlit UI (local exploration):

```bash
python main.py serve --host 0.0.0.0 --port 8501
```

## Running tests

Run the unit tests with `pytest`:

```bash
pytest -q
```

## Notes and safety

- Do not commit `config/.secrets` or `logs/` to the repository. Keep API keys out of source control.
- Audit logs are append-only JSONL in `logs/query_audit.jsonl` (or `logs/query_logs.json` for legacy flows).

## Next steps (recommended)

1. Implement execution-error automatic fix + retry inside `app.graph.workflow.run_workflow` to meet the Step 4 requirement.
2. Add configurable retry limits and approval flow for queries exceeding row thresholds.
3. Add log rotation/retention for `logs/query_audit.jsonl`.

## References

- Evaluation dataset (test cases): https://docs.google.com/spreadsheets/d/1lgh-Wk6wJMGSEZiQh_ILqVpuRn4UbPWFUnYzB1RZ9Qc/edit?gid=1012683343

## License / Attribution

This repository is a learning project. Do not use it as-is in production without reviewing security, rate limits, and provider credentials.
