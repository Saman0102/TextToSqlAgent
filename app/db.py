"""SQLAlchemy engine configuration."""

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from config import settings

_engine = None
_session_factory = None


def get_engine():
    global _engine
    if _engine is None:
        if not settings.database_url:
            raise RuntimeError("DATABASE_URL is not set")
        _engine = create_engine(settings.database_url, pool_pre_ping=True)
    return _engine


def get_session_factory():
    global _session_factory
    if _session_factory is None:
        _session_factory = sessionmaker(autocommit=False, autoflush=False, bind=get_engine())
    return _session_factory


SessionLocal = None
