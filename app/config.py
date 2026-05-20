"""Application configuration loaded from config files."""

from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, Iterable

import yaml


def _find_settings_path() -> Path:
    base_dir = Path(__file__).resolve().parent
    candidates = [
        base_dir.parent / "config" / "settings.yaml",
        base_dir / "config" / "settings.yaml",
    ]
    for path in candidates:
        if path.exists():
            return path
    return candidates[0]


SETTINGS_PATH = _find_settings_path()
CONFIG_DIR = SETTINGS_PATH.parent
SECRETS_PATHS = [CONFIG_DIR / ".secrets", CONFIG_DIR / ".secrets.yaml"]


def _load_yaml(path: Path) -> Dict[str, Any]:
    if not path.exists():
        return {}
    data = yaml.safe_load(path.read_text(encoding="utf-8"))
    if not isinstance(data, dict):
        return {}
    return data


def _load_config() -> Dict[str, Any]:
    settings = _load_yaml(SETTINGS_PATH)
    secrets: Dict[str, Any] = {}
    for path in SECRETS_PATHS:
        if path.exists():
            secrets.update(_load_yaml(path))
    return {**settings, **secrets}


def _get_value(config: Dict[str, Any], keys: Iterable[str], default: Any) -> Any:
    for key in keys:
        if key in config:
            return config[key]
    return default


def _get_str(config: Dict[str, Any], keys: Iterable[str], default: str) -> str:
    value = _get_value(config, keys, default)
    return str(value) if value is not None else default


def _get_int(config: Dict[str, Any], keys: Iterable[str], default: int) -> int:
    value = _get_value(config, keys, default)
    try:
        return int(value)
    except (TypeError, ValueError):
        return int(default)


@dataclass(frozen=True)
class Settings:
    database_url: str
    gemini_api_key: str
    llm_provider: str
    gemini_model: str
    max_rows: int
    fallback_provider: str
    ollama_url: str
    ollama_model: str


_config = _load_config()

gemini_api_key = _get_str(_config, ["gemini_api_key", "GEMINI_API_KEY"], "")
llm_provider = _get_str(_config, ["llm_provider", "LLM_PROVIDER"], "").lower()
if not llm_provider:
    if gemini_api_key:
        llm_provider = "gemini"
    else:
        llm_provider = "local"

fallback_provider = _get_str(
    _config,
    ["fallback_provider", "FALLBACK_PROVIDER"],
    "local",
).lower()

settings = Settings(
    database_url=_get_str(_config, ["database_url", "DATABASE_URL"], ""),
    gemini_api_key=gemini_api_key,
    llm_provider=llm_provider,
    gemini_model=_get_str(
        _config,
        ["gemini_model", "GEMINI_MODEL"],
        "gemini-1.5-flash",
    ),
    max_rows=_get_int(_config, ["max_rows", "MAX_ROWS"], 200),
    fallback_provider=fallback_provider,
    ollama_url=_get_str(
        _config,
        ["ollama_url", "OLLAMA_URL"],
        "http://localhost:11434/api/generate",
    ),
    ollama_model=_get_str(
        _config,
        ["ollama_model", "OLLAMA_MODEL"],
        "llama3.1:8b",
    ),
)
