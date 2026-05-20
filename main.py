#!/usr/bin/env python3
"""Repository entrypoint that delegates to app/main.py."""

from pathlib import Path
import sys

PROJECT_ROOT = Path(__file__).resolve().parent
APP_DIR = PROJECT_ROOT / "app"

if str(APP_DIR) not in sys.path:
    sys.path.insert(0, str(APP_DIR))

from main import main as app_main


if __name__ == "__main__":
	raise SystemExit(app_main())