"""JiraProvider — concrete TicketingProvider implementation for Atlassian Jira.

Wraps `atlassian-python-api` library to satisfy the TicketingProvider Protocol.

Design decisions (per Phase 2 Step 2 — see knowledge_base/design_docs/phase_2_roadmap.md):

- D8: chose `atlassian-python-api` direct over wrapping `sooperset/mcp-atlassian`
  (latter is MCP-server-first, not designed as Python library)
- Same library covers Confluence (Step 4) — single dependency
- Two-step approval gate enforced via ``approved`` parameter pattern
- Idempotency check: ``create_ticket(approved=False)`` returns similar OPEN
  tickets via JQL search

Limitations / known issues:
- Markdown ↔ ADF: Jira Cloud uses ADF for description; this adapter sends
  plain text or wiki markup. Rich formatting may not render perfectly. For
  v1.0, document this as known limitation; ADF conversion can come later.
- Custom fields: pass-through. User must know field IDs (customfield_NNNNN)
  for project. Adapter doesn't auto-discover.
- Workflow transitions: looked up by name; if user's project has unusual
  workflow names, may need explicit transition ID config.

Status: Phase 2 Step 2 implementation. Tests in ``tests/providers/test_jira.py``.
"""

from __future__ import annotations

from typing import Any

import re

from atlassian import Jira

from ._normalizers import (
    normalize_iso8601,
    safe_get,
    parse_acceptance_criteria,
    truncate,
)


_JIRA_KEY_PATTERN = re.compile(r"^[A-Z][A-Z0-9_]*-\d+$")


def _is_valid_jira_key(ticket_id: str) -> bool:
    """Validate Jira issue key format: ``[A-Z][A-Z0-9_]*-\\d+``.

    Examples:
        Valid: ``PROJ-123``, ``ENG-1``, ``TEST_2-456``
        Invalid: ``proj-123`` (lowercase), ``not-a-valid-id``, ``""``
    """
    return bool(_JIRA_KEY_PATTERN.match(ticket_id))


# Map canonical status names to common Jira workflow names.
# Adapter falls back to passing user-provided name as-is if not in this map.
_CANONICAL_STATUS_MAP = {
    "open": ["Open", "To Do", "Backlog", "New"],
    "in_progress": ["In Progress", "Doing", "Active"],
    "in_review": ["In Review", "Code Review", "Review"],
    "done": ["Done", "Closed", "Resolved", "Complete"],
    "blocked": ["Blocked", "Impediment"],
    "wont_fix": ["Won't Fix", "Won't Do", "Cancelled"],
}


class JiraProvider:
    """TicketingProvider for Atlassian Jira (Cloud or Server/DC).

    Config dict shape::

        {
            "url": "https://your-org.atlassian.net",
            "email": "you@example.com",
            "api_token": "ATATT3xFf...",
            "ticket_prefix": "PROJ",          # used for default project filtering
            "default_project_key": "PROJ",    # for create_ticket
            "verify_ssl": True,               # default True
            "cloud": True,                    # default True (Jira Cloud); False for Server/DC
        }

    Required keys: ``url``, ``email``, ``api_token``, ``ticket_prefix``,
    ``default_project_key``.
    """

    REQUIRED_CONFIG_KEYS = {
        "url",
        "email",
        "api_token",
        "ticket_prefix",
        "default_project_key",
    }

    def __init__(self, config: dict[str, Any]) -> None:
        """Initialize Jira client and validate config.

        Raises:
            ValueError: if required config keys missing.
        """
        missing = self.REQUIRED_CONFIG_KEYS - set(config.keys())
        if missing:
            raise ValueError(
                f"JiraProvider config missing required keys: {sorted(missing)}. "
                f"Required: {sorted(self.REQUIRED_CONFIG_KEYS)}"
            )

        self.config = config
        self.ticket_prefix = config["ticket_prefix"]
        self.default_project_key = config["default_project_key"]

        self._client = Jira(
            url=config["url"],
            username=config["email"],
            password=config["api_token"],
            cloud=config.get("cloud", True),
            verify_ssl=config.get("verify_ssl", True),
        )

    # ============================================================
    # Read methods (Tier 1 — auto-approved per CLAUDE.md trust tiering)
    # ============================================================

    def get_ticket(self, ticket_id: str) -> dict[str, Any]:
        """Fetch ticket by ID, return canonical shape."""
        # Strict validation: must look like PROJ-123 (letters+digits, dash, digits)
        if not ticket_id or not _is_valid_jira_key(ticket_id):
            raise ValueError(
                f"Malformed ticket_id {ticket_id!r}: expected format like 'PROJ-123' "
                f"(uppercase project key, dash, numeric ID)"
            )

        try:
            raw = self._client.issue(ticket_id, expand="renderedFields,transitions")
        except Exception as e:
            # atlassian-python-api raises various exceptions; normalize
            if "404" in str(e) or "not found" in str(e).lower():
                raise LookupError(f"Ticket {ticket_id} not found") from e
            raise ConnectionError(f"Jira fetch failed for {ticket_id}: {e}") from e

        return self._normalize_ticket(raw)

    def search_tickets(
        self,
        query: str,
        max_results: int = 50,
    ) -> list[dict[str, Any]]:
        """Search tickets by JQL or free-text.

        If ``query`` looks like JQL (contains ``=``, ``~``, ``IN``, ``ORDER BY``),
        use as-is. Otherwise, treat as free-text and build JQL like
        ``text ~ "query" AND project = PROJ``.
        """
        jql = self._build_jql(query)

        try:
            response = self._client.jql(jql, limit=max_results)
        except Exception as e:
            raise ConnectionError(f"Jira search failed: {e}") from e

        issues = response.get("issues", []) if isinstance(response, dict) else []
        return [self._normalize_ticket(issue, full=False) for issue in issues]

    def get_linked_tickets(self, ticket_id: str) -> list[dict[str, Any]]:
        """Fetch tickets linked via Jira issue links.

        Returns canonical shape: ``[{id, link_type, summary, status}, ...]``.
        """
        try:
            raw = self._client.issue(ticket_id, fields="issuelinks")
        except Exception as e:
            raise ConnectionError(f"Jira fetch failed for {ticket_id}: {e}") from e

        links = safe_get(raw, "fields.issuelinks", default=[]) or []
        normalized = []

        for link in links:
            link_type_data = link.get("type", {})
            link_type = link_type_data.get("name", "relates_to")

            # Each link has either inwardIssue or outwardIssue
            for direction in ("outwardIssue", "inwardIssue"):
                if direction in link:
                    issue = link[direction]
                    normalized.append(
                        {
                            "id": issue.get("key", ""),
                            "link_type": link_type,
                            "direction": "outward" if direction == "outwardIssue" else "inward",
                            "summary": safe_get(issue, "fields.summary", default=""),
                            "status": safe_get(issue, "fields.status.name", default=""),
                        }
                    )

        return normalized

    def get_comments(
        self,
        ticket_id: str,
        max_results: int = 50,
    ) -> list[dict[str, Any]]:
        """Fetch comments on ticket, sorted oldest-first."""
        try:
            raw = self._client.issue_get_comments(ticket_id)
        except Exception as e:
            raise ConnectionError(f"Jira comments fetch failed for {ticket_id}: {e}") from e

        comments = raw.get("comments", []) if isinstance(raw, dict) else []
        normalized = []

        for c in comments[:max_results]:
            normalized.append(
                {
                    "id": c.get("id", ""),
                    "author": safe_get(c, "author.displayName", default=safe_get(c, "author.name", default="")),
                    "body": c.get("body", ""),
                    "created_at": normalize_iso8601(c.get("created", "")),
                    "updated_at": normalize_iso8601(c.get("updated", "")),
                }
            )

        return normalized

    # ============================================================
    # Write methods (Tier 3 — explicit approval gate)
    # ============================================================

    def create_ticket(
        self,
        ticket_type: str,
        summary: str,
        description: str,
        custom_fields: dict[str, Any] | None = None,
        approved: bool = False,
    ) -> dict[str, Any]:
        """Create a Jira issue.

        Two-step approval gate per TicketingProvider Protocol.
        """
        if not summary:
            raise ValueError("create_ticket requires non-empty summary")
        if not ticket_type:
            raise ValueError("create_ticket requires ticket_type (e.g. 'Bug', 'Story')")

        custom_fields = custom_fields or {}
        project_key = custom_fields.pop("project_key", self.default_project_key)

        # Build payload
        payload = {
            "project": {"key": project_key},
            "issuetype": {"name": ticket_type},
            "summary": summary,
            "description": description,
        }
        # Pass through any extra custom fields
        payload.update(custom_fields)

        if not approved:
            # Preview mode — also do idempotency check
            similar = self._find_similar_open_tickets(summary, project_key)
            return {
                "preview": True,
                "payload": {
                    "ticket_type": ticket_type,
                    "project": project_key,
                    "summary": summary,
                    "description": truncate(description, 500),
                    "custom_fields": dict(custom_fields),  # copy for safety
                    "would_create_at": f"{self.config['url']}/browse/{project_key}-NEW",
                },
                "idempotency_check": similar,
            }

        # Actual create
        try:
            created = self._client.create_issue(fields=payload)
        except Exception as e:
            raise ConnectionError(f"Jira create_issue failed: {e}") from e

        # Re-fetch to get canonical shape with all fields populated
        new_id = created.get("key", "")
        if new_id:
            return self.get_ticket(new_id)
        return {
            "id": "",
            "summary": summary,
            "_raw": created,
            "_warning": "Could not extract ticket key from create response",
        }

    def add_comment(
        self,
        ticket_id: str,
        body: str,
        approved: bool = False,
    ) -> dict[str, Any]:
        """Add a comment to a ticket."""
        if not body:
            raise ValueError("add_comment requires non-empty body")

        if not approved:
            # Fetch ticket summary for preview context
            try:
                ticket = self.get_ticket(ticket_id)
                ticket_summary = ticket.get("summary", "")
            except (LookupError, ConnectionError):
                ticket_summary = "(could not fetch — verify ticket exists)"

            return {
                "preview": True,
                "payload": {"ticket_id": ticket_id, "body": body},
                "ticket_summary": ticket_summary,
            }

        try:
            result = self._client.issue_add_comment(ticket_id, body)
        except Exception as e:
            raise ConnectionError(f"Jira add_comment failed for {ticket_id}: {e}") from e

        return {
            "id": result.get("id", "") if isinstance(result, dict) else "",
            "url": f"{self.config['url']}/browse/{ticket_id}",
            "created_at": normalize_iso8601(
                safe_get(result, "created", default="") if isinstance(result, dict) else ""
            ),
        }

    def transition_ticket(
        self,
        ticket_id: str,
        new_status: str,
        comment: str | None = None,
        approved: bool = False,
    ) -> dict[str, Any]:
        """Transition a ticket to a new status.

        Looks up transition ID by status name (Jira workflow-specific).
        """
        if not new_status:
            raise ValueError("transition_ticket requires new_status")

        # Get current status + available transitions
        try:
            ticket = self._client.issue(ticket_id, expand="transitions")
        except Exception as e:
            raise ConnectionError(f"Jira fetch failed for {ticket_id}: {e}") from e

        old_status = safe_get(ticket, "fields.status.name", default="")
        transitions = ticket.get("transitions", [])

        # Find transition matching new_status
        transition_id = None
        for t in transitions:
            if t.get("to", {}).get("name", "").lower() == new_status.lower():
                transition_id = t.get("id")
                break
            # Also match by transition name (some workflows differ)
            if t.get("name", "").lower() == new_status.lower():
                transition_id = t.get("id")
                break

        if not transition_id:
            available = [t.get("to", {}).get("name", "") for t in transitions]
            raise ValueError(
                f"Cannot transition {ticket_id} to {new_status!r}: "
                f"not in allowed transitions {available} (from status {old_status!r})"
            )

        if not approved:
            return {
                "preview": True,
                "payload": {
                    "ticket_id": ticket_id,
                    "old_status": old_status,
                    "new_status": new_status,
                    "transition_id": transition_id,
                    "comment": comment,
                },
            }

        try:
            self._client.set_issue_status(ticket_id, new_status, fields=None)
            if comment:
                self._client.issue_add_comment(ticket_id, comment)
        except Exception as e:
            raise ConnectionError(f"Jira transition failed for {ticket_id}: {e}") from e

        return {
            "ticket_id": ticket_id,
            "old_status": old_status,
            "new_status": new_status,
            "transitioned_at": normalize_iso8601(""),  # Jira doesn't return timestamp
        }

    def update_ticket(
        self,
        ticket_id: str,
        updates: dict[str, Any],
        approved: bool = False,
    ) -> dict[str, Any]:
        """Update ticket fields (non-transition).

        ``updates`` keys are Jira field names (e.g. "summary", "priority",
        "labels", "customfield_10000").
        """
        if not updates:
            raise ValueError("update_ticket requires non-empty updates dict")

        if not approved:
            return {
                "preview": True,
                "payload": {"ticket_id": ticket_id, "updates": dict(updates)},
            }

        try:
            self._client.update_issue_field(ticket_id, fields=updates)
        except Exception as e:
            raise ConnectionError(f"Jira update failed for {ticket_id}: {e}") from e

        return self.get_ticket(ticket_id)

    # ============================================================
    # Internal helpers
    # ============================================================

    def _build_jql(self, query: str) -> str:
        """Build JQL query — pass through if looks like JQL, else wrap as text search."""
        # Heuristic: if contains JQL operators, treat as JQL
        jql_markers = ("=", " IN ", " ~ ", " AND ", " OR ", "ORDER BY", "STATUS", "PROJECT")
        is_jql = any(marker in query.upper() for marker in jql_markers)

        if is_jql:
            return query

        # Free-text search scoped to default project
        escaped = query.replace('"', '\\"')
        return f'project = {self.default_project_key} AND text ~ "{escaped}"'

    def _find_similar_open_tickets(
        self,
        summary: str,
        project_key: str,
        limit: int = 5,
    ) -> list[dict[str, Any]]:
        """Find OPEN tickets with similar summary — for idempotency check.

        Returns list of ``{id, summary, status, similarity_score}``.
        """
        # Take first 5 significant words from summary for fuzzy match
        words = [w for w in summary.split() if len(w) > 3][:5]
        if not words:
            return []

        # Build JQL: match any of these words, in this project, status not Done
        text_terms = " OR ".join(f'text ~ "{w}"' for w in words)
        jql = (
            f"project = {project_key} "
            f"AND ({text_terms}) "
            f"AND statusCategory != Done "
            f"ORDER BY created DESC"
        )

        try:
            response = self._client.jql(jql, limit=limit)
        except Exception:
            # Don't fail create_ticket preview just because idempotency check failed
            return []

        issues = response.get("issues", []) if isinstance(response, dict) else []

        # Crude similarity: count matching words
        summary_words = set(summary.lower().split())
        results = []
        for issue in issues:
            issue_summary = safe_get(issue, "fields.summary", default="")
            issue_words = set(issue_summary.lower().split())
            score = len(summary_words & issue_words) / max(len(summary_words | issue_words), 1)
            results.append(
                {
                    "id": issue.get("key", ""),
                    "summary": truncate(issue_summary, 120),
                    "status": safe_get(issue, "fields.status.name", default=""),
                    "similarity_score": round(score, 2),
                }
            )

        return results

    def _normalize_ticket(
        self,
        raw: dict[str, Any],
        full: bool = True,
    ) -> dict[str, Any]:
        """Convert Jira issue to canonical TicketingProvider shape.

        Args:
            raw: Jira API response dict
            full: If True, populate all fields including linked_tickets, custom_fields.
                If False, return minimal shape for search results.
        """
        if not isinstance(raw, dict):
            return {"_error": "non-dict raw response", "_raw": raw}

        fields = raw.get("fields", {})
        description = fields.get("description", "") or ""

        canonical = {
            "id": raw.get("key", ""),
            "summary": fields.get("summary", ""),
            "description": description,
            "status": safe_get(fields, "status.name", default=""),
            "priority": safe_get(fields, "priority.name", default=None),
            "type": safe_get(fields, "issuetype.name", default=""),
            "acceptance_criteria": parse_acceptance_criteria(description),
            "labels": fields.get("labels", []) or [],
            "assignee": safe_get(fields, "assignee.displayName", default=None),
            "reporter": safe_get(fields, "reporter.displayName", default=None),
            "created_at": normalize_iso8601(fields.get("created", "")),
            "updated_at": normalize_iso8601(fields.get("updated", "")),
            "url": f"{self.config['url']}/browse/{raw.get('key', '')}",
        }

        if full:
            # Linked tickets summary (without separate API call)
            links = fields.get("issuelinks", []) or []
            linked = []
            for link in links:
                for direction in ("outwardIssue", "inwardIssue"):
                    if direction in link:
                        linked.append(
                            {
                                "id": link[direction].get("key", ""),
                                "link_type": safe_get(link, "type.name", default=""),
                                "summary": safe_get(link, f"{direction}.fields.summary", default=""),
                            }
                        )
            canonical["linked_tickets"] = linked

            # Pass through custom fields (filter to customfield_* keys)
            canonical["custom_fields"] = {
                k: v for k, v in fields.items() if k.startswith("customfield_")
            }

        return canonical
