"""MCP dispatch server for ticketing provider.

Loads qa-cortex.config.toml at startup, instantiates the configured
TicketingProvider (Jira/Linear/GitHub/YouTrack), exposes its methods
as MCP tools.

Skills call ``mcp__qa_cortex_ticketing__<method>`` regardless of which
backend is configured.

Usage::

    python -m qa_cortex.servers.ticketing_server

(Or via .claude-plugin/plugin.json mcpServers config.)
"""

from __future__ import annotations

from typing import Any

from mcp.server.fastmcp import FastMCP

from ._common import init_provider, safe_invoke


mcp = FastMCP("qa-cortex-ticketing")
provider = init_provider("ticketing")


@mcp.tool()
def get_ticket(ticket_id: str) -> dict[str, Any]:
    """Fetch ticket by ID. Returns canonical shape (see Protocol docs)."""
    return safe_invoke(provider.get_ticket, ticket_id)


@mcp.tool()
def search_tickets(query: str, max_results: int = 50) -> list[dict[str, Any]] | dict:
    """Search tickets by free-text or provider-native syntax."""
    return safe_invoke(provider.search_tickets, query, max_results)


@mcp.tool()
def get_linked_tickets(ticket_id: str) -> list[dict[str, Any]] | dict:
    """Fetch tickets linked to this one."""
    return safe_invoke(provider.get_linked_tickets, ticket_id)


@mcp.tool()
def get_comments(ticket_id: str, max_results: int = 50) -> list[dict[str, Any]] | dict:
    """Fetch comments on a ticket."""
    return safe_invoke(provider.get_comments, ticket_id, max_results)


@mcp.tool()
def create_ticket(
    ticket_type: str,
    summary: str,
    description: str,
    custom_fields: dict[str, Any] | None = None,
    approved: bool = False,
) -> dict[str, Any]:
    """Create ticket. Two-step approval gate: approved=False returns preview."""
    return safe_invoke(
        provider.create_ticket, ticket_type, summary, description, custom_fields, approved
    )


@mcp.tool()
def add_comment(
    ticket_id: str,
    body: str,
    approved: bool = False,
) -> dict[str, Any]:
    """Add comment to ticket. Two-step approval gate."""
    return safe_invoke(provider.add_comment, ticket_id, body, approved)


@mcp.tool()
def transition_ticket(
    ticket_id: str,
    new_status: str,
    comment: str | None = None,
    approved: bool = False,
) -> dict[str, Any]:
    """Transition ticket status. Two-step approval gate."""
    return safe_invoke(provider.transition_ticket, ticket_id, new_status, comment, approved)


@mcp.tool()
def update_ticket(
    ticket_id: str,
    updates: dict[str, Any],
    approved: bool = False,
) -> dict[str, Any]:
    """Update ticket fields. Two-step approval gate."""
    return safe_invoke(provider.update_ticket, ticket_id, updates, approved)


if __name__ == "__main__":
    mcp.run()
