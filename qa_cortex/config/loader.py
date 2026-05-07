"""Config loader — parse qa-cortex.config.toml + resolve env vars + validate.

Per Phase 2 Step 6 (D9 decision: minimal validation, no pydantic dep).

Pure-stdlib for v1.0 — uses tomllib (Python 3.11+) and os.environ.
Avoids adding pydantic-settings dep just for config; manual validation
is straightforward for our schema.
"""

from __future__ import annotations

import os
import re
import sys
from pathlib import Path
from typing import Any

if sys.version_info >= (3, 11):
    import tomllib
else:
    import tomli as tomllib  # type: ignore


REQUIRED_PROVIDERS_KEYS = {"ticketing", "test_management", "documentation", "chat", "browser"}

VALID_PROVIDER_VALUES = {
    "ticketing": {"jira", "linear", "github", "youtrack"},
    "test_management": {"testrail", "zephyr", "allure"},
    "documentation": {"confluence", "notion", "github_wiki"},
    "chat": {"slack", "teams", "discord"},
    "browser": {"playwright"},
}


_ENV_VAR_PATTERN = re.compile(r"\$\{([A-Z_][A-Z0-9_]*)\}")


class ConfigError(ValueError):
    """Raised when config is malformed or missing required values."""


def load_config(path: str | Path | None = None) -> dict[str, Any]:
    """Load qa-cortex config from TOML file.

    Args:
        path: Optional path to config file. If None, searches:
              1. ``./qa-cortex.config.toml``
              2. ``./.qa-cortex/config.toml``
              3. ``$HOME/.config/qa-cortex/config.toml``

    Returns:
        Validated config dict with env vars resolved.

    Raises:
        ConfigError: if file not found, malformed, or invalid.
    """
    config_path = _resolve_path(path)
    raw = _read_toml(config_path)
    resolved = _resolve_env_vars(raw)
    _validate(resolved)
    return resolved


def _resolve_path(path: str | Path | None) -> Path:
    if path:
        p = Path(path)
        if not p.exists():
            raise ConfigError(f"Config file not found: {p}")
        return p

    candidates = [
        Path.cwd() / "qa-cortex.config.toml",
        Path.cwd() / ".qa-cortex" / "config.toml",
        Path.home() / ".config" / "qa-cortex" / "config.toml",
    ]
    for c in candidates:
        if c.exists():
            return c

    raise ConfigError(
        f"Config file not found. Searched: {[str(c) for c in candidates]}\n"
        f"Create qa-cortex.config.toml in repo root or pass explicit path."
    )


def _read_toml(path: Path) -> dict[str, Any]:
    try:
        with open(path, "rb") as f:
            return tomllib.load(f)
    except tomllib.TOMLDecodeError as e:
        raise ConfigError(f"TOML parse error in {path}: {e}") from e


def _resolve_env_vars(obj: Any) -> Any:
    """Recursively resolve ``${VAR}`` strings via os.environ."""
    if isinstance(obj, dict):
        return {k: _resolve_env_vars(v) for k, v in obj.items()}
    if isinstance(obj, list):
        return [_resolve_env_vars(v) for v in obj]
    if isinstance(obj, str):
        return _ENV_VAR_PATTERN.sub(_resolve_env_match, obj)
    return obj


def _resolve_env_match(match: re.Match[str]) -> str:
    var_name = match.group(1)
    value = os.environ.get(var_name)
    if value is None:
        raise ConfigError(
            f"Env var ${{{var_name}}} not set. "
            f"Add it to .env (gitignored) or shell environment."
        )
    return value


def _validate(config: dict[str, Any]) -> None:
    """Validate config has required structure and provider selections."""
    if "providers" not in config:
        raise ConfigError("Missing [providers] section in config")

    providers = config["providers"]
    if not isinstance(providers, dict):
        raise ConfigError("[providers] must be a table")

    missing = REQUIRED_PROVIDERS_KEYS - set(providers.keys())
    if missing:
        raise ConfigError(
            f"[providers] section missing required keys: {sorted(missing)}. "
            f"Required: {sorted(REQUIRED_PROVIDERS_KEYS)}"
        )

    for category, value in providers.items():
        valid_values = VALID_PROVIDER_VALUES.get(category)
        if valid_values and value not in valid_values:
            raise ConfigError(
                f"providers.{category} = {value!r} not recognized. "
                f"Valid: {sorted(valid_values)}"
            )

    # For each selected provider, ensure its config section exists
    # (browser provider exempt — Playwright is configured via MCP, not TOML)
    PROVIDERS_WITHOUT_CONFIG_SECTION = {"browser"}
    for category, provider_name in providers.items():
        if category in PROVIDERS_WITHOUT_CONFIG_SECTION:
            continue
        section_table = config.get(category, {})
        if not isinstance(section_table, dict):
            raise ConfigError(f"[{category}] must be a table")
        if provider_name not in section_table:
            raise ConfigError(
                f"Provider {provider_name!r} selected for {category}, "
                f"but [{category}.{provider_name}] section missing"
            )


def get_provider_config(config: dict[str, Any], category: str) -> dict[str, Any]:
    """Extract config for the selected provider in a category.

    E.g. if config["providers"]["ticketing"] == "jira", returns
    config["ticketing"]["jira"].
    """
    if category not in config.get("providers", {}):
        raise ConfigError(f"Category {category!r} not in providers section")

    selected = config["providers"][category]
    return config.get(category, {}).get(selected, {})
