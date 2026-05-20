"""Compatibility wrapper for schema_context.

The real implementation lives in `app.core.schema_context`. This module keeps
the old import path working for backward compatibility.
"""

from app.core.schema_context import *  # noqa: F401,F403