"""MCP dispatch server for documentation provider (Confluence/etc)."""

from __future__ import annotations

from typing import Any

from mcp.server.fastmcp import FastMCP

from ._common import init_provider, safe_invoke


mcp = FastMCP("qa-cortex-docs")
provider = init_provider("documentation")


@mcp.tool()
def search(
    query: str,
    space: str | None = None,
    max_results: int = 20,
) -> list[dict[str, Any]] | dict:
    """Search docs by query."""
    return safe_invoke(provider.search, query, space, max_results)


@mcp.tool()
def get_page(page_id: str) -> dict[str, Any]:
    """Fetch full page including body (converted to Markdown)."""
    return safe_invoke(provider.get_page, page_id)


@mcp.tool()
def list_spaces() -> list[dict[str, str]] | dict:
    """List user-accessible spaces."""
    return safe_invoke(provider.list_spaces)


if __name__ == "__main__":
    mcp.run()
