"""TestRailProvider — concrete TestManagementProvider implementation for TestRail.

Wraps `testrail-api` library to satisfy the TestManagementProvider Protocol.

Design (per Phase 2 Step 3 — see phase_2_roadmap.md):
- Direct testrail-api lib (not bun913/mcp-testrail subprocess approach)
- Two-step approval gate enforced via ``approved`` parameter
- ``find_cases_by_linked_ticket`` uses configured custom field
  (TestRail doesn't have native ticket linking — relies on project conventions)

Status: Phase 2 Step 3.
"""

from __future__ import annotations

from typing import Any

from testrail_api import TestRailAPI

from ._normalizers import normalize_iso8601, safe_get, truncate


# Canonical status name → TestRail status_id mapping.
# Adapter ships defaults; user can override via config["status_map"].
_DEFAULT_STATUS_MAP = {
    "passed": 1,
    "blocked": 2,
    "untested": 3,
    "retest": 4,
    "failed": 5,
}


class TestRailProvider:
    """TestManagementProvider for TestRail.

    Config dict shape::

        {
            "url": "https://your-org.testrail.io",
            "username": "you@example.com",
            "api_key": "...",
            "project_id": 1,                  # default project for searches/creates
            "linked_ticket_field": "custom_jira_id",  # custom field holding linked ticket
            "status_map": {"passed": 1, ...}, # optional override of defaults
        }

    Required: url, username, api_key, project_id, linked_ticket_field.
    """

    REQUIRED_CONFIG_KEYS = {
        "url",
        "username",
        "api_key",
        "project_id",
        "linked_ticket_field",
    }

    def __init__(self, config: dict[str, Any]) -> None:
        missing = self.REQUIRED_CONFIG_KEYS - set(config.keys())
        if missing:
            raise ValueError(
                f"TestRailProvider config missing required keys: {sorted(missing)}"
            )

        self.config = config
        self.project_id = config["project_id"]
        self.linked_ticket_field = config["linked_ticket_field"]
        self.status_map = {**_DEFAULT_STATUS_MAP, **(config.get("status_map") or {})}

        self._client = TestRailAPI(
            url=config["url"],
            email=config["username"],
            password=config["api_key"],
        )

    # ============================================================
    # Read methods (Tier 1)
    # ============================================================

    def get_test_case(self, case_id: str, include_steps: bool = True) -> dict[str, Any]:
        """Fetch test case by ID. ``include_steps`` controls steps field population."""
        try:
            raw = self._client.cases.get_case(case_id=int(case_id))
        except ValueError:
            raise ValueError(f"Malformed case_id {case_id!r}: expected numeric")
        except Exception as e:
            if "404" in str(e) or "not found" in str(e).lower():
                raise LookupError(f"Test case {case_id} not found") from e
            raise ConnectionError(f"TestRail fetch failed for {case_id}: {e}") from e

        return self._normalize_case(raw, include_steps=include_steps)

    def search_test_cases(
        self,
        query: str,
        section: str | None = None,
        max_results: int = 50,
    ) -> list[dict[str, Any]]:
        """Search by query, optionally scoped to section.

        TestRail doesn't have free-text case search; we filter client-side
        by title+steps content. For more sophisticated search, use TestRail's
        own filter UI. This method does substring match on title.
        """
        try:
            cases = self._client.cases.get_cases(project_id=self.project_id)
        except Exception as e:
            raise ConnectionError(f"TestRail search failed: {e}") from e

        # Some TestRail versions return list, others return paginated dict
        case_list = cases.get("cases", cases) if isinstance(cases, dict) else cases

        query_lc = query.lower()
        matches = [
            c for c in case_list
            if query_lc in c.get("title", "").lower()
        ]

        if section:
            matches = [c for c in matches if str(c.get("section_id", "")) == str(section)]

        return [self._normalize_case(c, include_steps=False) for c in matches[:max_results]]

    def find_cases_by_linked_ticket(
        self,
        ticket_id: str,
        include_steps: bool = True,
    ) -> list[dict[str, Any]]:
        """Find cases linked to a ticket via configured custom field.

        Per Protocol: include_steps defaults True (CLAUDE.md MANDATORY rule).
        """
        try:
            cases = self._client.cases.get_cases(project_id=self.project_id)
        except Exception as e:
            raise ConnectionError(f"TestRail fetch failed: {e}") from e

        case_list = cases.get("cases", cases) if isinstance(cases, dict) else cases
        field = self.linked_ticket_field

        # Match cases where custom field contains the ticket_id
        matches = []
        for c in case_list:
            field_val = c.get(field, "") or ""
            if isinstance(field_val, str) and ticket_id in field_val:
                matches.append(c)
            elif isinstance(field_val, list) and ticket_id in field_val:
                matches.append(c)

        return [self._normalize_case(c, include_steps=include_steps) for c in matches]

    def get_run(self, run_id: str) -> dict[str, Any]:
        """Fetch test run with passed/failed/blocked counts."""
        try:
            raw = self._client.runs.get_run(run_id=int(run_id))
        except ValueError:
            raise ValueError(f"Malformed run_id {run_id!r}: expected numeric")
        except Exception as e:
            if "404" in str(e) or "not found" in str(e).lower():
                raise LookupError(f"Run {run_id} not found") from e
            raise ConnectionError(f"TestRail run fetch failed: {e}") from e

        return {
            "id": str(raw.get("id", "")),
            "name": raw.get("name", ""),
            "status": "active" if not raw.get("is_completed") else "completed",
            "passed": raw.get("passed_count", 0),
            "failed": raw.get("failed_count", 0),
            "blocked": raw.get("blocked_count", 0),
            "untested": raw.get("untested_count", 0),
            "started_at": normalize_iso8601(raw.get("created_on", "")),
            "url": raw.get("url", ""),
        }

    # ============================================================
    # Write methods (Tier 3)
    # ============================================================

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
        """Create a test case. Two-step gate."""
        if not title:
            raise ValueError("create_test_case requires non-empty title")
        if not section:
            raise ValueError("create_test_case requires section (TestRail section_id)")

        custom_fields = custom_fields or {}
        linked_tickets = linked_tickets or []

        # Build payload
        payload: dict[str, Any] = {"title": title}

        # Convert canonical steps to TestRail separated steps format
        if steps:
            payload["custom_steps_separated"] = [
                {
                    "content": s.get("step", ""),
                    "expected": s.get("expected", ""),
                }
                for s in steps
            ]

        if priority:
            payload["priority_id"] = self._priority_to_id(priority)

        # Linked tickets via configured field
        if linked_tickets:
            payload[self.linked_ticket_field] = ",".join(linked_tickets)

        # Pass through extra custom fields
        for k, v in custom_fields.items():
            payload[k] = v

        if not approved:
            return {
                "preview": True,
                "payload": {
                    "section_id": section,
                    "title": title,
                    "step_count": len(steps),
                    "priority": priority,
                    "linked_tickets": linked_tickets,
                    "custom_fields": dict(custom_fields),
                },
            }

        try:
            created = self._client.cases.add_case(section_id=int(section), **payload)
        except Exception as e:
            raise ConnectionError(f"TestRail add_case failed: {e}") from e

        return self._normalize_case(created, include_steps=True)

    def add_result(
        self,
        case_id: str,
        run_id: str,
        status: str,
        comment: str | None = None,
        evidence_urls: list[str] | None = None,
        approved: bool = False,
    ) -> dict[str, Any]:
        """Record test result. Two-step gate."""
        status_id = self.status_map.get(status.lower())
        if status_id is None:
            raise ValueError(
                f"Unknown status {status!r}. Valid: {sorted(self.status_map.keys())}"
            )

        # Compose comment with evidence URLs if provided
        full_comment = comment or ""
        if evidence_urls:
            evidence_lines = "\n".join(f"- {url}" for url in evidence_urls)
            full_comment = f"{full_comment}\n\n## Evidence\n{evidence_lines}".strip()

        if not approved:
            return {
                "preview": True,
                "payload": {
                    "case_id": case_id,
                    "run_id": run_id,
                    "status": status,
                    "status_id": status_id,
                    "comment": truncate(full_comment, 300),
                    "evidence_count": len(evidence_urls or []),
                },
            }

        try:
            result = self._client.results.add_result_for_case(
                run_id=int(run_id),
                case_id=int(case_id),
                status_id=status_id,
                comment=full_comment,
            )
        except Exception as e:
            raise ConnectionError(f"TestRail add_result failed: {e}") from e

        return {
            "case_id": case_id,
            "run_id": run_id,
            "status": status,
            "comment": full_comment,
            "tested_at": normalize_iso8601(safe_get(result, "created_on", default="")),
            "tester": safe_get(result, "created_by", default=None),
            "evidence": evidence_urls or [],
        }

    # ============================================================
    # Internal helpers
    # ============================================================

    def _normalize_case(
        self,
        raw: dict[str, Any],
        include_steps: bool = True,
    ) -> dict[str, Any]:
        """Convert TestRail case → canonical TestManagementProvider shape."""
        if not isinstance(raw, dict):
            return {"_error": "non-dict raw response"}

        # Steps: TestRail has custom_steps (text) OR custom_steps_separated (structured)
        steps: list[dict[str, str]] = []
        if include_steps:
            separated = raw.get("custom_steps_separated") or []
            if separated:
                steps = [
                    {"step": s.get("content", ""), "expected": s.get("expected", "")}
                    for s in separated
                ]
            else:
                # Fallback: parse custom_steps text
                text_steps = raw.get("custom_steps", "")
                if text_steps:
                    steps = [{"step": text_steps, "expected": raw.get("custom_expected", "")}]

        return {
            "id": str(raw.get("id", "")),
            "title": raw.get("title", ""),
            "section": str(raw.get("section_id", "")) if raw.get("section_id") else None,
            "preconditions": [raw.get("custom_preconds", "")] if raw.get("custom_preconds") else [],
            "steps": steps,
            "expected_result": raw.get("custom_expected", ""),
            "type": self._type_id_to_name(raw.get("type_id")),
            "priority": self._priority_id_to_name(raw.get("priority_id")),
            "linked_tickets": self._extract_linked_tickets(raw),
            "tags": [],  # TestRail doesn't have tags as first-class
            "url": f"{self.config['url']}/index.php?/cases/view/{raw.get('id', '')}",
            "custom_fields": {k: v for k, v in raw.items() if k.startswith("custom_")},
        }

    def _extract_linked_tickets(self, raw: dict[str, Any]) -> list[str]:
        """Extract linked ticket IDs from configured custom field."""
        val = raw.get(self.linked_ticket_field, "") or ""
        if isinstance(val, str):
            # Comma-separated or single
            return [t.strip() for t in val.split(",") if t.strip()]
        if isinstance(val, list):
            return [str(t) for t in val if t]
        return []

    def _priority_to_id(self, priority: str | None) -> int | None:
        """Map canonical priority to TestRail priority_id (1-5).

        TestRail priority IDs are project-specific; default mapping:
        Low=1, Medium=2, High=3, Critical=4.
        """
        if not priority:
            return None
        mapping = {"low": 1, "medium": 2, "high": 3, "critical": 4}
        return mapping.get(priority.lower())

    def _priority_id_to_name(self, priority_id: int | None) -> str | None:
        """Reverse of _priority_to_id."""
        if priority_id is None:
            return None
        reverse = {1: "Low", 2: "Medium", 3: "High", 4: "Critical"}
        return reverse.get(priority_id)

    def _type_id_to_name(self, type_id: int | None) -> str | None:
        """Common TestRail type_ids; project-specific mappings vary."""
        if type_id is None:
            return None
        common = {
            1: "Automated",
            2: "Functionality",
            3: "Performance",
            6: "Regression",
            7: "Smoke",
            9: "Compatibility",
        }
        return common.get(type_id, f"type_{type_id}")
