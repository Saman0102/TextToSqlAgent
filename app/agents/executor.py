"""Executor agent that runs validated SQL."""

from __future__ import annotations

import json
import time
from pathlib import Path
from typing import Any, Dict, List, Optional

from app.agents.llm import LLMClient
from app.agents.planner import decompose_question
from app.agents.sql_generator import SQLGeneratorAgent
from app.agents.validator import validate_sql
from app.core.db import execute_query
from app.tools.db_tools import execute_readonly_query

LOG_PATH = Path("logs") / "query_logs.json"


class ExecutorAgent:
    def run(self, sql: str, params: dict | None = None) -> list[dict]:
        return execute_readonly_query(sql, params or {})


def _ensure_log_file() -> None:
    LOG_PATH.parent.mkdir(parents=True, exist_ok=True)
    if not LOG_PATH.exists():
        LOG_PATH.write_text("[]", encoding="utf-8")


def _append_log(entry: Dict[str, Any]) -> None:
    _ensure_log_file()
    data = json.loads(LOG_PATH.read_text(encoding="utf-8"))
    data.append(entry)
    LOG_PATH.write_text(json.dumps(data, indent=2), encoding="utf-8")


def run_pipeline(question: str, database_url: Optional[str] = None) -> Dict[str, Any]:
    """Legacy end-to-end pipeline (merged from root executor.py).

    Decomposes the question, generates SQL, validates, executes, and retries
    on failure up to 3 times.
    """
    start_time = time.time()
    retry_used = False
    status = "failed"
    result: List[Dict[str, Any]] = []
    sql = ""
    error_message = ""
    params: Dict[str, Any] = {}

    llm = LLMClient()
    generator = SQLGeneratorAgent(llm)
    schema_text = ""
    try:
        schema_path = Path(__file__).resolve().parents[2] / "db" / "schema.sql"
        if schema_path.exists():
            schema_text = schema_path.read_text(encoding="utf-8")
    except Exception:
        pass

    try:
        decomposition = decompose_question(question)
        if not database_url:
            from app.core.config import settings

            database_url = settings.database_url
            if not database_url:
                raise ValueError(
                    "DATABASE_URL not set in config/.secrets.yaml and no override provided"
                )

        plan = json.dumps(decomposition, indent=2)
        feedback = ""
        success = False

        for attempt in range(3):
            if attempt > 0:
                retry_used = True
                if sql and error_message:
                    sql = generator.fix_sql(question, sql, error_message, schema_text)
                    params = {}
                else:
                    gen = generator.run(question, plan, schema_text, error_feedback=feedback)
                    sql = gen.get("sql", "")
                    params = gen.get("params", {})
            else:
                gen = generator.run(question, plan, schema_text, error_feedback=feedback)
                sql = gen.get("sql", "")
                params = gen.get("params", {})

            is_valid, validation_message = validate_sql(sql)
            if not is_valid:
                error_message = validation_message
                feedback = f"SQL query validation failed: {validation_message}. Please generate a corrected SQL query."
                continue

            try:
                result = execute_query(sql, params=params, database_url=database_url)
                status = "success"
                success = True
                break
            except Exception as exc:
                error_message = str(exc)
                feedback = f"Database execution failed with error: {exc}. Please fix the query."

        if not success:
            return {
                "question": question,
                "sql": sql,
                "result": result,
                "status": status,
                "retry_used": retry_used,
                "error": error_message,
            }

        return {
            "question": question,
            "sql": sql,
            "result": result,
            "status": status,
            "retry_used": retry_used,
        }

    except Exception as exc:
        error_message = str(exc)
        return {
            "question": question,
            "sql": sql,
            "result": result,
            "status": status,
            "retry_used": retry_used,
            "error": error_message,
        }
    finally:
        duration = round(time.time() - start_time, 3)
        _append_log(
            {
                "timestamp": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
                "question": question,
                "sql": sql,
                "status": status,
                "retry_used": retry_used,
                "error": error_message,
                "duration_seconds": duration,
                "row_count": len(result),
            }
        )
