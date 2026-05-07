# Adding a New Provider

> Step-by-step guide for adding a backend (Linear, GitHub Issues, Notion, etc.).
> Reading time: ~10 min.

---

## Overview

qa-cortex's adapter framework makes adding providers structured. To add (say) Linear as a TicketingProvider:

1. Implement `LinearProvider` class satisfying `TicketingProvider` Protocol
2. Add to `load_provider()` dispatch in `qa_cortex/providers/base.py`
3. Add config validation entry
4. Write tests
5. Document in README + INSTALL

Effort: 2-4 hours per provider for someone familiar with Python + the target API.

---

## Step 1 — Pick the contract

Identify which Protocol you're implementing:

| Category | Protocol | Methods |
|---|---|---|
| Ticketing | `TicketingProvider` | get/search/get_linked/get_comments + create/update/comment/transition |
| Test management | `TestManagementProvider` | get_case/search/find_by_ticket/get_run + create_case/add_result |
| Documentation | `DocumentationProvider` | search/get_page/list_spaces |
| Chat | `ChatProvider` | list/history/replies/find_user + post/react |

Read the Protocol definition in `qa_cortex/providers/base.py` — every method has detailed docstring describing canonical return shape.

---

## Step 2 — Choose underlying library

Look for mature Python SDK:

| Provider | Recommended library | License |
|---|---|---|
| Linear | community Python wrappers OR direct GraphQL via `gql` | varies |
| GitHub Issues | `PyGithub` (3rd party) or `ghapi` | LGPL / Apache |
| Notion | `notion-client` (official) | MIT |
| Microsoft Teams | `botbuilder-core` or direct Graph API | MIT |
| YouTrack | direct REST via `requests` | — |
| Zephyr | direct REST via `requests` | — |

**Avoid:** wrapping MCP servers as subprocesses. Use Python libraries directly when available.

---

## Step 3 — Implement the adapter

Create `qa_cortex/providers/<name>.py`:

```python
"""<Provider> — concrete TicketingProvider implementation for <Provider>."""

from __future__ import annotations

from typing import Any

# import provider library
from your_lib import YourClient

from ._normalizers import normalize_iso8601, safe_get


class YourProvider:
    """TicketingProvider for YourBackend.

    Config dict shape::

        {
            "url": "https://...",
            "api_token": "...",
            # provider-specific keys
        }

    Required: url, api_token.
    """

    REQUIRED_CONFIG_KEYS = {"url", "api_token"}

    def __init__(self, config: dict[str, Any]) -> None:
        missing = self.REQUIRED_CONFIG_KEYS - set(config.keys())
        if missing:
            raise ValueError(
                f"YourProvider config missing required keys: {sorted(missing)}"
            )

        self.config = config
        self._client = YourClient(
            url=config["url"],
            token=config["api_token"],
        )

    # Read methods (Tier 1)

    def get_ticket(self, ticket_id: str) -> dict[str, Any]:
        try:
            raw = self._client.get_issue(ticket_id)
        except YourLib404 as e:
            raise LookupError(f"Ticket {ticket_id} not found") from e
        except YourLibException as e:
            raise ConnectionError(f"Fetch failed: {e}") from e

        return self._normalize(raw)

    # ... implement all Protocol methods

    # Write methods (Tier 3 — two-step approval gate)

    def create_ticket(
        self,
        ticket_type: str,
        summary: str,
        description: str,
        custom_fields: dict[str, Any] | None = None,
        approved: bool = False,
    ) -> dict[str, Any]:
        if not summary:
            raise ValueError("create_ticket requires non-empty summary")

        if not approved:
            # PREVIEW MODE — DO NOT EXECUTE WRITE
            similar = self._find_similar_open(summary)
            return {
                "preview": True,
                "payload": {
                    "ticket_type": ticket_type,
                    "summary": summary,
                    "description": description,
                    # ...
                },
                "idempotency_check": similar,
            }

        # ACTUAL WRITE
        result = self._client.create(...)
        return self._normalize(result)

    def _normalize(self, raw: dict) -> dict:
        """Convert provider-native shape → canonical dict."""
        return {
            "id": raw.get("key"),
            "summary": raw.get("title"),
            "description": raw.get("body"),
            "status": safe_get(raw, "state.name"),
            # ... canonical fields per Protocol docstring
        }
```

### Critical: two-step approval gate

EVERY write method MUST:

1. Accept `approved: bool = False` parameter
2. Return preview dict (with `"preview": True`) when `approved=False`
3. Execute actual write only when `approved=True`

The test `tests/providers/test_protocols.py::TestApprovalGatePattern::test_all_write_methods_have_approved_param_defaulting_false` enforces this. Cannot merge regression.

### Critical: canonical schemas

Read methods MUST return dicts matching shapes in Protocol docstrings. Brain code consumes these consistently. If your provider has unique fields that don't fit canonical shape, put them in `custom_fields` dict.

---

## Step 4 — Add to dispatch

In `qa_cortex/providers/base.py`, find `load_provider()`:

```python
def load_provider(category: str, config: dict[str, Any]) -> Any:
    # ...
    if category == "ticketing":
        if selected == "jira":
            from .jira import JiraProvider
            return JiraProvider(provider_config)
        elif selected == "linear":               # ← ADD
            from .linear import LinearProvider
            return LinearProvider(provider_config)
        elif selected == "your_provider":         # ← OR HERE
            from .your_provider import YourProvider
            return YourProvider(provider_config)
        # ...
```

Use lazy import — only load when selected.

---

## Step 5 — Add config validation

In `qa_cortex/config/loader.py`, update:

```python
VALID_PROVIDER_VALUES = {
    "ticketing": {"jira", "linear", "github", "youtrack", "your_provider"},  # ← ADD
    # ...
}
```

---

## Step 6 — Write tests

Create `tests/providers/test_<name>.py`:

```python
"""Unit tests for YourProvider."""

from __future__ import annotations

from unittest.mock import patch

import pytest

from qa_cortex.providers.your_provider import YourProvider


@pytest.fixture
def valid_config() -> dict:
    return {
        "url": "https://test.example.com",
        "api_token": "fake-token",
    }


@pytest.fixture
def sample_issue() -> dict:
    return {
        # mimic your provider's API response shape
        "key": "TEST-123",
        "title": "Sample",
        # ...
    }


class TestConfigValidation:
    def test_missing_keys_raises(self) -> None:
        with pytest.raises(ValueError, match="missing required keys"):
            YourProvider({})


class TestGetTicket:
    def test_returns_canonical_shape(self, valid_config, sample_issue) -> None:
        with patch("qa_cortex.providers.your_provider.YourClient") as MockClient:
            MockClient.return_value.get_issue.return_value = sample_issue
            provider = YourProvider(valid_config)
            result = provider.get_ticket("TEST-123")
            assert result["id"] == "TEST-123"
            assert result["summary"] == "Sample"


class TestCreateTicket:
    def test_preview_does_not_execute(self, valid_config) -> None:
        with patch("qa_cortex.providers.your_provider.YourClient") as MockClient:
            provider = YourProvider(valid_config)

            result = provider.create_ticket(
                ticket_type="Bug",
                summary="Test",
                description="Test desc",
                approved=False,
            )

            assert result["preview"] is True
            # Critical: ensure the create method NOT called
            MockClient.return_value.create.assert_not_called()

    def test_approved_executes(self, valid_config, sample_issue) -> None:
        with patch("qa_cortex.providers.your_provider.YourClient") as MockClient:
            MockClient.return_value.create.return_value = sample_issue
            provider = YourProvider(valid_config)

            provider.create_ticket(
                ticket_type="Bug",
                summary="Test",
                description="Test desc",
                approved=True,
            )

            MockClient.return_value.create.assert_called_once()
```

Aim for:
- Config validation tests
- Read method tests (canonical shape)
- Write method tests (preview mode + approved mode)
- Error handling tests (404 → LookupError, network → ConnectionError)
- Edge cases (empty inputs, malformed IDs)

---

## Step 7 — Verify Protocol satisfaction

Run:

```bash
python3 -c "
from qa_cortex.providers.your_provider import YourProvider
from qa_cortex.providers import TicketingProvider

# Check all expected methods present
expected = {'get_ticket', 'search_tickets', 'get_linked_tickets', 'get_comments',
            'create_ticket', 'add_comment', 'transition_ticket', 'update_ticket'}
actual = {m for m in dir(YourProvider) if not m.startswith('_')}
missing = expected - actual
assert not missing, f'Missing methods: {missing}'
print('✓ All Protocol methods implemented')
"
```

And:

```bash
pytest tests/providers/test_<name>.py -v
```

All tests should pass.

---

## Step 8 — Add example config

`docs/examples/<name>-config.toml`:

```toml
[providers]
ticketing = "your_provider"

[ticketing.your_provider]
url = "https://your-instance.example.com"
api_token = "${YOUR_PROVIDER_TOKEN}"
# ... provider-specific fields
```

Plus add token entry to `docs/examples/.env.example`.

---

## Step 9 — Update docs

In `README.md`, add row to "Default backends" table or "Adding a new backend" section.

In `INSTALL.md`, add credential setup instructions (e.g. "where to get API token, what scopes needed").

---

## Step 10 — Test end-to-end

If you have a test instance:

1. Create config snippet
2. Run `python scripts/setup.py --check`
3. Optionally write integration test in `tests/integration/test_<name>_e2e.py`
4. Run brain in Claude Code, try `Тестируем <ticket-id>`

---

## Common gotchas

### Pagination
Provider APIs paginate. Implement transparently — caller passes `max_results`, you handle multi-page fetch.

### Rate limiting
Providers throttle. Use library's built-in retry-with-backoff if available, or wrap calls with simple retry loop.

### Custom fields
Different providers have different conventions:
- Jira: `customfield_NNNNN`
- Linear: structured field types
- GitHub: labels + milestones (no custom fields per se)

Pass-through to `custom_fields` dict in canonical shape; let user know in adapter docstring.

### Workflow transitions
Each provider has different state machine. Lookup transition by name, raise `ValueError` with available transitions list if invalid (Jira pattern).

### Markdown ↔ provider native
- Jira Cloud uses ADF
- Linear uses Markdown
- GitHub uses GFM
- Confluence uses storage format

For v1.0: pass plain text or basic Markdown, document limitations. Full conversion is later work.

### Authentication
Most providers: token-based (Bearer). Some (Slack): OAuth. Document required scopes in adapter docstring.

---

## Pull request checklist

When contributing back (once qa-cortex is public):

- [ ] All Protocol methods implemented
- [ ] All write methods have `approved: bool = False`
- [ ] Tests cover read + write + errors + edge cases
- [ ] `tests/providers/test_protocols.py::TestApprovalGatePattern` passes
- [ ] `docs/examples/<name>-config.toml` added
- [ ] README "Default backends" table updated
- [ ] INSTALL credential setup section added
- [ ] CHANGELOG entry added
- [ ] No new top-level dependencies (use optional extras in pyproject.toml)

---

## Examples in repo

Read existing adapters for reference:

- `qa_cortex/providers/jira.py` — full TicketingProvider with idempotency check
- `qa_cortex/providers/testrail.py` — TestManagementProvider with custom field discovery
- `qa_cortex/providers/confluence.py` — DocumentationProvider (read-only, simpler)
- `qa_cortex/providers/slack.py` — ChatProvider with email-based user lookup

---

## Questions

If stuck, open an issue (when public) or check:
- `qa_cortex/providers/base.py` — Protocol contracts with detailed docstrings
- `qa_cortex/providers/_normalizers.py` — shape conversion utilities
- `tests/providers/test_jira.py` — reference test pattern
