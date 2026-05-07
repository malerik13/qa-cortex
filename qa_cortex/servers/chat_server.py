"""MCP dispatch server for chat provider (Slack/etc)."""

from __future__ import annotations

from typing import Any

from mcp.server.fastmcp import FastMCP

from ._common import init_provider, safe_invoke


mcp = FastMCP("qa-cortex-chat")
provider = init_provider("chat")


@mcp.tool()
def list_channels(include_private: bool = False) -> list[dict[str, Any]] | dict:
    """List accessible channels."""
    return safe_invoke(provider.list_channels, include_private)


@mcp.tool()
def get_channel_history(
    channel_id: str,
    limit: int = 100,
    oldest_ts: str | None = None,
) -> list[dict[str, Any]] | dict:
    """Fetch channel message history."""
    return safe_invoke(provider.get_channel_history, channel_id, limit, oldest_ts)


@mcp.tool()
def get_thread_replies(
    channel_id: str,
    thread_ts: str,
) -> list[dict[str, Any]] | dict:
    """Fetch all replies in a thread."""
    return safe_invoke(provider.get_thread_replies, channel_id, thread_ts)


@mcp.tool()
def find_user(username_or_email: str) -> dict[str, Any] | None | dict:
    """Look up user by username or email."""
    return safe_invoke(provider.find_user, username_or_email)


@mcp.tool()
def post_message(
    channel_id: str,
    body: str,
    thread_ts: str | None = None,
    approved: bool = False,
) -> dict[str, Any]:
    """Post a message. Two-step approval gate (no comms by default)."""
    return safe_invoke(provider.post_message, channel_id, body, thread_ts, approved)


@mcp.tool()
def add_reaction(
    channel_id: str,
    message_ts: str,
    emoji: str,
    approved: bool = False,
) -> dict[str, Any]:
    """Add emoji reaction. Two-step approval gate."""
    return safe_invoke(provider.add_reaction, channel_id, message_ts, emoji, approved)


if __name__ == "__main__":
    mcp.run()
