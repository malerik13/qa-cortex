"""Provider Protocol interfaces — the adapter contract.

Each provider category (ticketing, test management, documentation, chat) defines
an abstract Protocol that concrete implementations must satisfy. The brain calls
provider methods via dispatch MCP servers, which read configuration to select
which concrete implementation to use.

Design principles:

1. **Canonical schemas** — every method returns a normalized dict shape, not raw
   provider-specific JSON. Concrete adapters convert from provider-native shape
   to canonical shape.

2. **Two-step approval gate** — write methods accept ``approved: bool = False``
   parameter. When False, return preview payload. When True, perform actual write.
   This is the load-bearing safety pattern from scalefinal-qa-assistant.

3. **Idempotency hints** — preview responses include ``idempotency_check`` field
   pointing to similar-existing records (per CLAUDE.md anti-pattern #9).

4. **Honest gaps** — if a provider doesn't support a feature, the adapter raises
   ``NotImplementedError`` rather than silently degrading. Brain detects this
   and surfaces honestly to user.

5. **No magic state** — providers are stateless after initialization. Config
   passed at construction time, then methods are pure functions of inputs.

Status: Phase 2 Step 1 — Protocol definitions only. Concrete implementations
in subsequent steps (jira.py, testrail.py, confluence.py, slack.py).

See ``knowledge_base/design_docs/qa_cortex_v1.md`` §7 for full design rationale.
"""

from __future__ import annotations

from typing import Any, Protocol, runtime_checkable
from datetime import datetime


# ============================================================================
# Canonical shared schemas
# ============================================================================
#
# These TypedDict-like dict shapes describe the canonical normalized return
# types for provider methods. Concrete adapters must convert from their
# provider-native shapes to these. Brain code can safely consume these
# canonical shapes regardless of which adapter is active.
#
# We use plain dicts (not TypedDict) for v1.0 to keep dependency surface small.
# May migrate to TypedDict or pydantic in v2.0.


# ============================================================================
# TicketingProvider
# ============================================================================


@runtime_checkable
class TicketingProvider(Protocol):
    """Abstract ticketing system provider.

    Concrete implementations (each in its own module):

    - ``qa_cortex.providers.jira.JiraProvider`` — Atlassian Jira (default)
    - ``qa_cortex.providers.linear.LinearProvider``
    - ``qa_cortex.providers.github.GitHubProvider``
    - ``qa_cortex.providers.youtrack.YouTrackProvider`` (in scalefinal repo)

    Canonical ticket shape returned by ``get_ticket`` and friends::

        {
            "id": str,                           # Provider-native ID (e.g. "PROJ-123")
            "summary": str,                      # Ticket title / one-line description
            "description": str,                  # Full body / markdown
            "status": str,                       # Provider-native status name
            "priority": str | None,              # Provider-native priority
            "type": str,                         # "Bug" | "Story" | "Task" | "Epic" | provider-specific
            "acceptance_criteria": list[str],    # Parsed AC items if structured;
                                                 # empty list if unstructured
                                                 # (raw text in description still)
            "linked_tickets": list[dict],        # [{id, link_type, summary}, ...]
            "labels": list[str],                 # Provider tags / labels
            "assignee": str | None,              # Display name or username
            "reporter": str | None,
            "created_at": str,                   # ISO 8601
            "updated_at": str,                   # ISO 8601
            "url": str,                          # Direct browser URL to ticket
            "custom_fields": dict[str, Any],     # Provider-specific stuff brain may use
        }
    """

    def __init__(self, config: dict[str, Any]) -> None:
        """Initialize provider with config dict.

        Config dict comes from ``qa-cortex.config.toml`` ``[ticketing.<provider>]``
        section, with ``${VAR}`` env-var substitution already resolved.

        Implementations should validate required keys and fail fast at construction
        time, not at first method call.

        Args:
            config: Provider-specific config dict. Must include connection details
                (URL, credentials) and any provider-specific options.

        Raises:
            ValueError: if required config keys missing.
            ConnectionError: if connectivity check fails.
        """
        ...

    # ------ Read methods (Tier 1 — auto-approved per CLAUDE.md trust tiering) ------

    def get_ticket(self, ticket_id: str) -> dict[str, Any]:
        """Fetch ticket by ID.

        Args:
            ticket_id: Provider-native ticket ID (e.g. "PROJ-123" for Jira,
                "ENG-456" for Linear, "42" for GitHub Issues).

        Returns:
            Canonical ticket dict (shape documented above).

        Raises:
            ValueError: if ``ticket_id`` is malformed.
            LookupError: if ticket not found.
            ConnectionError: if backend unreachable.
        """
        ...

    def search_tickets(
        self,
        query: str,
        max_results: int = 50,
    ) -> list[dict[str, Any]]:
        """Search tickets by free-text query OR provider-specific syntax.

        Free-text query is best-effort across providers. For precise queries,
        users may pass provider-native syntax (Jira: JQL, Linear: filter expr,
        GitHub: search syntax).

        Args:
            query: Free-text or provider-native query.
            max_results: Cap on returned items.

        Returns:
            List of canonical ticket dicts (potentially with subset of fields
            populated for performance — at minimum: id, summary, status, type).
        """
        ...

    def get_linked_tickets(self, ticket_id: str) -> list[dict[str, Any]]:
        """Fetch tickets linked to this one.

        Returns:
            List of dicts: ``[{id, link_type, summary, status}, ...]`` where
            ``link_type`` is provider-native (e.g. "blocks", "blocked_by",
            "relates_to", "parent", "child").
        """
        ...

    def get_comments(
        self,
        ticket_id: str,
        max_results: int = 50,
    ) -> list[dict[str, Any]]:
        """Fetch comments on a ticket.

        Returns:
            List of dicts: ``[{id, author, body, created_at, updated_at}, ...]``
            sorted oldest-first.
        """
        ...

    # ------ Write methods (Tier 3 — explicit approval gate per CLAUDE.md) ------

    def create_ticket(
        self,
        ticket_type: str,
        summary: str,
        description: str,
        custom_fields: dict[str, Any] | None = None,
        approved: bool = False,
    ) -> dict[str, Any]:
        """Create a new ticket (bug/story/task/etc).

        Two-step approval gate:

        - ``approved=False`` (default): returns preview without creating.
        - ``approved=True``: creates ticket and returns canonical ticket dict.

        Preview response shape::

            {
                "preview": True,
                "payload": {
                    "ticket_type": str,
                    "summary": str,
                    "description": str,
                    "custom_fields": dict,
                    "would_create_at": str,    # provider URL (where it would land)
                },
                "idempotency_check": [
                    # similar OPEN tickets — brain surfaces these to user
                    # before approval to prevent duplicate creation
                    {"id": str, "summary": str, "status": str, "similarity_score": float},
                    ...
                ],
            }

        On approval, returns canonical ticket dict (same shape as ``get_ticket``).

        Args:
            ticket_type: "Bug" | "Story" | "Task" — provider-canonical names.
            summary: Title.
            description: Body in Markdown (adapter converts to provider-native if
                needed, e.g. Jira ADF).
            custom_fields: Provider-specific extras (severity, priority, labels,
                affected_version, parent_id, etc.). Adapter ignores unknown keys
                (logs warning) rather than failing.
            approved: Two-step gate flag. False = preview, True = execute.

        Returns:
            Either preview dict (``approved=False``) or canonical ticket dict
            (``approved=True``).

        Raises:
            ValueError: if required fields missing or invalid.
            PermissionError: if user lacks ticket creation permission.
        """
        ...

    def add_comment(
        self,
        ticket_id: str,
        body: str,
        approved: bool = False,
    ) -> dict[str, Any]:
        """Add a comment to a ticket.

        Two-step approval gate (same pattern as ``create_ticket``).

        Preview response shape::

            {
                "preview": True,
                "payload": {"ticket_id": str, "body": str},
                "ticket_summary": str,    # what we're commenting on
            }

        On approval, returns ``{"id": str, "url": str, "created_at": str}``.

        Args:
            ticket_id: Target ticket.
            body: Comment text in Markdown.
            approved: Two-step gate flag.
        """
        ...

    def transition_ticket(
        self,
        ticket_id: str,
        new_status: str,
        comment: str | None = None,
        approved: bool = False,
    ) -> dict[str, Any]:
        """Transition ticket to a new status.

        Two-step approval gate. Some providers require comment on transition
        (e.g. when moving to "Won't Fix" / "By Design").

        Args:
            ticket_id: Target ticket.
            new_status: Target status name (provider-canonical).
            comment: Optional transition comment.
            approved: Two-step gate flag.

        Returns:
            Preview dict or transition result with ``{ticket_id, old_status,
            new_status, transitioned_at}``.

        Raises:
            ValueError: if transition not allowed from current status (provider
                workflow may forbid certain transitions).
        """
        ...

    def update_ticket(
        self,
        ticket_id: str,
        updates: dict[str, Any],
        approved: bool = False,
    ) -> dict[str, Any]:
        """Update ticket fields (other than transitions, which use ``transition_ticket``).

        Two-step approval. Used for: severity changes, label updates, assignee
        changes, custom field updates, etc.

        Args:
            ticket_id: Target ticket.
            updates: Dict of field_name -> new_value. Field names provider-canonical.
            approved: Two-step gate flag.
        """
        ...


# ============================================================================
# TestManagementProvider
# ============================================================================


@runtime_checkable
class TestManagementProvider(Protocol):
    """Abstract test management provider (TestRail, Zephyr, Xray, Allure).

    Canonical test case shape::

        {
            "id": str,                          # Provider-native case ID
            "title": str,
            "section": str | None,              # TestRail section / Zephyr folder
            "preconditions": list[str],
            "steps": list[dict],                # [{step: str, expected: str}, ...]
            "expected_result": str,             # Top-level expected (some providers)
            "type": str | None,                 # "Functional" | "Smoke" | etc.
            "priority": str | None,
            "linked_tickets": list[str],        # IDs of related tickets
            "tags": list[str],
            "url": str,                         # Browser URL
            "custom_fields": dict[str, Any],
        }

    Canonical test run/result shape::

        {
            "case_id": str,
            "run_id": str,
            "status": str,                      # "Passed" | "Failed" | "Blocked" | "Untested"
            "comment": str | None,
            "tested_at": str,                   # ISO 8601
            "tester": str | None,
            "evidence": list[str],              # URLs to screenshots/logs/etc
        }
    """

    def __init__(self, config: dict[str, Any]) -> None:
        """Initialize with provider config."""
        ...

    # ------ Read methods (Tier 1) ------

    def get_test_case(self, case_id: str, include_steps: bool = True) -> dict[str, Any]:
        """Fetch test case by ID.

        Args:
            case_id: Provider-native ID.
            include_steps: If True, populate ``steps`` field with full step list.
                If False, ``steps`` may be ``None`` or empty (faster fetch).

        Returns:
            Canonical test case dict.
        """
        ...

    def search_test_cases(
        self,
        query: str,
        section: str | None = None,
        max_results: int = 50,
    ) -> list[dict[str, Any]]:
        """Search test cases by query, optionally scoped to section/folder."""
        ...

    def find_cases_by_linked_ticket(
        self,
        ticket_id: str,
        include_steps: bool = True,
    ) -> list[dict[str, Any]]:
        """Find test cases linked to a given ticket ID.

        This is the load-bearing query for QA flow Phase 1 — discovering
        existing coverage for a ticket before designing new scenarios.

        Args:
            ticket_id: Source ticket ID (e.g. Jira "PROJ-123").
            include_steps: If True, populate full ``steps`` lists. MANDATORY
                for accurate coverage analysis (without steps, brain can't tell
                if scenario is duplicate). Per CLAUDE.md hard rule.

        Returns:
            List of canonical test case dicts.
        """
        ...

    def get_run(self, run_id: str) -> dict[str, Any]:
        """Fetch test run / launch by ID.

        Returns shape::

            {
                "id": str,
                "name": str,
                "status": str,                  # provider-native
                "passed": int,
                "failed": int,
                "blocked": int,
                "untested": int,
                "started_at": str,
                "url": str,
            }
        """
        ...

    # ------ Write methods (Tier 3) ------

    def create_test_case(
        self,
        title: str,
        steps: list[dict[str, str]],
        section: str | None = None,
        priority: str | None = None,
        linked_tickets: list[str] | None = None,
        custom_fields: dict[str, Any] | None = None,
        approved: bool = False,
    ) -> dict[str, Any]:
        """Create a new test case.

        Two-step approval gate (same pattern as ticketing).
        """
        ...

    def add_result(
        self,
        case_id: str,
        run_id: str,
        status: str,
        comment: str | None = None,
        evidence_urls: list[str] | None = None,
        approved: bool = False,
    ) -> dict[str, Any]:
        """Record test execution result.

        Args:
            case_id: Test case ID.
            run_id: Test run / launch ID.
            status: "Passed" | "Failed" | "Blocked" | "Untested" (canonical;
                adapter maps to provider-native).
            comment: Test note / verdict.
            evidence_urls: Links to screenshots, logs, network captures.
            approved: Two-step gate.
        """
        ...


# ============================================================================
# DocumentationProvider
# ============================================================================


@runtime_checkable
class DocumentationProvider(Protocol):
    """Abstract documentation/wiki provider (Confluence, Notion, GitHub Wiki).

    Read-mostly. Write operations rare — most QA workflows read product docs,
    don't modify them.

    Canonical doc page shape::

        {
            "id": str,
            "title": str,
            "space": str | None,                # Confluence space, Notion db, etc.
            "url": str,
            "body_markdown": str,               # Converted to Markdown if provider
                                                # uses different format
            "labels": list[str],
            "updated_at": str,
            "author": str | None,
        }
    """

    def __init__(self, config: dict[str, Any]) -> None:
        """Initialize with provider config."""
        ...

    def search(
        self,
        query: str,
        space: str | None = None,
        max_results: int = 20,
    ) -> list[dict[str, Any]]:
        """Search docs by free-text query.

        Returns canonical page dicts with subset of fields (may omit ``body_markdown``
        for performance — fetch full via ``get_page``).
        """
        ...

    def get_page(self, page_id: str) -> dict[str, Any]:
        """Fetch full page including body."""
        ...

    def list_spaces(self) -> list[dict[str, str]]:
        """List available spaces / databases / wikis.

        Returns: ``[{key: str, name: str, description: str | None}, ...]``
        """
        ...


# ============================================================================
# ChatProvider
# ============================================================================


@runtime_checkable
class ChatProvider(Protocol):
    """Abstract chat / messaging provider (Slack, Teams, Discord).

    Per CLAUDE.md trust tiering: write operations (post_message, reply) are
    Tier 3 (explicit approval). Read operations (get_history, list_channels)
    are Tier 1.

    Canonical message shape::

        {
            "id": str,                          # Provider message ID
            "channel": str,                     # Channel ID or name
            "user": str,                        # Sender display name or ID
            "body": str,                        # Message text
            "timestamp": str,                   # ISO 8601
            "thread_ts": str | None,            # Parent thread timestamp if reply
            "reactions": dict[str, int],        # emoji -> count
            "permalink": str | None,
        }
    """

    def __init__(self, config: dict[str, Any]) -> None:
        """Initialize with provider config."""
        ...

    # ------ Read methods (Tier 1) ------

    def list_channels(
        self,
        include_private: bool = False,
    ) -> list[dict[str, Any]]:
        """List accessible channels.

        Returns: ``[{id, name, is_private, member_count, topic}, ...]``
        """
        ...

    def get_channel_history(
        self,
        channel_id: str,
        limit: int = 100,
        oldest_ts: str | None = None,
    ) -> list[dict[str, Any]]:
        """Fetch channel message history.

        Args:
            channel_id: Channel ID or name.
            limit: Max messages.
            oldest_ts: Optional ISO 8601 boundary — only newer than this.
        """
        ...

    def get_thread_replies(
        self,
        channel_id: str,
        thread_ts: str,
    ) -> list[dict[str, Any]]:
        """Fetch all replies in a thread."""
        ...

    def find_user(self, username_or_email: str) -> dict[str, Any] | None:
        """Look up user by username/email.

        Returns ``{id, name, real_name, email, is_bot}`` or None if not found.
        """
        ...

    # ------ Write methods (Tier 3) ------

    def post_message(
        self,
        channel_id: str,
        body: str,
        thread_ts: str | None = None,
        approved: bool = False,
    ) -> dict[str, Any]:
        """Post a message to a channel (or thread reply if ``thread_ts`` set).

        Two-step approval gate. Per CLAUDE.md default = no comms, requires
        explicit user approval in chat before sending.
        """
        ...

    def add_reaction(
        self,
        channel_id: str,
        message_ts: str,
        emoji: str,
        approved: bool = False,
    ) -> dict[str, Any]:
        """Add an emoji reaction to a message.

        Two-step approval (lightweight Tier 3 — reactions are still external comms).
        """
        ...


# ============================================================================
# Provider registry — runtime selection by config
# ============================================================================


def load_provider(category: str, config: dict[str, Any]) -> Any:
    """Load a configured provider by category and provider name.

    Reads config like::

        config["providers"]["ticketing"] = "jira"
        config["ticketing"]["jira"] = {"url": "...", "api_token": "..."}

    And returns an initialized JiraProvider instance.

    This is the dispatch function that MCP servers call.

    Args:
        category: One of "ticketing", "test_management", "documentation", "chat".
        config: Full qa-cortex config dict (parsed from qa-cortex.config.toml).

    Returns:
        Initialized provider instance satisfying the relevant Protocol.

    Raises:
        ValueError: if category unknown or provider name unrecognized.
        ImportError: if provider module not installed.
    """
    if "providers" not in config:
        raise ValueError("Config missing 'providers' section")

    selected = config["providers"].get(category)
    if not selected:
        raise ValueError(f"Category {category!r} not in config['providers']")

    provider_config = config.get(category, {}).get(selected, {})

    if category == "ticketing":
        if selected == "jira":
            from .jira import JiraProvider
            return JiraProvider(provider_config)
        elif selected == "linear":
            try:
                from .linear import LinearProvider  # type: ignore
            except ImportError as e:
                raise ImportError(
                    "LinearProvider not yet implemented. Phase 2 Step 2 covers Jira; "
                    "Linear adapter is Phase 3+ work or community contribution."
                ) from e
            return LinearProvider(provider_config)
        elif selected == "github":
            try:
                from .github import GitHubProvider  # type: ignore
            except ImportError as e:
                raise ImportError(
                    "GitHubProvider not yet implemented. Phase 2 Step 2 covers Jira; "
                    "GitHub adapter is community contribution work."
                ) from e
            return GitHubProvider(provider_config)
        elif selected == "youtrack":
            try:
                from .youtrack import YouTrackProvider  # type: ignore
            except ImportError as e:
                raise ImportError(
                    "YouTrackProvider not in qa-cortex (lives in private "
                    "scalefinal-qa-assistant repo). To use YouTrack, copy the "
                    "youtrack.py from scalefinal-qa-assistant or write your own."
                ) from e
            return YouTrackProvider(provider_config)

    elif category == "test_management":
        if selected == "testrail":
            from .testrail import TestRailProvider
            return TestRailProvider(provider_config)
        elif selected == "allure":
            try:
                from .allure import AllureProvider  # type: ignore
            except ImportError as e:
                raise ImportError(
                    "AllureProvider not in qa-cortex (private scalefinal repo). "
                    "Copy from there or implement against TestManagementProvider Protocol."
                ) from e
            return AllureProvider(provider_config)

    elif category == "documentation":
        if selected == "confluence":
            from .confluence import ConfluenceProvider
            return ConfluenceProvider(provider_config)

    elif category == "chat":
        if selected == "slack":
            from .slack import SlackProvider
            return SlackProvider(provider_config)

    elif category == "browser":
        # Playwright handled by Claude Code's built-in Playwright MCP, not via Python provider.
        # Return None — caller knows browser ops use mcp__playwright__* tools directly.
        return None

    raise ValueError(
        f"Unknown category={category!r} or provider={selected!r}. "
        f"See qa_cortex.config.VALID_PROVIDER_VALUES for valid combinations."
    )
