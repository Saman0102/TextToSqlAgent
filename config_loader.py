from __future__ import annotations

from pathlib import Path
from typing import Any, Dict

import yaml

PROJECT_ROOT = Path(__file__).resolve().parent
CONFIG_DIR = PROJECT_ROOT / 'config'
SETTINGS_PATH = CONFIG_DIR / 'settings.yaml'
SECRETS_PATHS = [CONFIG_DIR / '.secrets', CONFIG_DIR / '.secrets.yaml']


def _load_yaml(path: Path) -> Dict[str, Any]:
	if not path.exists():
		return {}
	data = yaml.safe_load(path.read_text(encoding='utf-8'))
	return data or {}


def load_config() -> Dict[str, Any]:
	settings = _load_yaml(SETTINGS_PATH)
	secrets: Dict[str, Any] = {}
	for path in SECRETS_PATHS:
		if path.exists():
			secrets = _load_yaml(path)
			break
	return {**settings, **secrets}


def get_config_value(key: str, default: Any = None) -> Any:
	return load_config().get(key, default)
