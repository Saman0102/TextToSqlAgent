# Text-to-SQL Pipeline and Query Execution System

This project implements a prompt-chaining pipeline that decomposes questions, generates SQL, validates
the query, executes it against PostgreSQL, and retries once if the database returns an error.

## What you get

- `main.py`: project entrypoint for CLI, Streamlit UI, and evaluation
- `sql_generator.py`: LLM calls for decomposition, SQL generation, and self-correction
- `validator.py`: rule-based SQL validation (SELECT only)
- `executor.py`: pipeline orchestration and logging
- `database.py`: SQL execution helper
- `prompts/templates.py`: schema context and prompt templates
- `streamlit_app.py`: Streamlit chat interface
- `logs/query_logs.json`: append-only execution logs

## Quick start

```bash
pip install -r requirements.txt
```

Set `DATABASE_URL` and `HUGGINGFACE_API_KEY` in config/.secrets.yaml. No `.env` is required.

## CLI usage

```bash
python main.py --question "How many customers are from the USA?"
```

Or explicitly use the subcommand:

```bash
python main.py run --question "How many customers are from the USA?"
```

## Streamlit UI

```bash
python main.py serve --host 0.0.0.0 --port 8501
```

Open the app in your browser:

```text
http://127.0.0.1:8501/
```

## Docker

```bash
docker compose up --build
```

The Streamlit UI will be available on port 8501.

## Evaluation

```bash
python main.py evaluate
```

The evaluation script prints a report with per-question results and overall metrics.
