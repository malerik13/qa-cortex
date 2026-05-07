"""Shared utilities for MCP dispatch servers.

All four servers (ticketing, test_mgmt, docs, chat) share:
- Config loading at startup
- Provider initialization
- Error → MCP-friendly response normalization
- Logging setup
"""

from __future__ import annotations

import logging
import sys
from typing import Any, Callable

from qa_cortex.config import load_config, ConfigError
from qa_cortex.providers import load_provider


logger = logging.getLogger("qa_cortex.servers")


def init_provider(category: str) -> Any:
    """Load config + initialize provider for category. Fails loudly."""
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
