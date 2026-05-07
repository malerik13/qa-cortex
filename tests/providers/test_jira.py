"""Unit tests for JiraProvider.

Uses unittest.mock to stub the underlying ``atlassian.Jira`` client.
Tests verify:
- Config validation
- Canonical shape conversion
- Two-step approval gate (preview vs actual write)
- Error handling
- Idempotency check pattern
"""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest

from qa_cortex.providers.jira import JiraProvider


@pytest.fixture
def valid_config() -> dict:
    return {
        "url": "https://test.atlassian.net",
        "email": "test@example.com",
        "api_token": "fake-token",
        "ticket_prefix": "TEST",
        "default_project_key": "TEST",
    }


@pytest.fixture
def sample_jira_issue() -> dict:
    """Mimics Jira API issue response."""
    return {
        "key": "TEST-123",
        "fields": {
            "summary": "Sample ticket for testing",
            "description": "Description body\n\nAcceptance Criteria:\n- AC item 1\n- AC item 2",
            "status": {"name": "Open"},
            "priority": {"name": "Medium"},
            "issuetype": {"name": "Bug"},
            "labels": ["smoke", "regression"],
            "assignee": {"displayName": "Alice Tester"},
            "reporter": {"displayName": "Bob Reporter"},
            "created": "2026-05-01T10:30:00.000+0000",
            "updated": "2026-05-07T14:22:00.000+0000",
            "issuelinks": [
                {
                    "type": {"name": "blocks"},
                    "outwardIssue": {
                        "key": "TEST-456",
                        "fields": {
                            "summary": "Linked ticket",
                            "status": {"name": "In Progress"},
                        },
                    },
                }
            ],
            "customfield_10001": "custom value",
        },
    }


# ============================================================
# Config validation
# ============================================================


class TestConfigValidation:
    def test_missing_required_keys_raises_value_error(self) -> None:
        config = {"url": "https://test.atlassian.net"}
        with pytest.raises(ValueError, match="missing required keys"):
            JiraProvider(config)

    def test_all_required_keys_valid(self, valid_config: dict) -> None:
        with patch("qa_cortex.providers.jira.Jira"):
            provider = JiraProvider(valid_config)
            assert provider.ticket_prefix == "TEST"
            assert provider.default_project_key == "TEST"


# ============================================================
# Read methods
# ============================================================


class TestGetTicket:
    def test_returns_canonical_shape(self, valid_config: dict, sample_jira_issue: dict) -> None:
        with patch("qa_cortex.providers.jira.Jira") as MockJira:
            MockJira.return_value.issue.return_value = sample_jira_issue
            provider = JiraProvider(valid_config)

            result = provider.get_ticket("TEST-123")

            assert result["id"] == "TEST-123"
            assert result["summary"] == "Sample ticket for testing"
            assert result["status"] == "Open"
            assert result["priority"] == "Medium"
            assert result["type"] == "Bug"
            assert result["labels"] == ["smoke", "regression"]
            assert result["assignee"] == "Alice Tester"
            assert result["url"] == "https://test.atlassian.net/browse/TEST-123"
            assert result["created_at"] == "2026-05-01T10:30:00Z"

    def test_extracts_acceptance_criteria(
        self, valid_config: dict, sample_jira_issue: dict
    ) -> None:
        with patch("qa_cortex.providers.jira.Jira") as MockJira:
            MockJira.return_value.issue.return_value = sample_jira_issue
            provider = JiraProvider(valid_config)

            result = provider.get_ticket("TEST-123")

            assert "AC item 1" in result["acceptance_criteria"]
            assert "AC item 2" in result["acceptance_criteria"]

    def test_includes_linked_tickets(
        self, valid_config: dict, sample_jira_issue: dict
    ) -> None:
        with patch("qa_cortex.providers.jira.Jira") as MockJira:
            MockJira.return_value.issue.return_value = sample_jira_issue
            provider = JiraProvider(valid_config)

            result = provider.get_ticket("TEST-123")

            assert len(result["linked_tickets"]) == 1
            assert result["linked_tickets"][0]["id"] == "TEST-456"
            assert result["linked_tickets"][0]["link_type"] == "blocks"

    def test_passes_through_custom_fields(
        self, valid_config: dict, sample_jira_issue: dict
    ) -> None:
        with patch("qa_cortex.providers.jira.Jira") as MockJira:
            MockJira.return_value.issue.return_value = sample_jira_issue
            provider = JiraProvider(valid_config)

            result = provider.get_ticket("TEST-123")

            assert result["custom_fields"]["customfield_10001"] == "custom value"

    def test_malformed_id_raises_value_error(self, valid_config: dict) -> None:
        with patch("qa_cortex.providers.jira.Jira"):
            provider = JiraProvider(valid_config)

            with pytest.raises(ValueError, match="Malformed ticket_id"):
                provider.get_ticket("not-a-valid-id")  # missing dash structure

            with pytest.raises(ValueError, match="Malformed ticket_id"):
                provider.get_ticket("")

    def test_404_raises_lookup_error(self, valid_config: dict) -> None:
        with patch("qa_cortex.providers.jira.Jira") as MockJira:
            MockJira.return_value.issue.side_effect = Exception("HTTPError 404 not found")
            provider = JiraProvider(valid_config)

            with pytest.raises(LookupError, match="not found"):
                provider.get_ticket("TEST-999")


class TestSearchTickets:
    def test_jql_passes_through_when_jql_detected(self, valid_config: dict) -> None:
        with patch("qa_cortex.providers.jira.Jira") as MockJira:
            MockJira.return_value.jql.return_value = {"issues": []}
            provider = JiraProvider(valid_config)

            provider.search_tickets("project = TEST AND status = Open")

            # Should have called jql with the JQL string
            MockJira.return_value.jql.assert_called_once()
            args, _ = MockJira.return_value.jql.call_args
            assert "project = TEST" in args[0]

    def test_free_text_wrapped_in_text_search(self, valid_config: dict) -> None:
        with patch("qa_cortex.providers.jira.Jira") as MockJira:
            MockJira.return_value.jql.return_value = {"issues": []}
            provider = JiraProvider(valid_config)

            provider.search_tickets("login bug")

            args, _ = MockJira.return_value.jql.call_args
            assert 'project = TEST' in args[0]
            assert 'text ~ "login bug"' in args[0]


# ============================================================
# Write methods — two-step approval gate
# ============================================================


class TestCreateTicket:
    def test_preview_mode_returns_payload_without_calling_create(
        self, valid_config: dict
    ) -> None:
        with patch("qa_cortex.providers.jira.Jira") as MockJira:
            MockJira.return_value.jql.return_value = {"issues": []}  # no similar
            provider = JiraProvider(valid_config)

            result = provider.create_ticket(
                ticket_type="Bug",
                summary="Test bug",
                description="Test description",
                approved=False,
            )

            assert result["preview"] is True
            assert result["payload"]["summary"] == "Test bug"
            assert result["payload"]["ticket_type"] == "Bug"
            assert "idempotency_check" in result
            # Critical: create_issue NOT called in preview
            MockJira.return_value.create_issue.assert_not_called()

    def test_approved_true_actually_creates(
        self, valid_config: dict, sample_jira_issue: dict
    ) -> None:
        with patch("qa_cortex.providers.jira.Jira") as MockJira:
            MockJira.return_value.create_issue.return_value = {"key": "TEST-789"}
            MockJira.return_value.issue.return_value = sample_jira_issue
            provider = JiraProvider(valid_config)

            result = provider.create_ticket(
                ticket_type="Bug",
                summary="Test bug",
                description="Test description",
                approved=True,
            )

            MockJira.return_value.create_issue.assert_called_once()
            assert result["id"] == "TEST-123"  # from sample, since we mock fetch

    def test_idempotency_check_returns_similar_tickets(
        self, valid_config: dict
    ) -> None:
        with patch("qa_cortex.providers.jira.Jira") as MockJira:
            MockJira.return_value.jql.return_value = {
                "issues": [
                    {
                        "key": "TEST-111",
                        "fields": {
                            "summary": "Existing similar bug",
                            "status": {"name": "Open"},
                        },
                    }
                ]
            }
            provider = JiraProvider(valid_config)

            result = provider.create_ticket(
                ticket_type="Bug",
                summary="Existing similar bug we might duplicate",
                description="...",
                approved=False,
            )

            assert len(result["idempotency_check"]) > 0
            assert result["idempotency_check"][0]["id"] == "TEST-111"
            assert "similarity_score" in result["idempotency_check"][0]

    def test_empty_summary_raises(self, valid_config: dict) -> None:
        with patch("qa_cortex.providers.jira.Jira"):
            provider = JiraProvider(valid_config)

            with pytest.raises(ValueError, match="non-empty summary"):
                provider.create_ticket(
                    ticket_type="Bug",
                    summary="",
                    description="...",
                )


class TestAddComment:
    def test_preview_mode_does_not_post(self, valid_config: dict, sample_jira_issue: dict) -> None:
        with patch("qa_cortex.providers.jira.Jira") as MockJira:
            MockJira.return_value.issue.return_value = sample_jira_issue
            provider = JiraProvider(valid_config)

            result = provider.add_comment("TEST-123", "Test comment", approved=False)

            assert result["preview"] is True
            assert result["payload"]["body"] == "Test comment"
            assert result["ticket_summary"]  # has context
            MockJira.return_value.issue_add_comment.assert_not_called()

    def test_approved_actually_posts(
        self, valid_config: dict, sample_jira_issue: dict
    ) -> None:
        with patch("qa_cortex.providers.jira.Jira") as MockJira:
            MockJira.return_value.issue_add_comment.return_value = {
                "id": "10001",
                "created": "2026-05-07T15:00:00.000+0000",
            }
            provider = JiraProvider(valid_config)

            result = provider.add_comment("TEST-123", "Test comment", approved=True)

            MockJira.return_value.issue_add_comment.assert_called_once_with(
                "TEST-123", "Test comment"
            )
            assert result["id"] == "10001"


class TestTransitionTicket:
    def test_preview_returns_transition_id(self, valid_config: dict) -> None:
        with patch("qa_cortex.providers.jira.Jira") as MockJira:
            MockJira.return_value.issue.return_value = {
                "fields": {"status": {"name": "Open"}},
                "transitions": [
                    {"id": "31", "name": "Done", "to": {"name": "Done"}},
                ],
            }
            provider = JiraProvider(valid_config)

            result = provider.transition_ticket("TEST-123", "Done", approved=False)

            assert result["preview"] is True
            assert result["payload"]["transition_id"] == "31"
            MockJira.return_value.set_issue_status.assert_not_called()

    def test_invalid_transition_raises(self, valid_config: dict) -> None:
        with patch("qa_cortex.providers.jira.Jira") as MockJira:
            MockJira.return_value.issue.return_value = {
                "fields": {"status": {"name": "Open"}},
                "transitions": [
                    {"id": "11", "name": "Start Progress", "to": {"name": "In Progress"}},
                ],
            }
            provider = JiraProvider(valid_config)

            with pytest.raises(ValueError, match="not in allowed transitions"):
                provider.transition_ticket("TEST-123", "NonExistentStatus", approved=False)


# ============================================================
# Internal helpers
# ============================================================


class TestBuildJQL:
    def test_jql_pattern_passes_through(self, valid_config: dict) -> None:
        with patch("qa_cortex.providers.jira.Jira"):
            provider = JiraProvider(valid_config)
            jql = "status = Open AND priority = High"
            assert provider._build_jql(jql) == jql

    def test_free_text_wrapped(self, valid_config: dict) -> None:
        with patch("qa_cortex.providers.jira.Jira"):
            provider = JiraProvider(valid_config)
            result = provider._build_jql("login bug")
            assert "project = TEST" in result
            assert 'text ~ "login bug"' in result


class TestNormalizationHelpers:
    def test_normalize_ticket_handles_missing_fields(self, valid_config: dict) -> None:
        with patch("qa_cortex.providers.jira.Jira"):
            provider = JiraProvider(valid_config)

            # Minimal Jira response
            minimal = {"key": "TEST-1", "fields": {"summary": "S"}}
            result = provider._normalize_ticket(minimal)

            assert result["id"] == "TEST-1"
            assert result["summary"] == "S"
            assert result["status"] == ""
            assert result["priority"] is None
            assert result["labels"] == []
