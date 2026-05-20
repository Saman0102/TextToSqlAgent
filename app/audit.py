"""Simple audit logger for query attempts and execution events.

Writes JSON lines to `logs/query_audit.jsonl` in the repository root.
"""

from __future__ import annotations

import json
import secrets
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, Optional


ROOT = Path(__file__).resolve().parents[1]
LOG_DIR = ROOT / "logs"
LOG_PATH = LOG_DIR / "query_audit.jsonl"


def _ensure_log_dir() -> None:
    try:
        LOG_DIR.mkdir(parents=True, exist_ok=True)
    except Exception:
        pass


def make_audit_id() -> str:
    """Return a short timestamp-based audit identifier."""
    timestamp = datetime.utcnow().strftime("%Y%m%dT%H%M%SZ")
    suffix = secrets.token_hex(3)
    return f"{timestamp}-{suffix}"


def log_audit(event: str, details: Dict[str, Any], audit_id: Optional[str] = None) -> None:
    """Append an audit event as a JSON line.

    event: short string like 'validation'|'execution'|'summarizer'
    details: serializable dict with event-specific fields
    """
    _ensure_log_dir()
    record_details = dict(details)
    if audit_id is not None:
        record_details.setdefault("audit_id", audit_id)
    record = {
        "ts": datetime.utcnow().isoformat() + "Z",
        "event": event,
        "details": record_details,
    }
    if audit_id is not None:
        record["audit_id"] = audit_id
    try:
        with LOG_PATH.open("a", encoding="utf-8") as fh:
            fh.write(json.dumps(record, default=str, ensure_ascii=False) + "\n")
    except Exception:
        # best-effort: do not raise during normal operation
        pass
