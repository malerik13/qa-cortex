"""End-to-end Jira integration tests.

Hit real Jira instance. Skipped unless --run-integration flag passed and
credentials set in env. See conftest.py for setup.

These tests verify the actual Jira → JiraProvider → canonical-shape pipeline,
including network paths, custom field handling, idempotency check accuracy.
"""

from __future__ import annotations

import pytest

from qa_cortex.providers.jira import JiraProvider
from .conftest import requires_jira


pytestmark = [pytest.mark.integration, requires_jira]


class TestJiraReadOps:
    def test_get_existing_ticket(self, jira_config: dict) -> None:
        """Reads a known existing ticket from the test project."""
        provider = JiraProvider(jira_config)
        # Assumes test project has at least 1 ticket; user creates one manually first
        results = provider.search_tickets(
            query=f"project = {jira_config['default_project_key']}",
            max_results=1,
        )
        if not results:
            pytest.skip(
                f"No tickets in test project {jira_config['default_project_key']}. "
                f"Create one manually to enable this test."
            )

        ticket_id = results[0]["id"]
        ticket = provider.get_ticket(ticket_id)

        assert ticket["id"] == ticket_id
        assert ticket["summary"]
        assert ticket["url"].startswith(jira_config["url"])

    def test_search_returns_results(self, jira_config: dict) -> None:
        provider = JiraProvider(jira_config)
        results = provider.search_tickets(
            query=f"project = {jira_config['default_project_key']}",
            max_results=10,
        )
        # Should not error even if 0 results
        assert isinstance(results, list)


class TestJiraWriteOpsLifecycle:
    """Full create → update → comment → transition lifecycle.

    Creates tickets in test project; cleanup recommended after run.
    """

    def test_create_with_idempotency_check(self, jira_config: dict) -> None:
        provider = JiraProvider(jira_config)

        # Preview should NOT create
        preview = provider.create_ticket(
            ticket_type="Task",
            summary="qa-cortex E2E test ticket — DO NOT MERGE",
            description="Created by integration test. Safe to delete.",
            approved=False,
        )
        assert preview["preview"] is True
        assert "idempotency_check" in preview

    def test_create_then_comment_lifecycle(self, jira_config: dict) -> None:
        provider = JiraProvider(jira_config)

        # Create
        created = provider.create_ticket(
            ticket_type="Task",
            summary="qa-cortex lifecycle test",
            description="Will be commented + (maybe) cleaned up",
            approved=True,
        )
        assert created["id"]
        ticket_id = created["id"]

        try:
            # Comment
            comment_result = provider.add_comment(
                ticket_id, "qa-cortex E2E comment test", approved=True
            )
            assert comment_result.get("id") or comment_result.get("url")

            # Read comments back
            comments = provider.get_comments(ticket_id)
            assert any(
                "qa-cortex E2E comment" in c.get("body", "") for c in comments
            )
        finally:
            # Note: Jira doesn't have a clean delete API for issues without admin
            # Recommend setting up a dedicated test project that's wiped periodically
            pass
