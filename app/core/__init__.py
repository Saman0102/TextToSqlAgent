"""Core application modules (config, db, audit, schema).

This package contains the core runtime components so the rest of the app
can import stable package-qualified names like `app.core.config`.
"""

__all__ = ["config", "db", "audit", "schema", "schema_context"]
