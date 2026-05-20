"""Database access helpers."""

from sqlalchemy import text

from config import settings
from db import get_engine


def execute_readonly_query(sql: str, params: dict) -> list[dict]:
    with get_engine().connect() as conn:
        result = conn.execute(text(sql), params)
        rows = [dict(row._mapping) for row in result]

    if settings.max_rows and len(rows) > settings.max_rows:
        rows = rows[: settings.max_rows]

    return rows
