"""Full QA workflow integration test.

Simulates Phase 1 of QA flow: brain receives ticket → loads context → drafts intake.

This is the Phase 2 success gate test. If this passes against a real Jira+TestRail+
Confluence stack, qa-cortex Phase 2 is validated.
"""

from __future__ import annotations

import pytest

from qa_cortex.providers import load_provider
from .conftest import requires_jira, requires_testrail


pytestmark = [pytest.mark.integration]


@requires_jira
@requires_testrail
def test_phase_1_full_intake(jira_config: dict, testrail_config: dict) -> None:
    """Simulate brain's Phase 1 pre-load batch.

    Steps:
    1. Search Jira for a test ticket
    2. Get ticket details
    3. Get linked tickets
    4. Get comments
    5. Find linked test cases in TestRail
    6. Verify all returned canonical shapes

    Each provider call mirrors what the brain does in start-ticket-test
    skill Step 3 (parallel pre-load batch).
    """
    config = {
        "providers": {
            "ticketing": "jira",
            "test_management": "testrail",
        },
        "ticketing": {"jira": jira_config},
        "test_management": {"testrail": testrail_config},
    }

    ticketing = load_provider("ticketing", config)
    test_mgmt = load_provider("test_management", config)

    # Find a ticket in test project
    candidates = ticketing.search_tickets(
        query=f"project = {jira_config['default_project_key']}",
        max_results=1,
    )
    if not candidates:
        pytest.skip("No tickets in test Jira project — create one manually first")

    ticket_id = candidates[0]["id"]

    # Phase 1 batch
    ticket = ticketing.get_ticket(ticket_id)
    linked = ticketing.get_linked_tickets(ticket_id)
    comments = ticketing.get_comments(ticket_id)
    cases = test_mgmt.find_cases_by_linked_ticket(ticket_id)

    # Verify shapes
    assert "id" in ticket and ticket["id"] == ticket_id
    assert "summary" in ticket
    assert "url" in ticket
    assert isinstance(linked, list)
    assert isinstance(comments, list)
    assert isinstance(cases, list)

    print(f"\n✓ Phase 1 intake complete for {ticket_id}:")
    print(f"  Ticket: {ticket['summary']}")
    print(f"  Linked tickets: {len(linked)}")
    print(f"  Comments: {len(comments)}")
    print(f"  TestRail cases: {len(cases)}")
