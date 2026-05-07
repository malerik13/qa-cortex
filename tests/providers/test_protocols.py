"""Tests for Provider Protocol structural integrity.

Verifies that the abstract Protocol interfaces in ``qa_cortex.providers.base``
have the expected method signatures and runtime_checkable behavior.

Concrete adapter tests come in Phase 2 Step 2+ as adapters are implemented.
"""

from __future__ import annotations

import inspect

import pytest

from qa_cortex.providers import (
    TicketingProvider,
    TestManagementProvider,
    DocumentationProvider,
    ChatProvider,
    load_provider,
)


class TestTicketingProvider:
    """Verify TicketingProvider Protocol surface."""

    EXPECTED_METHODS = {
        "get_ticket",
        "search_tickets",
        "get_linked_tickets",
        "get_comments",
        "create_ticket",
        "add_comment",
        "transition_ticket",
        "update_ticket",
    }

    def test_all_expected_methods_present(self) -> None:
        actual = {m for m in dir(TicketingProvider) if not m.startswith("_")}
        missing = self.EXPECTED_METHODS - actual
        assert not missing, f"Missing methods: {missing}"

    def test_create_ticket_has_approved_param(self) -> None:
        sig = inspect.signature(TicketingProvider.create_ticket)
        assert "approved" in sig.parameters
        assert sig.parameters["approved"].default is False, (
            "approved param must default to False (preview mode)"
        )

    def test_runtime_checkable(self) -> None:
        # Should not raise
        assert hasattr(TicketingProvider, "_is_runtime_protocol")


class TestTestManagementProvider:
    """Verify TestManagementProvider Protocol surface."""

    EXPECTED_METHODS = {
        "get_test_case",
        "search_test_cases",
        "find_cases_by_linked_ticket",
        "get_run",
        "create_test_case",
        "add_result",
    }

    def test_all_expected_methods_present(self) -> None:
        actual = {m for m in dir(TestManagementProvider) if not m.startswith("_")}
        missing = self.EXPECTED_METHODS - actual
        assert not missing, f"Missing methods: {missing}"

    def test_find_cases_by_linked_ticket_has_include_steps(self) -> None:
        sig = inspect.signature(TestManagementProvider.find_cases_by_linked_ticket)
        assert "include_steps" in sig.parameters
        assert sig.parameters["include_steps"].default is True, (
            "include_steps must default True per CLAUDE.md MANDATORY rule"
        )


class TestDocumentationProvider:
    """Verify DocumentationProvider Protocol surface."""

    EXPECTED_METHODS = {"search", "get_page", "list_spaces"}

    def test_all_expected_methods_present(self) -> None:
        actual = {m for m in dir(DocumentationProvider) if not m.startswith("_")}
        missing = self.EXPECTED_METHODS - actual
        assert not missing, f"Missing methods: {missing}"


class TestChatProvider:
    """Verify ChatProvider Protocol surface."""

    EXPECTED_METHODS = {
        "list_channels",
        "get_channel_history",
        "get_thread_replies",
        "find_user",
        "post_message",
        "add_reaction",
    }

    def test_all_expected_methods_present(self) -> None:
        actual = {m for m in dir(ChatProvider) if not m.startswith("_")}
        missing = self.EXPECTED_METHODS - actual
        assert not missing, f"Missing methods: {missing}"

    def test_post_message_has_approved_param(self) -> None:
        sig = inspect.signature(ChatProvider.post_message)
        assert "approved" in sig.parameters
        assert sig.parameters["approved"].default is False, (
            "post_message defaults to preview (no comms by default per CLAUDE.md)"
        )


class TestLoadProvider:
    """Verify dispatch function works post-Phase 2 Step 7."""

    def test_dispatches_jira(self) -> None:
        from unittest.mock import patch

        config = {
            "providers": {"ticketing": "jira"},
            "ticketing": {
                "jira": {
                    "url": "https://test.atlassian.net",
                    "email": "test@example.com",
                    "api_token": "fake",
                    "ticket_prefix": "TEST",
                    "default_project_key": "TEST",
                }
            },
        }

        with patch("qa_cortex.providers.jira.Jira"):
            provider = load_provider("ticketing", config)

        from qa_cortex.providers.jira import JiraProvider
        assert isinstance(provider, JiraProvider)

    def test_dispatches_testrail(self) -> None:
        from unittest.mock import patch

        config = {
            "providers": {"test_management": "testrail"},
            "test_management": {
                "testrail": {
                    "url": "https://test.testrail.io",
                    "username": "u",
                    "api_key": "k",
                    "project_id": 1,
                    "linked_ticket_field": "custom_jira_id",
                }
            },
        }

        with patch("qa_cortex.providers.testrail.TestRailAPI"):
            provider = load_provider("test_management", config)

        from qa_cortex.providers.testrail import TestRailProvider
        assert isinstance(provider, TestRailProvider)

    def test_browser_returns_none(self) -> None:
        # Playwright is handled by Claude Code's built-in MCP — provider dispatch returns None
        config = {"providers": {"browser": "playwright"}}
        result = load_provider("browser", config)
        assert result is None

    def test_unknown_category_raises(self) -> None:
        with pytest.raises(ValueError, match="not in config"):
            load_provider("ticketing", {"providers": {}})

    def test_youtrack_raises_import_error_with_helpful_msg(self) -> None:
        config = {
            "providers": {"ticketing": "youtrack"},
            "ticketing": {"youtrack": {"url": "x"}},
        }
        with pytest.raises(ImportError, match="YouTrackProvider not in qa-cortex"):
            load_provider("ticketing", config)


class TestApprovalGatePattern:
    """Verify all write methods follow the two-step approval gate pattern."""

    WRITE_METHODS_BY_PROTOCOL = {
        TicketingProvider: ["create_ticket", "add_comment", "transition_ticket", "update_ticket"],
        TestManagementProvider: ["create_test_case", "add_result"],
        ChatProvider: ["post_message", "add_reaction"],
    }

    def test_all_write_methods_have_approved_param_defaulting_false(self) -> None:
        """Every write method MUST accept ``approved: bool = False``.

        This is the load-bearing safety pattern. If a contract method is added
        without it, this test fails — forcing explicit decision rather than
        silent regression.
        """
        for protocol, method_names in self.WRITE_METHODS_BY_PROTOCOL.items():
            for method_name in method_names:
                method = getattr(protocol, method_name)
                sig = inspect.signature(method)
                assert "approved" in sig.parameters, (
                    f"{protocol.__name__}.{method_name} must accept 'approved' param"
                )
                assert sig.parameters["approved"].default is False, (
                    f"{protocol.__name__}.{method_name}.approved must default to False"
                )
