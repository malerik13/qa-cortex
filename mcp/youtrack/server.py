#!/usr/bin/env python3
"""
ScaleFinal QA — YouTrack MCP Server
====================================
Single entry point for every YouTrack operation the plugin performs.

Rules:
  - Credentials come ONLY from .env (YOUTRACK_BASE_URL, YOUTRACK_TOKEN).
    NEVER hardcode tokens in source. Each team member has a personal token.
  - Read operations are unrestricted.
  - Write operations (create_ticket, link_tickets, add_comment) RETURN a payload
    preview; actual creation requires explicit human approval in Claude UI.

Tools:
  get_ticket(ticket_id)                       — full issue/article with description, fields
  search_tickets(query, max_results)          — YouTrack query language
  search_knowledge_base(query, version?)      — local version snapshots (v1.4..v2.9)
  get_version_features(version)               — full feature list of a release
  get_linked_tickets(ticket_id)               — parent/child/related graph for ticket
  get_comments(ticket_id, max_results)        — discussion trail on a ticket
  preview_ticket_payload(summary, desc, ...)  — builds a payload, DOES NOT SUBMIT
"""

import glob
import json
import os
import re
import sys
from pathlib import Path
from urllib.parse import quote

try:
    from dotenv import load_dotenv
except ImportError:
    print("ERROR: python-dotenv not installed. Run: pip install -r requirements.txt", file=sys.stderr)
    sys.exit(1)

# Plugin root = two levels up from this file (mcp/youtrack/server.py -> plugin root)
PLUGIN_ROOT = Path(__file__).resolve().parent.parent.parent
load_dotenv(PLUGIN_ROOT / ".env")

import requests
import mcp.server.stdio
import mcp.types as types
from mcp.server import Server
from mcp.server.models import InitializationOptions


# ─── YouTrack Client ──────────────────────────────────────────────────────────

class YouTrackClient:
    def __init__(self):
        self.base_url = (os.getenv("YOUTRACK_BASE_URL") or "").rstrip("/")
        self.token = os.getenv("YOUTRACK_TOKEN") or ""
        if not self.base_url or not self.token:
            raise ValueError(
                "Missing YOUTRACK_BASE_URL or YOUTRACK_TOKEN. "
                "Copy templates/env.template to .env and fill in your personal token."
            )
        self.project = os.getenv("YOUTRACK_PROJECT", "TRD")
        self.headers = {
            "Authorization": f"Bearer {self.token}",
            "Accept": "application/json",
            "Content-Type": "application/json",
        }

    def _get(self, path: str, timeout: int = 15):
        r = requests.get(f"{self.base_url}{path}", headers=self.headers, timeout=timeout)
        return r.json() if r.status_code == 200 else None

    def get_issue(self, issue_id: str):
        fields = (
            "id,idReadable,summary,description,"
            "customFields(name,value(name,text)),"
            "links(direction,linkType(name,sourceToTarget,targetToSource),"
            "issues(idReadable,summary,customFields(name,value(name,text))))"
        )
        return self._get(f"/api/issues/{issue_id}?fields={fields}")

    def get_article(self, article_id: str):
        fields = "id,idReadable,summary,content,childArticles(id,idReadable,summary)"
        return self._get(f"/api/articles/{article_id}?fields={fields}")

    def get_comments(self, issue_id: str, limit: int = 20):
        fields = "id,text,author(name),created"
        data = self._get(f"/api/issues/{issue_id}/comments?fields={fields}&$top={limit}")
        return data or []

    def search_issues(self, query: str, max_results: int = 20):
        fields = "id,idReadable,summary,description,customFields(name,value(name,text))"
        url = f"/api/issues?query={quote(query)}&fields={fields}&$top={max_results}"
        return self._get(url) or []

    # ─── Write API (gated by approved=True at tool layer) ─────────────────
    def _post(self, path: str, body: dict, timeout: int = 20):
        r = requests.post(
            f"{self.base_url}{path}",
            headers=self.headers,
            json=body,
            timeout=timeout,
        )
        if r.status_code in (200, 201):
            try:
                return {"ok": True, "data": r.json()}
            except Exception:
                return {"ok": True, "data": {}}
        return {
            "ok": False,
            "status": r.status_code,
            "error": (r.text or "")[:500],
        }

    def create_issue_basic(self, summary: str, description: str):
        """Create a bare issue in the project. Custom fields applied separately
        via apply_commands (more forgiving than direct customFields POST)."""
        body = {
            "project": {"shortName": self.project},
            "summary": summary,
            "description": description,
        }
        return self._post("/api/issues?fields=id,idReadable,summary", body)

    def apply_commands(self, query: str, issue_id: str):
        """Apply a YouTrack command-language string to an issue.
        Examples: 'Type Task Stack Testing subtask of TRD-11639'
        """
        body = {
            "query": query,
            "issues": [{"idReadable": issue_id}],
        }
        return self._post("/api/commands", body)

    def get_subtasks(self, parent_id: str) -> list[dict]:
        """Return outward Subtask children of the given parent."""
        issue = self.get_issue(parent_id)
        if not issue:
            return []
        children = []
        for link in issue.get("links", []):
            ltype = (link.get("linkType") or {}).get("name", "").lower()
            direction = link.get("direction", "")
            if ltype == "subtask" and direction in ("OUTWARD", "BOTH"):
                for sub in link.get("issues", []):
                    children.append({
                        "id": sub.get("idReadable", ""),
                        "summary": sub.get("summary", ""),
                        "custom_fields": sub.get("customFields") or [],
                    })
        return children

    def analyze_links(self, parent_id: str) -> dict:
        """Full link-graph analysis. Returns structured view: all subtasks
        categorized by function ([QA] / [BE] / [FE] / [CR #N] / [BA] / other),
        plus inward subtasks (this ticket's parents) and relates.

        Used by create_qa_subtask to present complete picture before any write.
        Brain must surface this to Yaroslav so the decision 'use existing vs
        create new' is informed by full graph, not just first [QA] match.
        """
        issue = self.get_issue(parent_id)
        if not issue:
            return {"error": f"Ticket {parent_id} not found"}

        # Categorize all linked issues
        graph = {
            "parent_id": parent_id,
            "parent_summary": issue.get("summary", ""),
            "subtasks_outward": [],   # this ticket's children
            "subtasks_inward":  [],   # this ticket's parents
            "relates":          [],
            "duplicates":       [],
            "other_links":      [],
            "by_function": {
                "QA":    [],
                "BE":    [],
                "FE":    [],
                "CR":    [],
                "BA":    [],
                "other": [],
            },
        }

        for link in issue.get("links", []):
            ltype = (link.get("linkType") or {}).get("name", "").lower()
            direction = link.get("direction", "")
            for sub in link.get("issues", []):
                entry = {
                    "id": sub.get("idReadable", ""),
                    "summary": sub.get("summary", ""),
                    "link_type": ltype,
                    "direction": direction,
                    "custom_fields": sub.get("customFields") or [],
                }

                # Direction-based bucketing
                if ltype == "subtask":
                    if direction == "OUTWARD":
                        graph["subtasks_outward"].append(entry)
                    elif direction == "INWARD":
                        graph["subtasks_inward"].append(entry)
                    else:
                        graph["other_links"].append(entry)
                elif ltype == "relates":
                    graph["relates"].append(entry)
                elif "duplicate" in ltype:
                    graph["duplicates"].append(entry)
                else:
                    graph["other_links"].append(entry)

                # Function tag bucketing — only outward subtasks
                if ltype == "subtask" and direction == "OUTWARD":
                    summary = entry["summary"]
                    if summary.startswith("[QA]"):
                        graph["by_function"]["QA"].append(entry)
                    elif summary.startswith("[BE]"):
                        graph["by_function"]["BE"].append(entry)
                    elif summary.startswith("[FE]"):
                        graph["by_function"]["FE"].append(entry)
                    elif summary.startswith("[CR"):  # [CR #1], [CR #2], ...
                        graph["by_function"]["CR"].append(entry)
                    elif summary.startswith("[BA]"):
                        graph["by_function"]["BA"].append(entry)
                    else:
                        graph["by_function"]["other"].append(entry)

        return graph

    def find_qa_subtasks(self, parent_id: str) -> list[dict]:
        """Return ALL [QA]-prefixed outward subtasks (could be multiple).
        Use analyze_links for richer view including state/version/sprint."""
        return self.analyze_links(parent_id).get("by_function", {}).get("QA", [])

    def add_comment(self, issue_id: str, text: str) -> dict:
        """Post a comment to an issue. Returns {ok, data} or {ok=False, error}."""
        return self._post(f"/api/issues/{issue_id}/comments", {"text": text})

    def get_state(self, issue_id: str) -> str:
        """Return current State of an issue (best-effort)."""
        issue = self.get_issue(issue_id)
        if not issue:
            return ""
        for f in issue.get("customFields") or []:
            if f.get("name") == "State":
                val = f.get("value")
                if isinstance(val, dict):
                    return val.get("name", "") or ""
        return ""

    def find_similar_open_bugs(self, parent_trd: str, summary_keywords: list[str]) -> list[dict]:
        """Idempotency check for bug creation — search bugs.json for open bugs
        that mention same parent_trd in summary and share keywords. Used to
        warn before filing potential duplicates.

        Pure local lookup — does not hit YouTrack API.
        """
        bugs_path = PLUGIN_ROOT / "knowledge_base" / "bugs.json"
        if not bugs_path.exists():
            return []
        try:
            data = json.loads(bugs_path.read_text())
        except Exception:
            return []
        OPEN_STATES = {"Submitted", "To Do", "In Progress", "Pull-Request", "Reopen",
                       "Ready for QA", "QA in progress", "QA gate", "BA To Do", "BA in progress",
                       "Tech Research", "To Estimate", "For Planning", "To Groom"}
        matches = []
        for b in data.get("bugs", []):
            if b.get("status") not in OPEN_STATES:
                continue
            summary_lower = (b.get("summary") or "").lower()
            preview_lower = (b.get("preview") or "").lower()
            # Must reference the same parent
            if parent_trd.upper() not in summary_lower and parent_trd.upper() not in preview_lower:
                continue
            # Must share at least one keyword (substring match)
            if not summary_keywords:
                matches.append(b)
                continue
            if any(kw.lower() in summary_lower or kw.lower() in preview_lower for kw in summary_keywords):
                matches.append(b)
        return matches


# ─── Knowledge Base (local) ───────────────────────────────────────────────────

def search_local_kb(query: str, version: str = None) -> list[dict]:
    """Search knowledge_base/v*.json snapshots."""
    kb_dir = PLUGIN_ROOT / "knowledge_base"
    if not kb_dir.exists():
        return []

    pattern = f"v{version}.json" if version else "v*.json"
    files = sorted(glob.glob(str(kb_dir / pattern)))

    query_lower = query.lower()
    results = []
    for filepath in files:
        try:
            with open(filepath, encoding="utf-8") as f:
                data = json.load(f)
        except (json.JSONDecodeError, OSError):
            continue

        ver = data.get("version", "?")
        for feature in data.get("features", []):
            haystack = " ".join([
                feature.get("title", ""),
                feature.get("module", ""),
                feature.get("description", ""),
                feature.get("historicalContext", ""),
            ]).lower()
            if query_lower in haystack:
                results.append({
                    "version": ver,
                    "title": feature.get("title", ""),
                    "module": feature.get("module", ""),
                    "description": feature.get("description", ""),
                    "historicalContext": feature.get("historicalContext", ""),
                    "businessLogicChanges": feature.get("businessLogicChanges", []),
                    "testingChecklist": feature.get("testingChecklist", []),
                })
    return results


def extract_field(custom_fields: list, name: str) -> str:
    for f in custom_fields or []:
        if f.get("name") != name:
            continue
        val = f.get("value")
        if not val:
            return ""
        if isinstance(val, dict):
            return val.get("name") or val.get("text") or ""
        if isinstance(val, list):
            return ", ".join(v.get("name", "") for v in val if v)
        return str(val)
    return ""


# ─── MCP Server ───────────────────────────────────────────────────────────────

server = Server("youtrack-scalefinal")
_client: YouTrackClient | None = None


def client() -> YouTrackClient:
    global _client
    if _client is None:
        _client = YouTrackClient()
    return _client


@server.list_tools()
async def list_tools() -> list[types.Tool]:
    return [
        types.Tool(
            name="get_ticket",
            description=(
                "Fetch a YouTrack issue or article by ID (e.g. TRD-12076). "
                "Returns summary, description, custom fields, and links."
            ),
            inputSchema={
                "type": "object",
                "properties": {
                    "ticket_id": {"type": "string", "description": "Ticket ID (e.g. TRD-12076)"}
                },
                "required": ["ticket_id"],
            },
        ),
        types.Tool(
            name="search_tickets",
            description=(
                "Search YouTrack using YouTrack Query Language. "
                "Examples: 'Release Version: 2.9 To Release Notes: Yes', "
                "'#{User Story} Swap Profile', '#{Bug} 2FA updated: -7d .. Today'."
            ),
            inputSchema={
                "type": "object",
                "properties": {
                    "query": {"type": "string"},
                    "max_results": {"type": "integer", "default": 20},
                },
                "required": ["query"],
            },
        ),
        types.Tool(
            name="search_knowledge_base",
            description=(
                "Search local version snapshots (v1.4..v2.9). Returns features "
                "with business logic, UI changes, and testing checklists."
            ),
            inputSchema={
                "type": "object",
                "properties": {
                    "query": {"type": "string"},
                    "version": {"type": "string", "default": None},
                },
                "required": ["query"],
            },
        ),
        types.Tool(
            name="get_version_features",
            description="List all features of a specific CRM version (e.g. '2.9').",
            inputSchema={
                "type": "object",
                "properties": {"version": {"type": "string"}},
                "required": ["version"],
            },
        ),
        types.Tool(
            name="get_linked_tickets",
            description=(
                "Get parent/child/related links for a ticket. Used for regression "
                "scouting — 'what might break around this change'."
            ),
            inputSchema={
                "type": "object",
                "properties": {"ticket_id": {"type": "string"}},
                "required": ["ticket_id"],
            },
        ),
        types.Tool(
            name="get_comments",
            description="Fetch discussion comments on a ticket (chronological).",
            inputSchema={
                "type": "object",
                "properties": {
                    "ticket_id": {"type": "string"},
                    "max_results": {"type": "integer", "default": 20},
                },
                "required": ["ticket_id"],
            },
        ),
        types.Tool(
            name="preview_ticket_payload",
            description=(
                "Build a bug/task payload for human review. "
                "THIS TOOL NEVER SUBMITS TO YOUTRACK. It returns the JSON that would "
                "be posted, so the QA can review and approve before any write."
            ),
            inputSchema={
                "type": "object",
                "properties": {
                    "summary":     {"type": "string"},
                    "description": {"type": "string"},
                    "type":        {"type": "string", "description": "Bug | Task | User Story"},
                    "priority":    {"type": "string", "description": "Critical | Major | Normal | Minor"},
                    "related_to":  {"type": "array",  "items": {"type": "string"}, "description": "TRD-XXXXX ids"},
                },
                "required": ["summary", "description", "type"],
            },
        ),
        types.Tool(
            name="create_qa_subtask",
            description=(
                "Create a [QA] subtask in YouTrack linked to the given parent ticket. "
                "Used in Phase 1.5 of qa_workflow. WRITE OPERATION — requires approved=true. "
                "Without approved=true returns a preview INCLUDING the full link graph "
                "(BE/FE/CR/QA/relates) and a recommendation: USE_EXISTING / CREATE_NEW / ASK_QA. "
                "Idempotent — refuses to create if a [QA] subtask exists, unless force=true."
            ),
            inputSchema={
                "type": "object",
                "properties": {
                    "parent_ticket":   {"type": "string", "description": "Parent TRD-XXXXX (the User Story / feature being tested)"},
                    "module":          {"type": "string", "description": "Module name in [brackets], e.g. 'Email builder', 'KYC', '2FA'. Extracted from parent summary."},
                    "parent_summary":  {"type": "string", "description": "The parent's summary AFTER the module prefix. Becomes the QA subtask title's tail."},
                    "body":            {"type": "string", "description": "Test plan body — dry, engineering English. 5 sections: Scope / Approach / Risks / AC coverage / Env+roles. 15-30 lines."},
                    "priority":        {"type": "string", "description": "Critical | Major | Normal | Minor (mirrors parent or QA judgement)"},
                    "release_version": {"type": "string", "description": "e.g. '3.0' (mirrors parent)"},
                    "sprint":          {"type": "string", "description": "Sprint name, e.g. 'TRP Sprint 56'. Optional."},
                    "story_points":    {"type": "integer", "description": "SP QA estimate. Optional."},
                    "approved":        {"type": "boolean", "description": "MUST BE true for actual creation. Default false = preview only with full link-graph analysis + recommendation."},
                    "force":           {"type": "boolean", "description": "Bypass idempotency check (allow creating another [QA] subtask even if one already exists). Default false. Use ONLY after Yaroslav reviewed full graph and explicitly wants a new one."},
                },
                "required": ["parent_ticket", "module", "parent_summary", "body"],
            },
        ),
        types.Tool(
            name="create_bug",
            description=(
                "Create a Bug ticket in YouTrack. WRITE OPERATION — requires approved=true. "
                "Without approved=true returns a preview with: idempotency check (similar open bugs in bugs.json for same parent), "
                "proposed payload, and `apply_commands` string. "
                "Title format: '[TRD-PARENT] <one-line summary>' per ScaleFinal convention "
                "(parent reference in title, NOT as Subtask link). "
                "Two-step approval: preview → Yaroslav says 'да create' → re-call with approved=true."
            ),
            inputSchema={
                "type": "object",
                "properties": {
                    "parent_trd":         {"type": "string", "description": "Parent User Story TRD-XXXXX (added as [TRD-XXXXX] prefix in title)"},
                    "summary":            {"type": "string", "description": "Bug summary AFTER the parent prefix. E.g. 'Bulk Send Emails — no client_emails records created'"},
                    "description":        {"type": "string", "description": "Full bug description in EN, per CLAUDE.md template (Prerequisites, Steps, Expected, Actual, Environment, etc.)"},
                    "severity":           {"type": "string", "description": "Severity: Critical | Major | Normal | Minor | Trivial. Apply qa_persona §11 algorithm."},
                    "priority":           {"type": "string", "description": "Priority: Critical | High | Normal | Low. Default Normal."},
                    "subsystem":          {"type": "string", "description": "Subsystem: CRM | TPM | CA | etc. Default CRM."},
                    "stack":              {"type": "string", "description": "Backend | Frontend | Backend+Frontend | etc."},
                    "affected_version":   {"type": "string", "description": "Version where bug observed, e.g. '3.0'"},
                    "release_version":    {"type": "string", "description": "Target fix version, e.g. '3.0' or '3.1'. Often same as affected_version."},
                    "tags":               {"type": "array",  "items": {"type": "string"}, "description": "Tags array. Include '1st cohort' if criteria met (qa_persona §5 + Insight 13). Other common: 'regression', 'blocker', 'security'."},
                    "bsource":            {"type": "string", "description": "Bug source: 'feature-test' | 'production' | 'regression' | etc. Per ScaleFinal convention."},
                    "additional_commands":{"type": "string", "description": "Extra YouTrack command-language fragment to apply. E.g. 'Sprint \"TRP Sprint 56\"'. Optional."},
                    "approved":           {"type": "boolean", "description": "MUST BE true for actual creation. Default false = preview + idempotency check only."},
                    "force":              {"type": "boolean", "description": "Bypass duplicate-warning if similar open bug exists. Default false."},
                },
                "required": ["parent_trd", "summary", "description", "severity", "affected_version"],
            },
        ),
        types.Tool(
            name="add_comment",
            description=(
                "Post a comment to a YouTrack issue. WRITE OPERATION — requires approved=true. "
                "Language: EN by default per qa_persona §7 language matrix (comments to dev/PO are EN). "
                "Without approved=true returns the comment text preview for Yaroslav review."
            ),
            inputSchema={
                "type": "object",
                "properties": {
                    "ticket_id": {"type": "string", "description": "TRD-XXXXX"},
                    "text":      {"type": "string", "description": "Comment text (EN per language matrix unless RU is justified)"},
                    "approved":  {"type": "boolean", "description": "MUST BE true for actual posting. Default false = preview."},
                },
                "required": ["ticket_id", "text"],
            },
        ),
        types.Tool(
            name="update_ticket_status",
            description=(
                "Transition a YouTrack ticket to a new state (Reopen, Verified, Won't Fix, Done, In Progress, etc.). "
                "WRITE OPERATION — requires approved=true. Optional accompanying comment "
                "(strongly recommended — best practice when transitioning state). "
                "Without approved=true shows current state, intended new state, and optional comment preview."
            ),
            inputSchema={
                "type": "object",
                "properties": {
                    "ticket_id": {"type": "string", "description": "TRD-XXXXX"},
                    "new_state": {"type": "string", "description": "Target state: Verified | Reopen | Won't Fix | Done | In Progress | Submitted | etc."},
                    "comment":   {"type": "string", "description": "Justification comment (EN, posted with the transition). Strongly recommended."},
                    "approved":  {"type": "boolean", "description": "MUST BE true for actual transition. Default false = preview."},
                },
                "required": ["ticket_id", "new_state"],
            },
        ),
    ]


@server.call_tool()
async def call_tool(name: str, arguments: dict) -> list[types.TextContent]:
    try:
        if name == "get_ticket":
            tid = arguments["ticket_id"].strip()
            c = client()
            result = c.get_issue(tid)
            if not result or "summary" not in result:
                result = c.get_article(tid)
            if not result:
                return [types.TextContent(type="text", text=f"Ticket {tid} not found.")]

            out = [f"# {result.get('idReadable', tid)}: {result.get('summary', '')}\n"]
            body = result.get("description") or result.get("content") or ""
            if body:
                out.append(body[:6000])

            cf = result.get("customFields", [])
            if cf:
                out.append("\n\n## Custom Fields")
                for f in cf:
                    val = f.get("value")
                    if val is not None and val != [] and val != "":
                        if isinstance(val, dict):
                            vs = val.get("name") or val.get("text") or str(val)
                        elif isinstance(val, list):
                            vs = ", ".join(
                                (v.get("name") or v.get("text") or str(v)) if isinstance(v, dict) else str(v)
                                for v in val if v
                            )
                        else:
                            vs = str(val)
                        if vs:
                            out.append(f"- **{f['name']}**: {vs}")

            links = result.get("links", [])
            if links:
                out.append("\n\n## Links")
                for link in links:
                    ltype = (link.get("linkType") or {}).get("name", "?")
                    direction = link.get("direction", "")
                    for issue in link.get("issues", []):
                        out.append(f"- [{ltype} / {direction}] {issue.get('idReadable')}: {issue.get('summary', '')}")

            return [types.TextContent(type="text", text="\n".join(out))]

        elif name == "search_tickets":
            query = arguments["query"]
            limit = arguments.get("max_results", 20)
            issues = client().search_issues(query, limit)
            if not issues:
                return [types.TextContent(type="text", text=f"No results for: {query}")]

            lines = [f"## Results for '{query}' ({len(issues)})\n"]
            for i in issues:
                lines.append(f"**{i.get('idReadable', '?')}** — {i.get('summary', '')}")
                desc = (i.get("description") or "").strip()
                if desc:
                    preview = re.sub(r"[#*`\[\]|!\n]", " ", desc[:200]).strip()
                    lines.append(f"  _{preview}..._")
                lines.append("")
            return [types.TextContent(type="text", text="\n".join(lines))]

        elif name == "search_knowledge_base":
            results = search_local_kb(arguments["query"], arguments.get("version"))
            if not results:
                v = arguments.get("version")
                return [types.TextContent(type="text", text=f"No local KB results for '{arguments['query']}'" + (f" in v{v}" if v else ""))]
            lines = [f"## Local KB: '{arguments['query']}' — {len(results)} results\n"]
            for r in results[:10]:
                lines.append(f"### [{r['version']}] {r['title']}")
                lines.append(f"**Module:** {r['module']}")
                if r['historicalContext']:
                    lines.append(f"**Historical context:** {r['historicalContext']}")
                for bl in r.get("businessLogicChanges", [])[:3]:
                    lines.append(f"- BL: {bl}")
                for ch in r.get("testingChecklist", [])[:3]:
                    lines.append(f"- Test: {ch}")
                lines.append("")
            return [types.TextContent(type="text", text="\n".join(lines))]

        elif name == "get_version_features":
            v = arguments["version"]
            path = PLUGIN_ROOT / "knowledge_base" / f"v{v}.json"
            if not path.exists():
                available = [p.stem for p in sorted((PLUGIN_ROOT / "knowledge_base").glob("v*.json"))]
                return [types.TextContent(type="text", text=f"v{v} not found. Available: {', '.join(available)}")]
            with open(path, encoding="utf-8") as f:
                data = json.load(f)
            feats = data.get("features", [])
            lines = [f"# v{v} — {len(feats)} features\n"]
            for ft in feats:
                lines.append(f"## {ft['title']}")
                lines.append(f"**Module:** {ft.get('module', '?')}")
                if ft.get("historicalContext"):
                    lines.append(f"**History:** {ft['historicalContext']}")
                for item in ft.get("testingChecklist", [])[:4]:
                    lines.append(f"- {item}")
                lines.append("")
            return [types.TextContent(type="text", text="\n".join(lines))]

        elif name == "get_linked_tickets":
            tid = arguments["ticket_id"].strip()
            data = client().get_issue(tid)
            if not data:
                return [types.TextContent(type="text", text=f"Ticket {tid} not found.")]
            links = data.get("links", [])
            if not links:
                return [types.TextContent(type="text", text=f"{tid}: no links.")]
            out = [f"# Links for {tid}\n"]
            grouped: dict[str, list] = {}
            for link in links:
                ltype = (link.get("linkType") or {}).get("name", "?")
                dir_ = link.get("direction", "")
                key = f"{ltype} ({dir_})"
                for issue in link.get("issues", []):
                    grouped.setdefault(key, []).append(
                        f"- {issue.get('idReadable')}: {issue.get('summary', '')}"
                    )
            for key, items in grouped.items():
                out.append(f"## {key}")
                out.extend(items)
                out.append("")
            return [types.TextContent(type="text", text="\n".join(out))]

        elif name == "get_comments":
            tid = arguments["ticket_id"].strip()
            limit = arguments.get("max_results", 20)
            comments = client().get_comments(tid, limit)
            if not comments:
                return [types.TextContent(type="text", text=f"{tid}: no comments.")]
            out = [f"# Comments on {tid} ({len(comments)})\n"]
            for c in comments:
                author = (c.get("author") or {}).get("name", "?")
                text = (c.get("text") or "").strip()
                out.append(f"**{author}:** {text[:500]}")
                out.append("")
            return [types.TextContent(type="text", text="\n".join(out))]

        elif name == "preview_ticket_payload":
            payload = {
                "summary":     arguments["summary"],
                "description": arguments["description"],
                "type":        arguments["type"],
                "priority":    arguments.get("priority", "Normal"),
                "related_to":  arguments.get("related_to", []),
            }
            out = [
                "## 📋 Ticket Payload Preview (NOT SUBMITTED)",
                "",
                "This is a preview only. Review the fields below.",
                "To create the ticket in YouTrack, open it manually or ask Claude to",
                "create it — Claude will ask for explicit approval before posting.",
                "",
                "```json",
                json.dumps(payload, indent=2, ensure_ascii=False),
                "```",
            ]
            return [types.TextContent(type="text", text="\n".join(out))]

        elif name == "create_qa_subtask":
            parent_ticket   = arguments["parent_ticket"].strip()
            module          = arguments["module"].strip()
            parent_summary  = arguments["parent_summary"].strip()
            body_text       = arguments["body"]
            priority        = arguments.get("priority", "Normal")
            release_version = arguments.get("release_version", "")
            sprint          = arguments.get("sprint", "")
            story_points    = arguments.get("story_points")
            approved        = bool(arguments.get("approved", False))
            force           = bool(arguments.get("force", False))  # bypass duplicate-suspicion

            qa_summary = f"[QA] [{module}] {parent_summary}"

            c = client()

            # Full link graph analysis — surface complete picture to brain/QA.
            graph = c.analyze_links(parent_ticket)
            if "error" in graph:
                return [types.TextContent(type="text", text=f"❌ {graph['error']}")]

            existing_qa = graph.get("by_function", {}).get("QA", [])

            def _render_graph_section() -> list[str]:
                """Pretty-print the full link graph for preview."""
                lines = [f"### 🔗 Full link graph for {parent_ticket}"]
                lines.append(f"**Parent:** {parent_ticket} — {graph.get('parent_summary', '')[:120]}")
                lines.append("")

                fn = graph.get("by_function", {})
                for fn_name, fn_label in [("CR", "Change Requests"), ("BE", "Backend"), ("FE", "Frontend"),
                                           ("QA", "QA testing"), ("BA", "Business Analysis"), ("other", "Other tagged")]:
                    items = fn.get(fn_name, [])
                    if not items:
                        continue
                    lines.append(f"**{fn_label}** ({len(items)}):")
                    for item in items:
                        # Pull state/version/sprint from custom_fields if present
                        cf = {f.get("name", ""): f.get("value") for f in item.get("custom_fields", [])}
                        state = ""
                        version = ""
                        if isinstance(cf.get("State"), dict):
                            state = cf["State"].get("name") or ""
                        if isinstance(cf.get("Release Version"), dict):
                            version = cf["Release Version"].get("name") or ""
                        meta = []
                        if state:   meta.append(f"state={state}")
                        if version: meta.append(f"v={version}")
                        meta_str = f" _({', '.join(meta)})_" if meta else ""
                        lines.append(f"  • {item['id']} — {item['summary'][:90]}{meta_str}")
                    lines.append("")

                inward = graph.get("subtasks_inward", [])
                if inward:
                    lines.append(f"**Parent of {parent_ticket}** (inward Subtask):")
                    for item in inward:
                        lines.append(f"  • {item['id']} — {item['summary'][:90]}")
                    lines.append("")

                relates = graph.get("relates", [])
                if relates:
                    lines.append(f"**Related** ({len(relates)}):")
                    for item in relates:
                        lines.append(f"  • {item['id']} — {item['summary'][:90]}")
                    lines.append("")
                return lines

            def _recommendation() -> tuple[str, str]:
                """Return (verdict, reasoning) — verdict in: USE_EXISTING / CREATE_NEW / ASK_QA."""
                if not existing_qa:
                    return "CREATE_NEW", "no existing [QA] subtask found"
                # Multiple existing — definitely ASK
                if len(existing_qa) > 1:
                    return "ASK_QA", f"{len(existing_qa)} existing [QA] subtasks — review which (if any) covers this iteration"
                # Single existing — check if it overlaps with intended creation
                ex = existing_qa[0]
                cf = {f.get("name", ""): f.get("value") for f in ex.get("custom_fields", [])}
                ex_state = ""
                ex_version = ""
                if isinstance(cf.get("State"), dict):
                    ex_state = cf["State"].get("name", "")
                if isinstance(cf.get("Release Version"), dict):
                    ex_version = cf["Release Version"].get("name", "")
                # Same release version + not Done → likely the same iteration → use existing
                if ex_version and release_version and ex_version == release_version and ex_state not in ("Done", "Verified", "Closed"):
                    return "USE_EXISTING", f"existing {ex['id']} (v={ex_version}, state={ex_state}) covers this release"
                # Different release version → likely new CR / new iteration → create new
                if ex_version and release_version and ex_version != release_version:
                    return "CREATE_NEW", f"existing {ex['id']} is for v={ex_version}, new subtask for v={release_version} (different release)"
                # Done/closed but new test iteration needed
                if ex_state in ("Done", "Verified", "Closed"):
                    return "ASK_QA", f"existing {ex['id']} is {ex_state} — confirm: re-open it, or create new for current iteration?"
                return "ASK_QA", f"existing {ex['id']} — verify scope vs new iteration"

            verdict, reasoning = _recommendation()

            if not approved:
                # Preview only — no writes. Show graph + recommendation + payload.
                cmds = ["Type Task", "Stack Testing", "Subsystem CRM", f"Priority {priority}"]
                if release_version:
                    cmds.append(f"Release Version {release_version}")
                if sprint:
                    cmds.append(f'Sprint "{sprint}"')
                if story_points is not None:
                    cmds.append(f"SP QA {story_points}")
                cmds.append(f"subtask of {parent_ticket}")
                cmd_str = " ".join(cmds)

                out = ["## 📋 QA Subtask Preview (NOT SUBMITTED — approved=false)", ""]
                out.extend(_render_graph_section())
                out.append("---")
                out.append(f"### 🤖 Recommendation: **{verdict}**")
                out.append(f"_Reasoning:_ {reasoning}")
                out.append("")
                if verdict == "USE_EXISTING":
                    ex = existing_qa[0]
                    out.append(f"⚠️  Brain рекомендует НЕ создавать. Использовать существующий: **{ex['id']}**.")
                    out.append("Если всё же нужно создать новый (например, для отдельного sub-flow) — re-call with `force: true, approved: true`.")
                elif verdict == "ASK_QA":
                    out.append("⚠️  Brain не уверен. Покажи Ярославу полный граф, спроси решение:")
                    out.append("  - использовать существующий?")
                    out.append("  - создать новый с уточнённым scope?")
                    out.append("  - re-open закрытый?")
                    out.append("Только после явного согласия — `approved: true` (+ `force: true` если есть [QA]).")
                else:
                    out.append("✅ Brain рекомендует создать новый [QA] subtask.")
                out.append("")

                out.append("---")
                out.append("### Proposed payload")
                out.append(f"**Title:** `{qa_summary}`")
                out.append(f"**Parent:** {parent_ticket}")
                out.append("**Custom fields (via apply_commands):**")
                out.append(f"```\n{cmd_str}\n```")
                out.append("")
                out.append("**Body:**")
                out.append("```")
                out.append(body_text[:2000])
                out.append("```")
                out.append("")
                out.append("To submit: re-call with `approved: true` (+ `force: true` if existing [QA] should be ignored). Brain MUST show this preview to QA first.")
                return [types.TextContent(type="text", text="\n".join(out))]

            # ── approved=true path ──
            if existing_qa and not force:
                lines = [
                    f"ℹ️  Existing [QA] subtask(s) for {parent_ticket} — creation skipped (idempotency).",
                    "",
                ]
                for ex in existing_qa:
                    cf = {f.get("name", ""): f.get("value") for f in ex.get("custom_fields", [])}
                    state = ""
                    version = ""
                    if isinstance(cf.get("State"), dict):
                        state = cf["State"].get("name") or ""
                    if isinstance(cf.get("Release Version"), dict):
                        version = cf["Release Version"].get("name") or ""
                    meta = []
                    if state:   meta.append(f"state={state}")
                    if version: meta.append(f"v={version}")
                    meta_str = f" ({', '.join(meta)})" if meta else ""
                    lines.append(f"  • **{ex['id']}**{meta_str} — {ex['summary']}")
                lines.append("")
                lines.append(f"Brain recommendation: **{verdict}** — {reasoning}")
                lines.append("")
                lines.append("If you really want to create another [QA] subtask anyway, re-call with `force: true, approved: true`.")
                return [types.TextContent(type="text", text="\n".join(lines))]

            # Step 1: create base issue
            create_result = c.create_issue_basic(qa_summary, body_text)
            if not create_result.get("ok"):
                return [types.TextContent(type="text", text=(
                    f"❌ Failed to create issue.\n"
                    f"Status: {create_result.get('status')}\n"
                    f"Error: {create_result.get('error')}"
                ))]
            new_id = (create_result.get("data") or {}).get("idReadable", "")
            if not new_id:
                return [types.TextContent(type="text", text=(
                    f"❌ Issue created but no idReadable returned. Raw: {create_result.get('data')}"
                ))]

            # Step 2: apply custom fields + parent link via commands
            cmds = ["Type Task", "Stack Testing", "Subsystem CRM", f"Priority {priority}"]
            if release_version:
                cmds.append(f"Release Version {release_version}")
            if sprint:
                cmds.append(f'Sprint "{sprint}"')
            if story_points is not None:
                cmds.append(f"SP QA {story_points}")
            cmds.append(f"subtask of {parent_ticket}")
            cmd_str = " ".join(cmds)

            cmd_result = c.apply_commands(cmd_str, new_id)
            cmd_ok = cmd_result.get("ok", False)

            url = f"{c.base_url}/issue/{new_id}"
            out = [
                f"## ✅ QA Subtask Created — {new_id}",
                "",
                f"**Title:** {qa_summary}",
                f"**Parent:** {parent_ticket}",
                f"**URL:** {url}",
                "",
            ]
            if cmd_ok:
                out.append(f"✓ Custom fields + parent link applied: `{cmd_str}`")
            else:
                out.append(f"⚠️  Issue created BUT custom-field commands failed:")
                out.append(f"   Status: {cmd_result.get('status')}")
                out.append(f"   Error: {cmd_result.get('error')}")
                out.append(f"   You may need to set fields manually in YouTrack UI.")
            out.append("")
            out.append("Journal log it: `scripts/journal.sh log \"Created QA subtask "
                       f"{new_id} for {parent_ticket}\"`")
            return [types.TextContent(type="text", text="\n".join(out))]

        elif name == "create_bug":
            parent_trd       = arguments["parent_trd"].strip()
            bug_summary      = arguments["summary"].strip()
            bug_description  = arguments["description"]
            severity         = arguments["severity"].strip()
            affected_version = arguments["affected_version"].strip()
            priority         = arguments.get("priority", "Normal").strip()
            subsystem        = arguments.get("subsystem", "CRM").strip()
            stack            = arguments.get("stack", "").strip()
            release_version  = arguments.get("release_version", "").strip()
            tags             = arguments.get("tags") or []
            bsource          = arguments.get("bsource", "").strip()
            extra_cmds       = arguments.get("additional_commands", "").strip()
            approved         = bool(arguments.get("approved", False))
            force            = bool(arguments.get("force", False))

            full_title = f"[{parent_trd}] {bug_summary}"
            c = client()

            # Idempotency — search bugs.json for similar OPEN bugs
            keywords = [w for w in re.split(r"\W+", bug_summary) if len(w) >= 4][:5]
            similar = c.find_similar_open_bugs(parent_trd, keywords)

            # Build apply_commands string
            cmd_parts = ["Type Bug", f"Severity {severity}", f"Priority {priority}",
                         f"Subsystem {subsystem}", f"Affected version {affected_version}",
                         # Bugs never go into client release notes (only User Stories do).
                         # Without this field YouTrack workflow rejects with 400 — see
                         # knowledge_base/youtrack_bug_fields.md §32 and TRD-12728 calibration.
                         "To Release Notes No"]
            if stack:           cmd_parts.append(f"Stack {stack}")
            if release_version: cmd_parts.append(f"Release Version {release_version}")
            if bsource:         cmd_parts.append(f"BSource {bsource}")
            for tag in tags:
                # YouTrack tag with spaces needs quoting
                if " " in tag:
                    cmd_parts.append(f'tag "{tag}"')
                else:
                    cmd_parts.append(f"tag {tag}")
            if extra_cmds:      cmd_parts.append(extra_cmds)
            cmd_str = " ".join(cmd_parts)

            if not approved:
                out = ["## 🐛 Create Bug — Preview (NOT SUBMITTED — approved=false)", ""]
                out.append(f"**Title:** `{full_title}`")
                out.append(f"**Parent (in title):** {parent_trd}")
                out.append("")
                out.append("**Custom fields (via apply_commands):**")
                out.append(f"```\n{cmd_str}\n```")
                out.append("")
                out.append("**Description (first 1500 chars):**")
                out.append("```")
                out.append(bug_description[:1500])
                out.append("```")
                out.append("")

                # Idempotency warning
                if similar:
                    out.append(f"⚠️  **{len(similar)} similar OPEN bug(s) found in bugs.json for {parent_trd}:**")
                    for b in similar[:5]:
                        fc = " [1st cohort]" if b.get("is_first_cohort") else ""
                        out.append(f"  • **{b['id']}** [{b.get('status','?')}] {b.get('summary','')[:100]}{fc}")
                    out.append("")
                    out.append("Re-call with `approved: true, force: true` if you intend to file anyway (separate symptom — Daily Rule 6).")
                else:
                    out.append("✓ No similar open bugs found for this parent in bugs.json — safe to create.")
                out.append("")
                out.append("Brain MUST show this preview to Yaroslav. On «да create» → re-call with `approved: true`.")
                return [types.TextContent(type="text", text="\n".join(out))]

            # ── approved=true path ──
            if similar and not force:
                lines = [f"⚠️  Similar OPEN bug(s) for {parent_trd} — creation aborted (idempotency).", ""]
                for b in similar[:5]:
                    fc = " [1st cohort]" if b.get("is_first_cohort") else ""
                    lines.append(f"  • **{b['id']}** [{b.get('status','?')}] {b.get('summary','')[:100]}{fc}")
                lines.append("")
                lines.append("If this is a separate symptom (Daily Rule 6 — one symptom one bug), re-call with `force: true, approved: true`.")
                return [types.TextContent(type="text", text="\n".join(lines))]

            # Create
            create_result = c.create_issue_basic(full_title, bug_description)
            if not create_result.get("ok"):
                return [types.TextContent(type="text", text=(
                    f"❌ Failed to create bug.\n"
                    f"Status: {create_result.get('status')}\n"
                    f"Error: {create_result.get('error')}"
                ))]
            new_id = (create_result.get("data") or {}).get("idReadable", "")

            # Apply commands
            cmd_result = c.apply_commands(cmd_str, new_id)

            url = f"{c.base_url}/issue/{new_id}"
            out = [
                f"## ✅ Bug Created — {new_id}",
                "",
                f"**Title:** {full_title}",
                f"**URL:** {url}",
                "",
            ]
            if cmd_result.get("ok"):
                out.append(f"✓ Custom fields applied: `{cmd_str}`")
            else:
                out.append(f"⚠️  Issue created BUT custom-field commands failed:")
                out.append(f"   Status: {cmd_result.get('status')}")
                out.append(f"   Error: {cmd_result.get('error')}")
                out.append(f"   Set Type=Bug + severity + tags manually in YouTrack UI.")
            out.append("")
            tag_str = ",".join(tags) if tags else ""
            out.append("**Mandatory next step — journal:**")
            tag_arg = f' "{tag_str}"' if tag_str else ""
            out.append("```bash")
            out.append(f'scripts/journal.sh bug {new_id} "{bug_summary}" {affected_version}{tag_arg}')
            out.append("```")
            return [types.TextContent(type="text", text="\n".join(out))]

        elif name == "add_comment":
            ticket_id = arguments["ticket_id"].strip()
            text      = arguments["text"]
            approved  = bool(arguments.get("approved", False))

            if not approved:
                out = ["## 💬 Add Comment — Preview (NOT SUBMITTED — approved=false)", ""]
                out.append(f"**Ticket:** {ticket_id}")
                out.append("")
                out.append("**Comment text:**")
                out.append("```")
                out.append(text[:2000])
                out.append("```")
                out.append("")
                # Language sanity check
                cyrillic_chars = sum(1 for ch in text if 'Ѐ' <= ch <= 'ӿ')
                if cyrillic_chars > len(text) * 0.1:
                    out.append("⚠️  **Language check:** comment contains substantial Cyrillic. Per `qa_persona.md §7` language matrix, comments to dev should be EN. Confirm intentional or rephrase to EN.")
                    out.append("")
                out.append("On «да post» → re-call with `approved: true`.")
                return [types.TextContent(type="text", text="\n".join(out))]

            # Post
            c = client()
            result = c.add_comment(ticket_id, text)
            if not result.get("ok"):
                return [types.TextContent(type="text", text=(
                    f"❌ Failed to post comment.\n"
                    f"Status: {result.get('status')}\n"
                    f"Error: {result.get('error')}"
                ))]
            url = f"{c.base_url}/issue/{ticket_id}"
            return [types.TextContent(type="text", text=(
                f"✅ Comment posted to {ticket_id}.\n"
                f"URL: {url}\n\n"
                f"_Journal it manually if it's a significant interaction_:\n"
                f'`scripts/journal.sh log "Posted comment on {ticket_id} — <one-line>"`'
            ))]

        elif name == "update_ticket_status":
            ticket_id = arguments["ticket_id"].strip()
            new_state = arguments["new_state"].strip()
            comment   = arguments.get("comment", "").strip()
            approved  = bool(arguments.get("approved", False))

            c = client()
            current_state = c.get_state(ticket_id)

            if not approved:
                out = ["## 🔄 Update Ticket Status — Preview (NOT SUBMITTED)", ""]
                out.append(f"**Ticket:** {ticket_id}")
                out.append(f"**Current state:** `{current_state or '?'}`")
                out.append(f"**→ New state:** `{new_state}`")
                out.append("")
                if comment:
                    out.append("**Accompanying comment:**")
                    out.append("```")
                    out.append(comment[:1000])
                    out.append("```")
                else:
                    out.append("⚠️  **No comment provided.** Best practice — add justification comment when transitioning state. Re-call with `comment` field set.")
                out.append("")
                # Validation hints
                if new_state.lower() in ("verified", "won't fix", "wontfix", "done", "closed") and not comment:
                    out.append("⚠️  Terminal state without comment — strongly recommended to explain rationale.")
                    out.append("")
                out.append("On «да update» → re-call with `approved: true`.")
                return [types.TextContent(type="text", text="\n".join(out))]

            # Apply state change (with optional comment posted first)
            results = []
            if comment:
                comment_result = c.add_comment(ticket_id, comment)
                results.append(("comment", comment_result))
            cmd_result = c.apply_commands(f"State {new_state}", ticket_id)
            results.append(("state", cmd_result))

            url = f"{c.base_url}/issue/{ticket_id}"
            out = [f"## ✅ Update Ticket Status — {ticket_id}", "",
                   f"**State:** `{current_state or '?'}` → `{new_state}`",
                   f"**URL:** {url}", ""]
            for op_name, res in results:
                if res.get("ok"):
                    out.append(f"✓ {op_name} — applied")
                else:
                    out.append(f"⚠️  {op_name} — failed: status={res.get('status')} err={res.get('error')}")
            out.append("")
            out.append(f'_Journal_: `scripts/journal.sh log "Status {ticket_id}: {current_state} → {new_state}"`')
            return [types.TextContent(type="text", text="\n".join(out))]

        return [types.TextContent(type="text", text=f"Unknown tool: {name}")]

    except Exception as e:
        return [types.TextContent(type="text", text=f"Error: {e}")]


# ─── Entry ────────────────────────────────────────────────────────────────────

async def main():
    from mcp.server.lowlevel.server import NotificationOptions
    async with mcp.server.stdio.stdio_server() as (read, write):
        await server.run(
            read, write,
            InitializationOptions(
                server_name="youtrack-scalefinal",
                server_version="0.3.0",
                capabilities=server.get_capabilities(
                    notification_options=NotificationOptions(),
                    experimental_capabilities={},
                ),
            ),
        )


if __name__ == "__main__":
    import asyncio
    asyncio.run(main())
