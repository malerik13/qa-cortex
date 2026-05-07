"""Shared utilities for MCP dispatch servers.

All four servers (ticketing, test_mgmt, docs, chat) share:
- Config loading at startup
- Provider initialization
- Error → MCP-friendly response normalization
- Logging setup
"""

from __future__ import annotations

import logging
import os
import sys
from pathlib import Path
from typing import Any, Callable

from qa_cortex.config import load_config, ConfigError
from qa_cortex.providers import load_provider


logger = logging.getLogger("qa_cortex.servers")


def _load_dotenv_for_project() -> None:
    """Load .env from the project directory (next to qa-cortex.config.toml).

    Resolution order:
    1. Directory of $QA_CORTEX_CONFIG (if set)
    2. Current working directory

    Without this, MCP servers spawned by Claude Code via plugin.json don't
    inherit credentials from .env — they only see whatever env vars the
    MCP host explicitly forwarded. python-dotenv lets us load them at
    server startup so providers can resolve ${VAR} placeholders.
    """
    try:
        from dotenv import load_dotenv
    except ImportError:
        return  # dotenv not installed — rely on env vars set externally

    config_env = os.environ.get("QA_CORTEX_CONFIG")
    if config_env:
        project_dir = Path(config_env).parent
    else:
        project_dir = Path.cwd()

    dotenv_path = project_dir / ".env"
    if dotenv_path.exists():
        load_dotenv(dotenv_path, override=False)
        logger.debug("Loaded .env from %s", dotenv_path)


def init_provider(category: str) -> Any:
    """Load config + initialize provider for category. Fails loudly.

    Auto-loads .env from the directory containing qa-cortex.config.toml
    (or current working directory) so that MCP servers get credentials
    without needing every var duplicated in plugin.json env block.
    """
    # Auto-load .env before config resolution
    _load_dotenv_for_project()

    try:
        config = load_config()
    except ConfigError as e:
        sys.stderr.write(f"qa-cortex {category} server failed to load config: {e}\n")
        sys.exit(2)

    try:
        provider = load_provider(category, config)
    except Exception as e:
        sys.stderr.write(
            f"qa-cortex {category} server failed to initialize provider: {e}\n"
        )
        sys.exit(3)

    if provider is None:
        sys.stderr.write(
            f"qa-cortex {category} server: no provider needed (browser uses Claude Code MCP)\n"
        )
        sys.exit(0)

    return provider


def safe_invoke(method: Callable, *args, **kwargs) -> dict[str, Any]:
    """Invoke a provider method, normalize errors to MCP-friendly dicts.

    On exception, returns ``{"error": str, "type": exception_class_name}``
    rather than raising — MCP clients (Claude Code) get usable error response.
    """
    try:
        return method(*args, **kwargs)
    except (LookupError, ValueError, ConnectionError, ImportError, PermissionError) as e:
        return {
            "error": str(e),
            "type": type(e).__name__,
        }
    except Exception as e:
        # Unexpected — log full trace, return sanitized message
        logger.exception("Unexpected error in MCP method")
        return {
            "error": f"Internal error: {type(e).__name__}",
            "type": "InternalError",
        }
