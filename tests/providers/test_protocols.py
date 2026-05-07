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
    """Verify dispatch function signature is reserved."""

    def test_raises_not_implemented_phase_a(self) -> None:
        # Phase 2 Step 1 — stub returns informative NotImplementedError
        with pytest.raises(NotImplementedError, match="not yet implemented"):
            load_provider("ticketing", {})


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
