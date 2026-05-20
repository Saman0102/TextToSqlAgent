"""Schema utilities for loading and representing database schema."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Dict


DEFAULT_SCHEMA_PATH = Path(__file__).resolve().parents[1] / "sample_schema.json"


def load_schema(path: Path) -> Dict[str, list]:
    if not path.exists():
        return {}
    if path.suffix.lower() == ".json":
        return json.loads(path.read_text(encoding="utf-8"))
    # basic SQL parsing fallback (not used heavily)
    return {}
