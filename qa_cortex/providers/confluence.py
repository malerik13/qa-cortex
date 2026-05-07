"""ConfluenceProvider — concrete DocumentationProvider for Atlassian Confluence.

Reuses the ``atlassian-python-api`` dep already installed for Jira.
Read-only — no create_page/update_page (out of scope for v1.0).

Status: Phase 2 Step 4.
"""

from __future__ import annotations

import re
from typing import Any

from atlassian import Confluence

from ._normalizers import normalize_iso8601, safe_get


class ConfluenceProvider:
    """DocumentationProvider for Confluence (Cloud or Server/DC).

    Config dict shape::

        {
            "url": "https://your-org.atlassian.net/wiki",
            "email": "you@example.com",
            "api_token": "ATATT3xFf...",
            "default_space_key": "PROJ",      # default space for searches
            "verify_ssl": True,               # default True
            "cloud": True,                    # default True
        }

    Required: url, email, api_token.
    """

    REQUIRED_CONFIG_KEYS = {"url", "email", "api_token"}

    def __init__(self, config: dict[str, Any]) -> None:
        missing = self.REQUIRED_CONFIG_KEYS - set(config.keys())
        if missing:
            raise ValueError(
                f"ConfluenceProvider config missing required keys: {sorted(missing)}"
            )

        self.config = config
        self.default_space = config.get("default_space_key")

        self._client = Confluence(
            url=config["url"],
            username=config["email"],
            password=config["api_token"],
            cloud=config.get("cloud", True),
            verify_ssl=config.get("verify_ssl", True),
        )

    def search(
        self,
        query: str,
        space: str | None = None,
        max_results: int = 20,
    ) -> list[dict[str, Any]]:
        """Search Confluence pages.

        Args:
            query: Free-text or CQL.
            space: Optional space key scope.
            max_results: Cap on results.
        """
        cql = self._build_cql(query, space)

        try:
            response = self._client.cql(cql, limit=max_results)
        except Exception as e:
            raise ConnectionError(f"Confluence search failed: {e}") from e

        results = response.get("results", []) if isinstance(response, dict) else []
        return [self._normalize_page(r, full=False) for r in results]

    def get_page(self, page_id: str) -> dict[str, Any]:
        """Fetch full page including body."""
        try:
            raw = self._client.get_page_by_id(page_id, expand="body.view,space,version")
        except Exception as e:
            if "404" in str(e) or "not found" in str(e).lower():
                raise LookupError(f"Page {page_id} not found") from e
            raise ConnectionError(f"Confluence fetch failed: {e}") from e

        return self._normalize_page(raw, full=True)

    def list_spaces(self) -> list[dict[str, str]]:
        """List user-accessible spaces."""
        try:
            response = self._client.get_all_spaces(start=0, limit=100, expand="description")
        except Exception as e:
            raise ConnectionError(f"Confluence list_spaces failed: {e}") from e

        spaces = response.get("results", []) if isinstance(response, dict) else []
        return [
            {
                "key": s.get("key", ""),
                "name": s.get("name", ""),
                "description": safe_get(s, "description.plain.value", default=None),
            }
            for s in spaces
        ]

    # ============================================================
    # Internal helpers
    # ============================================================

    def _build_cql(self, query: str, space: str | None) -> str:
        """Build CQL — pass through if looks like CQL, else free-text wrap."""
        cql_markers = (" AND ", " OR ", "type=", "space=", "label=")
        is_cql = any(marker in query.upper() for marker in cql_markers)

        if is_cql:
            return query

        # Free-text — escape quotes, wrap as text search
        escaped = query.replace('"', '\\"')
        cql = f'text ~ "{escaped}"'
        if space or self.default_space:
            cql = f'space = "{space or self.default_space}" AND ' + cql
        return cql

    def _normalize_page(self, raw: dict[str, Any], full: bool = True) -> dict[str, Any]:
        """Convert Confluence page → canonical DocumentationProvider shape."""
        if not isinstance(raw, dict):
            return {"_error": "non-dict raw response"}

        body_html = safe_get(raw, "body.view.value", default="")
        body_md = self._html_to_markdown(body_html) if (full and body_html) else ""

        # Page URL — Confluence Cloud: /wiki/spaces/<KEY>/pages/<ID>
        page_id = raw.get("id", "")
        space_key = safe_get(raw, "space.key", default="")
        url = f"{self.config['url']}/spaces/{space_key}/pages/{page_id}" if page_id else ""

        return {
            "id": str(page_id),
            "title": raw.get("title", ""),
            "space": space_key or None,
            "url": url,
            "body_markdown": body_md if full else "",
            "labels": [
                lbl.get("name", "")
                for lbl in safe_get(raw, "metadata.labels.results", default=[]) or []
            ],
            "updated_at": normalize_iso8601(safe_get(raw, "version.when", default="")),
            "author": safe_get(raw, "version.by.displayName", default=None),
        }

    def _html_to_markdown(self, html: str) -> str:
        """Convert Confluence storage HTML to plain Markdown.

        Lightweight conversion — handles common tags. For full fidelity,
        users can install ``markdownify`` and we'll auto-prefer it. v1.0
        scope: best-effort, document limitations.
        """
        try:
            from markdownify import markdownify as md_convert
            return md_convert(html, heading_style="ATX")
        except ImportError:
            # Fallback: strip HTML tags, preserve paragraphs
            text = re.sub(r"<br\s*/?>", "\n", html)
            text = re.sub(r"</p>\s*<p>", "\n\n", text)
            text = re.sub(r"<[^>]+>", "", text)
            text = re.sub(r"\n{3,}", "\n\n", text)
            return text.strip()
