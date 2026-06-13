"""Canonical source for database connectivity. Do not import from any other location.

Merged from: database.py (root), app/db.py, app/core/db.py.
Provides singleton engine/session factory plus a raw ``execute_query`` helper.
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional

from sqlalchemy import create_engine, text
from sqlalchemy.engine import Engine
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import sessionmaker

from app.core.config import settings

_engine = None
_session_factory = None
SessionLocal = None


def get_database_url(override: str | None = None) -> str:
    """Return the database URL from settings or an explicit override."""
    url = override or settings.database_url
    if not url:
        raise ValueError("DATABASE_URL is not set in config/.secrets.yaml")
    return url


def _fallback_url(url: str) -> str | None:
    """Rewrite URL to try a different common port (e.g. 5432 vs 5433)."""
    if ":5433" in url:
        return url.replace(":5433", ":5432")
    if ":5432" in url:
        return url.replace(":5432", ":5433")
    return None


def get_engine() -> Engine:
    """Return a singleton SQLAlchemy engine (creates on first call)."""
    global _engine
    if _engine is None:
        url = get_database_url()
        try:
            # Try primary database URL
            engine = create_engine(url, pool_pre_ping=True)
            with engine.connect() as conn:
                conn.execute(text("SELECT 1"))
            _engine = engine
        except Exception:
            fb_url = _fallback_url(url)
            if fb_url:
                try:
                    engine = create_engine(fb_url, pool_pre_ping=True)
                    with engine.connect() as conn:
                        conn.execute(text("SELECT 1"))
                    _engine = engine
                    return _engine
                except Exception:
                    pass
            # Fall back to primary if all fails
            _engine = create_engine(url, pool_pre_ping=True)
    return _engine


def get_session_factory():
    """Return a singleton session factory bound to the engine."""
    global _session_factory
    if _session_factory is None:
        _session_factory = sessionmaker(autocommit=False, autoflush=False, bind=get_engine())
    return _session_factory


def execute_query(sql: str, params: Optional[Dict[str, Any]] = None, database_url: Optional[str] = None) -> List[Dict[str, Any]]:
    """Execute a raw SQL string and return rows as list of dicts.

    If *database_url* is provided, a one-off engine is used instead of the
    singleton (useful for evaluation scripts). Supports parameterized queries.
    """
    from app.tools.db_tools import quote_mixed_case_identifiers
    sql_quoted = quote_mixed_case_identifiers(sql)
    url = get_database_url(database_url)
    try:
        engine = create_engine(url) if database_url else get_engine()
        with engine.connect() as connection:
            result = connection.execute(text(sql_quoted), params or {})
            columns = list(result.keys())
            return [dict(zip(columns, row)) for row in result.fetchall()]
    except Exception as exc:
        fb_url = _fallback_url(url)
        if fb_url:
            try:
                engine = create_engine(fb_url)
                with engine.connect() as connection:
                    result = connection.execute(text(sql_quoted), params or {})
                    columns = list(result.keys())
                    return [dict(zip(columns, row)) for row in result.fetchall()]
            except Exception:
                pass
        raise RuntimeError(str(exc)) from exc

