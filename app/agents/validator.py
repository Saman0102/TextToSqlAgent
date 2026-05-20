"""SQL validator enforcing read-only queries.

Improvements:
- Removes string literals and comments before scanning to avoid false negatives/positives.
- Blocks a wider set of administrative or state-modifying SQL keywords.
- Disallows SELECT ... INTO (which can create tables) and transaction/control statements.
"""

import re
from dataclasses import dataclass
from typing import Pattern

from app.audit import log_audit


@dataclass
class ValidationResult:
    is_valid: bool
    message: str


_BANNED_KEYWORDS = [
    "drop",
    "delete",
    "update",
    "insert",
    "alter",
    "truncate",
    "create",
    "grant",
    "revoke",
    "merge",
    "copy",
    "execute",
    "call",
    "do",
    "begin",
    "commit",
    "rollback",
    "set",
    "vacuum",
    "listen",
    "notify",
]


BANNED_PATTERN: Pattern = re.compile(r"\b(" + r"|".join(_BANNED_KEYWORDS) + r")\b", re.IGNORECASE)


def _strip_literals_and_comments(sql: str) -> str:
    """Return SQL with string literals and comments removed.

    This helps avoid matching banned keywords that appear inside quotes or comments.
    """
    # remove single-line comments -- and #
    sql_no_line_comments = re.sub(r"--.*?$|#.*?$", "", sql, flags=re.MULTILINE)
    # remove block comments /* ... */
    sql_no_block_comments = re.sub(r"/\*.*?\*/", "", sql_no_line_comments, flags=re.DOTALL)
    # remove single-quoted and double-quoted string literals
    sql_no_strings = re.sub(r"'(?:''|[^'])*'", "''", sql_no_block_comments)
    sql_no_strings = re.sub(r'\"(?:\"\"|[^\"])*\"', '\"\"', sql_no_strings)
    return sql_no_strings


class SQLValidator:
    def validate(self, sql: str, audit_id: str | None = None) -> ValidationResult:
        if not sql or not sql.strip():
            return ValidationResult(False, "Empty SQL query")

        # Normalize
        normalized = sql.strip()
        stripped = normalized.rstrip(";").strip()

        # Disallow statement chaining via semicolons, but permit a single trailing semicolon.
        if ";" in stripped:
            return ValidationResult(False, "Multiple statements are not allowed")

        # Work on a cleaned copy to avoid false matches inside strings/comments
        cleaned = _strip_literals_and_comments(stripped)

        # Disallow dangerous keywords
        if BANNED_PATTERN.search(cleaned):
            result = ValidationResult(False, "Destructive or administrative SQL is not allowed")
            try:
                log_audit("validation", {"sql": sql, "valid": False, "reason": result.message}, audit_id=audit_id)
            except Exception:
                pass
            return result

        # Disallow SELECT ... INTO (can create tables)
        if re.search(r"\bselect\b[\s\S]{0,200}\binto\b", cleaned, re.IGNORECASE):
            result = ValidationResult(False, "SELECT ... INTO (table creation) is not allowed")
            try:
                log_audit("validation", {"sql": sql, "valid": False, "reason": result.message}, audit_id=audit_id)
            except Exception:
                pass
            return result

        # Only allow queries that start with SELECT or WITH
        if not re.match(r"^(select|with)\b", cleaned.lstrip(), re.IGNORECASE):
            result = ValidationResult(False, "Only SELECT/CTE read-only queries are allowed")
            try:
                log_audit("validation", {"sql": sql, "valid": False, "reason": result.message}, audit_id=audit_id)
            except Exception:
                pass
            return result

        # All good - record a successful validation event
        try:
            log_audit("validation", {"sql": sql, "valid": True, "reason": "OK"}, audit_id=audit_id)
        except Exception:
            pass

        return ValidationResult(True, "OK")
