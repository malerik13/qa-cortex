"""Shared shape conversion utilities.

Provider-specific responses get normalized to canonical schemas defined
in base.py docstrings. Adapters use these helpers to keep conversion
logic consistent.
"""

from __future__ import annotations

from typing import Any
from datetime import datetime


def normalize_iso8601(value: str | datetime | None) -> str:
    """Convert various date formats to ISO 8601 string.

    Handles:
    - Already-ISO strings (passthrough)
    - datetime objects (.isoformat())
    - None (returns empty string)

    Returns ISO 8601 with seconds precision, e.g. "2026-05-07T10:30:00Z".
    """
    if value is None:
        return ""
    if isinstance(value, datetime):
        return value.strftime("%Y-%m-%dT%H:%M:%SZ")
    if isinstance(value, str):
        # Try to parse and re-emit canonical
        for fmt in (
            "%Y-%m-%dT%H:%M:%S.%f%z",
            "%Y-%m-%dT%H:%M:%S%z",
            "%Y-%m-%dT%H:%M:%S.%fZ",
            "%Y-%m-%dT%H:%M:%SZ",
            "%Y-%m-%d %H:%M:%S",
            "%Y-%m-%d",
        ):
            try:
                dt = datetime.strptime(value, fmt)
                return dt.strftime("%Y-%m-%dT%H:%M:%SZ")
            except ValueError:
                continue
        # Couldn't parse — return as is
        return value
    return str(value)


def safe_get(d: dict[str, Any], path: str, default: Any = None) -> Any:
    """Navigate nested dict by dot-path. Returns default on missing.

    Example::

        safe_get({"a": {"b": {"c": 42}}}, "a.b.c") == 42
        safe_get({"a": {"b": {}}}, "a.b.c", default=0) == 0
        safe_get({}, "x.y.z") is None
    """
    keys = path.split(".")
    current = d
    for k in keys:
        if not isinstance(current, dict):
            return default
        current = current.get(k)
        if current is None:
            return default
    return current


def truncate(text: str, max_len: int = 200) -> str:
    """Truncate string to max_len chars with ellipsis if needed."""
    if not text:
        return ""
    if len(text) <= max_len:
        return text
    return text[: max_len - 3] + "..."


def parse_acceptance_criteria(description: str) -> list[str]:
    """Extract structured AC items from description text.

    Looks for patterns like:
    - "Acceptance Criteria:" followed by bulleted/numbered list
    - "AC:" sections
    - Numbered lists like "1. ..." "2. ..."

    Returns extracted items as list of strings. Empty list if nothing matches
    a recognized AC pattern (caller can fall back to raw description).
    """
    if not description:
        return []

    items: list[str] = []
    in_ac_section = False

    for raw_line in description.split("\n"):
        line = raw_line.strip()
        if not line:
            continue

        # AC section markers
        lower = line.lower()
        if any(
            marker in lower
            for marker in (
                "acceptance criteria:",
                "acceptance criteria",
                "**ac:**",
                "## ac",
                "## acceptance",
            )
        ):
            in_ac_section = True
            continue

        if in_ac_section:
            # Stop on next section header
            if line.startswith("#") or line.startswith("**") and line.endswith("**"):
                break

            # Extract bulleted/numbered items
            for prefix in ("- ", "* ", "+ "):
                if line.startswith(prefix):
                    items.append(line[len(prefix) :].strip())
                    break
            else:
                # Numbered: "1.", "1)", "1)"
                if line[:3].rstrip().rstrip(".").rstrip(")").isdigit():
                    rest = line.split(maxsplit=1)
                    if len(rest) > 1:
                        items.append(rest[1].strip())

    return items
