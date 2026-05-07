"""qa_cortex.providers — Adapter framework for backend integrations.

The four Protocol interfaces (:class:`TicketingProvider`,
:class:`TestManagementProvider`, :class:`DocumentationProvider`,
:class:`ChatProvider`) define the contract.

Concrete implementations live in sibling modules (Phase 2 Step 2+):

- ``jira.py`` — Atlassian Jira (default)
- ``linear.py`` — Linear
- ``github.py`` — GitHub Issues
- ``testrail.py`` — TestRail
- ``confluence.py`` — Atlassian Confluence
- ``slack.py`` — Slack

Instance-specific providers stay in their own repos:

- ``youtrack.py`` (scalefinal-qa-assistant)
- ``allure.py`` (scalefinal-qa-assistant)

Status: Phase 2 Step 1 — Protocol contracts defined. Concrete adapters pending.
"""

from .base import (
    TicketingProvider,
    TestManagementProvider,
    DocumentationProvider,
    ChatProvider,
    load_provider,
)

__all__ = [
    "TicketingProvider",
    "TestManagementProvider",
    "DocumentationProvider",
    "ChatProvider",
    "load_provider",
]
