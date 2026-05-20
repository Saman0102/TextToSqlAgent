"""Executor agent that runs validated SQL."""

from tools.db_tools import execute_readonly_query


class ExecutorAgent:
    def run(self, sql: str, params: dict | None = None) -> list[dict]:
        return execute_readonly_query(sql, params or {})
