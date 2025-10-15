"""Configuration helpers for BugZero v2."""

from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Optional

CONFIG_ENV_VAR = "BUGZERO_CONFIG"
TOKEN_ENV_VAR = "GITHUB_TOKEN"
DEFAULT_CONFIG_PATH = Path(
    os.environ.get(CONFIG_ENV_VAR, "~/.config/bugzero/config.json")
).expanduser()


def _read_config(path: Path) -> dict:
    if not path.exists():
        return {}
    try:
        with path.open("r", encoding="utf-8") as handle:
            return json.load(handle)
    except json.JSONDecodeError as exc:
        raise RuntimeError(f"Config file at {path} is not valid JSON") from exc


def _write_config(path: Path, data: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as handle:
        json.dump(data, handle, indent=2)


def resolve_token(
    *,
    explicit: Optional[str] = None,
    config_path: Optional[Path] = None,
) -> str:
    """Return a GitHub token from the explicit value, env var, or config file."""
    if explicit:
        token = explicit.strip()
        if token:
            return token
    env_token = os.getenv(TOKEN_ENV_VAR, "").strip()
    if env_token:
        return env_token

    path = config_path or DEFAULT_CONFIG_PATH
    token = _read_config(path).get("github_token", "").strip()
    if token:
        return token

    raise RuntimeError(
        "GitHub token not found. Set the GITHUB_TOKEN environment variable "
        "or run `bugzero token set` to persist it."
    )


def store_token(token: str, *, config_path: Optional[Path] = None) -> Path:
    """Persist a token to the config file."""
    token = token.strip()
    if not token:
        raise ValueError("Cannot store empty token")
    path = config_path or DEFAULT_CONFIG_PATH
    data = _read_config(path)
    data["github_token"] = token
    _write_config(path, data)
    return path


def delete_token(*, config_path: Optional[Path] = None) -> None:
    """Remove the stored token if present."""
    path = config_path or DEFAULT_CONFIG_PATH
    if not path.exists():
        return
    data = _read_config(path)
    data.pop("github_token", None)
    if data:
        _write_config(path, data)
    else:
        path.unlink(missing_ok=True)


def token_status(*, config_path: Optional[Path] = None) -> dict:
    """Return information about where a token can be sourced."""
    path = config_path or DEFAULT_CONFIG_PATH
    env_present = bool(os.getenv(TOKEN_ENV_VAR, "").strip())
    config_present = bool(_read_config(path).get("github_token"))
    return {
        "env": env_present,
        "config_path": str(path) if config_present else None,
    }

