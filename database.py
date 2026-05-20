from __future__ import annotations

from typing import Any, Dict, List, Optional

from sqlalchemy import create_engine, text
from sqlalchemy.engine import Engine
from sqlalchemy.exc import SQLAlchemyError

from config_loader import get_config_value


def get_database_url(override: Optional[str] = None) -> str:
    url = override or get_config_value('DATABASE_URL')
    if not url:
        raise ValueError('DATABASE_URL is not set in config/.secrets.yaml')
    return url


def get_engine(database_url: Optional[str] = None) -> Engine:
    return create_engine(get_database_url(database_url))


def execute_query(sql: str, database_url: Optional[str] = None) -> List[Dict[str, Any]]:
    engine = get_engine(database_url)
    try:
        with engine.connect() as connection:
            result = connection.execute(text(sql))
            columns = list(result.keys())
            return [dict(zip(columns, row)) for row in result.fetchall()]
    except SQLAlchemyError as exc:
        raise RuntimeError(str(exc)) from exc