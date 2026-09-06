"""Runtime config — the served-model endpoint and reasoning mode.

Everything is overridable by env var so the harness can point at any
OpenAI-compatible serve without code changes.
"""

from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path

_REPO_ROOT = Path(__file__).resolve().parents[2]


def _default_profile_dir() -> str:
    base = os.environ.get("LOCALAPPDATA") if os.name == "nt" else None
    if base:
        return str(Path(base) / "TaxAgent" / "profiles")
    return str(Path.home() / ".taxagent" / "profiles")


def _float_env(name: str, default: str) -> float:
    raw = os.environ.get(name, default)
    try:
        return float(raw)
    except ValueError:
        raise ValueError(f"{name} must be a number") from None


@dataclass(frozen=True)
class Settings:
    base_url: str = os.environ.get("TAXAGENT_BASE_URL", "http://127.0.0.1:8011/v1")
    model: str = os.environ.get("TAXAGENT_MODEL", "qwen")
    api_key: str = os.environ.get("TAXAGENT_API_KEY", "EMPTY")
    # where persisted user profiles live (one JSON per user_id)
    profile_dir: str = os.environ.get("TAXAGENT_PROFILE_DIR", _default_profile_dir())
    # "native" -> response_format json_schema (vLLM guided decoding, most reliable
    # here and keeps the system message first). "prompted"/"tool" available too.
    output_mode: str = os.environ.get("TAXAGENT_OUTPUT_MODE", "native")
    temperature: float = _float_env("TAXAGENT_TEMPERATURE", "0")


settings = Settings()
