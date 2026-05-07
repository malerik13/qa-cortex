"""MCP dispatch server for test management provider (TestRail/etc)."""

from __future__ import annotations

from typing import Any

from mcp.server.fastmcp import FastMCP

from ._common import init_provider, safe_invoke


mcp = FastMCP("qa-cortex-test-mgmt")
provider = init_provider("test_management")


@mcp.tool()
def get_test_case(case_id: str, include_steps: bool = True) -> dict[str, Any]:
    """Fetch test case. ``include_steps`` defaults True (CLAUDE.md MANDATORY rule)."""
    return safe_invoke(provider.get_test_case, case_id, include_steps)


@mcp.tool()
def search_test_cases(
    query: str,
    section: str | None = None,
    max_results: int = 50,
) -> list[dict[str, Any]] | dict:
    """Search test cases."""
    return safe_invoke(provider.search_test_cases, query, section, max_results)


@mcp.tool()
def find_cases_by_linked_ticket(
    ticket_id: str,
    include_steps: bool = True,
) -> list[dict[str, Any]] | dict:
    """Find test cases linked to a ticket. Load-bearing for QA Phase 1."""
    return safe_invoke(provider.find_cases_by_linked_ticket, ticket_id, include_steps)


@mcp.tool()
def get_run(run_id: str) -> dict[str, Any]:
    """Fetch test run / launch with pass/fail/blocked counts."""
    return safe_invoke(provider.get_run, run_id)


@mcp.tool()
def create_test_case(
    title: str,
    steps: list[dict[str, str]],
    section: str | None = None,
    priority: str | None = None,
    linked_tickets: list[str] | None = None,
    custom_fields: dict[str, Any] | None = None,
    approved: bool = False,
) -> dict[str, Any]:
    """Create test case. Two-step approval gate."""
    return safe_invoke(
        provider.create_test_case,
        title, steps, section, priority, linked_tickets, custom_fields, approved,
    )


@mcp.tool()
def add_result(
    case_id: str,
    run_id: str,
    status: str,
    comment: str | None = None,
    evidence_urls: list[str] | None = None,
    approved: bool = False,
) -> dict[str, Any]:
    """Record test result. Two-step approval gate."""
    return safe_invoke(
        provider.add_result, case_id, run_id, status, comment, evidence_urls, approved,
    )


if __name__ == "__main__":
    mcp.run()
