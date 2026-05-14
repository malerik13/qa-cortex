#!/usr/bin/env python3
"""
ScaleFinal QA — Allure TestOps MCP Server
=========================================
Single entry point for every Allure TestOps operation the plugin performs.

Sibling of mcp/youtrack/server.py — same design rules:
  - Credentials come ONLY from .env (ALLURE_BASE_URL, ALLURE_TOKEN, ALLURE_PROJECT_ID).
    NEVER hardcode tokens. Each team member has a personal token.
  - Read operations are unrestricted.
  - Write operations (create_test_case, update_test_case, attach_issue) RETURN a
    payload preview or require an explicit `approved: true` flag from the human.
    The default path is: draft → show user → user says "yes" → call with approved=true.

Tools:
  search_test_cases(query, max_results)        — substring search over local index
  get_test_case(test_case_id)                  — full detail incl. scenario steps (live)
  find_test_cases_by_issue(ticket_id)          — local index lookup: TRD-XXXXX → cases
  list_recent_test_cases(limit)                — latest modified cases (live)
  preview_test_case_payload(name, scenario...) — builds create payload, DOES NOT SUBMIT
  create_test_case(..., approved=True)         — submits the case. Refuses without approved=True.
"""

import json
import os
import sys
from pathlib import Path
from urllib.parse import urlencode

try:
    from dotenv import load_dotenv
except ImportError:
    print("ERROR: python-dotenv not installed. Run: pip install -r requirements.txt", file=sys.stderr)
    sys.exit(1)

PLUGIN_ROOT = Path(__file__).resolve().parent.parent.parent
load_dotenv(PLUGIN_ROOT / ".env")

import requests
import mcp.server.stdio
import mcp.types as types
from mcp.server import Server
from mcp.server.models import InitializationOptions


# ─── Allure Client ────────────────────────────────────────────────────────────

class AllureClient:
    def __init__(self):
        self.base_url = (os.getenv("ALLURE_BASE_URL") or "").rstrip("/")
        self.token = os.getenv("ALLURE_TOKEN") or ""
        try:
            self.project_id = int(os.getenv("ALLURE_PROJECT_ID") or "0")
        except ValueError:
            self.project_id = 0
        try:
            self.integration_id = int(os.getenv("ALLURE_INTEGRATION_ID") or "0")
        except ValueError:
            self.integration_id = 0
        if not self.base_url or not self.token or not self.project_id:
            raise ValueError(
                "Missing ALLURE_BASE_URL / ALLURE_TOKEN / ALLURE_PROJECT_ID. "
                "Copy templates/env.template to .env and fill in."
            )
        self.headers = {
            "Authorization": f"Api-Token {self.token}",
            "Accept": "application/json",
            "Content-Type": "application/json",
        }
        self._issue_cache: dict[str, dict] = {}  # key "TRD-11527" -> {id, integrationId, name, url, closed}

    def _get(self, path: str, params: dict = None, timeout: int = 20):
        url = f"{self.base_url}{path}"
        if params:
            url = f"{url}?{urlencode(params)}"
        r = requests.get(url, headers=self.headers, timeout=timeout)
        if r.status_code != 200:
            return {"_error": f"HTTP {r.status_code}: {r.text[:500]}"}
        try:
            return r.json()
        except ValueError:
            return {"_error": f"Invalid JSON from {path}"}

    def _post(self, path: str, body: dict, timeout: int = 20):
        r = requests.post(f"{self.base_url}{path}", headers=self.headers,
                          json=body, timeout=timeout)
        try:
            data = r.json()
        except ValueError:
            data = {"_raw": r.text[:500]}
        return {"_status": r.status_code, "_body": data}

    def get_test_case(self, tc_id: int):
        return self._get(f"/api/rs/testcase/{tc_id}")

    def get_test_case_scenario(self, tc_id: int):
        """Fetch scenario steps. Allure has two endpoints with different formats:

        - `/step` (singular) — actual source; returns
          `{root: {children: [id...]}, scenarioSteps: {id: {body, expectedResultId, children, ...}}}`
        - `/scenario` (plural) — legacy; often returns `{steps: []}`
          even when case has manual scenario content

        Patterns observed (TRD-12728 calibration 2026-05-13, 19200-19500 scan):
          - 56% of populated cases use NESTED steps (~39 of 69 sampled)
          - Two nesting mechanisms coexist:
            (a) `expectedResultId` → points to an "Expected Result" wrapper
                step whose `children` are the actual expected outcomes
            (b) `children` directly on root step → numbered sub-steps

        We convert to flat `{steps: [...]}` with `{name, expectedResult, steps}`
        recursively. Fall back to `/scenario` only if `/step` empty.
        """
        raw = self._get(f"/api/rs/testcase/{tc_id}/step")
        if raw and not raw.get("_error"):
            root_children = (raw.get("root") or {}).get("children") or []
            scenario_steps = raw.get("scenarioSteps") or {}
            result = [
                self._build_step(sid, scenario_steps)
                for sid in root_children
            ]
            result = [s for s in result if s.get("name") or s.get("steps")]
            if result:
                return {"steps": result}
        # Fallback — /scenario legacy endpoint
        return self._get(f"/api/rs/testcase/{tc_id}/scenario")

    def _build_step(self, sid, scenario_steps: dict) -> dict:
        """Recursively build a step from scenarioSteps dict.

        Returns: {name, expectedResult, steps}
        - name = step body
        - expectedResult = newline-joined children of the expectedResultId
          wrapper step (if any), preserving Allure's "Expected Result"
          convention without rendering the wrapper label
        - steps = recursive sub-steps from this step's `children` field
        """
        s = scenario_steps.get(str(sid)) or scenario_steps.get(sid) or {}
        if not s:
            return {"name": "", "expectedResult": "", "steps": []}

        name = (s.get("body") or "").strip()

        # Resolve expectedResultId → wrapper.children → multi-line expected text
        expected_lines = []
        er_id = s.get("expectedResultId")
        if er_id:
            wrapper = scenario_steps.get(str(er_id)) or scenario_steps.get(er_id) or {}
            wrapper_children = wrapper.get("children") or []
            if wrapper_children:
                for cid in wrapper_children:
                    cs = scenario_steps.get(str(cid)) or scenario_steps.get(cid) or {}
                    line = (cs.get("body") or "").strip()
                    if line:
                        expected_lines.append(line)
            else:
                # Wrapper might have direct body content (no children)
                wrapper_body = (wrapper.get("body") or "").strip()
                if wrapper_body and wrapper_body.lower() != "expected result":
                    expected_lines.append(wrapper_body)

        # Recurse into direct sub-steps (numbered 1.1, 1.2 in rendering)
        sub_steps = []
        for cid in (s.get("children") or []):
            sub = self._build_step(cid, scenario_steps)
            if sub.get("name") or sub.get("steps"):
                sub_steps.append(sub)

        return {
            "name": name,
            "expectedResult": "\n".join(expected_lines),
            "steps": sub_steps,
        }

    def get_test_case_issues(self, tc_id: int):
        return self._get(f"/api/rs/testcase/{tc_id}/issue")

    def list_test_cases(self, page: int = 0, size: int = 50):
        return self._get("/api/rs/testcase", {
            "projectId": self.project_id,
            "page": page,
            "size": size,
            "sort": "lastModifiedDate,desc",
        })

    def create_test_case(self, payload: dict):
        # Ensure required projectId
        body = dict(payload)
        body.setdefault("projectId", self.project_id)
        return self._post("/api/rs/testcase", body)

    def set_scenario(self, tc_id: int, steps: list[dict]):
        """Scenario must be posted separately — the /testcase POST ignores it.
        Endpoint: POST /api/rs/testcase/{id}/scenario, body {"steps":[...]}."""
        return self._post(f"/api/rs/testcase/{tc_id}/scenario", {"steps": steps})

    def get_testcase_cfv(self, tc_id: int):
        """Read custom field values already attached to a test case."""
        return self._get(f"/api/rs/testcase/{tc_id}/cfv")

    def set_testcase_cfv(self, tc_id: int, cfv_refs: list[dict]):
        """Attach custom field values (Feature, Story, Epic...) to a test case.
        Each ref is {"id": <cfv_id>, "name": "<display>", "customField": {"id": <-2|-3|-1>, "name": "<Feature|Story|Epic>"}}.
        The API is picky — it REJECTS an object (must be an array) and REJECTS a plain
        {id: N} element (must be the full CFV dto wrapper). This helper enforces the shape.
        Endpoint: POST /api/rs/testcase/{id}/cfv, body: array of CustomFieldValueWithCfDto."""
        normalized = []
        for r in cfv_refs:
            if not isinstance(r, dict) or "id" not in r:
                continue
            cf = r.get("customField") or {}
            normalized.append({
                "id": r["id"],
                "name": r.get("name", ""),
                "customField": {
                    "id": cf.get("id"),
                    "name": cf.get("name", ""),
                },
            })
        return self._post(f"/api/rs/testcase/{tc_id}/cfv", normalized)

    def find_cfv_from_reference_case(self, reference_tc_id: int) -> list[dict]:
        """Reuse the Feature/Story/Epic CFV values already set on another test case.
        Handy when creating a sibling case: pass one of the existing TRD-XXXXX cases
        as reference and its Feature+Story will auto-attach to the new one."""
        data = self.get_testcase_cfv(reference_tc_id)
        if not isinstance(data, list):
            return []
        return data

    # ─── Issue tracker links (first-class "Issues links" in Allure UI) ─────
    # NOTE: These live on a different endpoint (/api/testcase/{id}/issue) than
    # the generic REST API (/api/rs/...). The `links` array on the test case
    # object is a SEPARATE mechanism ("Links" section) and is not what users
    # see as "Issues links". Always use set_issues() for proper YT binding.

    def _load_all_issues(self):
        """Cache all issues from the YouTrack integration. ~600 issues, ~4 pages."""
        if self._issue_cache:
            return
        if not self.integration_id:
            return
        page = 0
        while True:
            data = self._get("/api/issue", {
                "integrationId": self.integration_id,
                "page": page,
                "size": 200,
            })
            if not isinstance(data, dict) or "content" not in data:
                break
            for it in data.get("content", []) or []:
                key = it.get("name")
                if key:
                    self._issue_cache[key] = {
                        "id": it.get("id"),
                        "integrationId": it.get("integrationId", self.integration_id),
                        "name": key,
                        "url": it.get("url", ""),
                        "closed": it.get("closed", False),
                    }
            if data.get("last") or page + 1 >= data.get("totalPages", 1):
                break
            page += 1

    def resolve_issue_refs(self, keys: list[str]) -> list[dict]:
        """Turn a list of ['TRD-11527', ...] into Allure-ready issue refs."""
        if not keys:
            return []
        self._load_all_issues()
        yt_base = (os.getenv("YOUTRACK_BASE_URL") or "https://youtrack.scalefinal.io").rstrip("/")
        resolved = []
        for k in keys:
            k = k.strip()
            if not k:
                continue
            cached = self._issue_cache.get(k)
            if cached:
                resolved.append(cached)
            else:
                # Fallback: construct a minimal ref. Allure may reject unknown issues,
                # but worth trying — at minimum this surfaces a clear error.
                resolved.append({
                    "integrationId": self.integration_id,
                    "name": k,
                    "url": f"{yt_base}/issue/{k}",
                    "closed": False,
                })
        return resolved

    def set_issues(self, tc_id: int, issue_refs: list[dict]):
        """Attach YouTrack issues to a test case as first-class Issues links.
        Endpoint: POST /api/testcase/{id}/issue (note: /api/testcase, NOT /api/rs/testcase).
        Body: array of {id, integrationId, name, url, closed}."""
        url = f"{self.base_url}/api/testcase/{tc_id}/issue"
        r = requests.post(url, headers=self.headers, json=issue_refs, timeout=20)
        try:
            data = r.json()
        except ValueError:
            data = {"_raw": r.text[:500]}
        return {"_status": r.status_code, "_body": data}


# ─── Local index (knowledge_base/test_cases.json) ─────────────────────────────

INDEX_PATH = PLUGIN_ROOT / "knowledge_base" / "test_cases.json"


def load_index() -> dict:
    if not INDEX_PATH.exists():
        return {"generated_at": None, "cases": []}
    try:
        with open(INDEX_PATH, encoding="utf-8") as f:
            return json.load(f)
    except (json.JSONDecodeError, OSError):
        return {"generated_at": None, "cases": []}


def search_index_by_name(query: str, limit: int = 20) -> list[dict]:
    idx = load_index()
    q = query.lower().strip()
    if not q:
        return []
    results = []
    for c in idx.get("cases", []):
        name = (c.get("name") or "").lower()
        if q in name:
            results.append(c)
            if len(results) >= limit:
                break
    return results


def find_by_issue(ticket_id: str) -> list[dict]:
    """Find test cases associated with a TRD ticket.

    Allure test cases reference YouTrack tickets through TWO channels:
      1. `links` array with entries of type=ISSUE (first-class).
      2. Story/Feature/Epic custom-field values whose `name` starts with 'TRD-XXXXX'.
         This is the common case for ScaleFinal — existing TRD-linked cases often
         have empty `links` and only the CFV reference.
    We match on both.
    """
    idx = load_index()
    needle = ticket_id.strip().upper()
    if not needle:
        return []
    results = []
    for c in idx.get("cases", []):
        matched = False
        # Channel 1 — ISSUE links
        for link in c.get("links", []) or []:
            if link.get("type") == "ISSUE" and (link.get("name") or "").upper() == needle:
                results.append(c)
                matched = True
                break
        if matched:
            continue
        # Channel 2 — CFV names starting with TRD-XXXXX
        for v in c.get("cfvs", []) or []:
            name_upper = (v.get("name") or "").upper()
            if name_upper.startswith(needle + " ") or name_upper == needle or name_upper.startswith(needle + "]") or f"[{needle}]" in name_upper:
                results.append(c)
                break
    return results


# ─── MCP Server ───────────────────────────────────────────────────────────────

server = Server("allure-scalefinal")
_client: AllureClient | None = None


def client() -> AllureClient:
    global _client
    if _client is None:
        _client = AllureClient()
    return _client


@server.list_tools()
async def list_tools() -> list[types.Tool]:
    return [
        types.Tool(
            name="search_test_cases",
            description=(
                "Substring search over the local Allure index "
                "(knowledge_base/test_cases.json). Fast; use this for most queries. "
                "If the index is missing or stale, run scripts/update-allure-index.py."
            ),
            inputSchema={
                "type": "object",
                "properties": {
                    "query": {"type": "string", "description": "text to match in test-case name (case-insensitive)"},
                    "max_results": {"type": "integer", "default": 20},
                },
                "required": ["query"],
            },
        ),
        types.Tool(
            name="get_test_case",
            description=(
                "Fetch a single Allure test case by numeric ID — live call. "
                "Returns metadata + linked YouTrack issues + scenario steps."
            ),
            inputSchema={
                "type": "object",
                "properties": {
                    "test_case_id": {"type": "integer", "description": "Numeric Allure test case ID"}
                },
                "required": ["test_case_id"],
            },
        ),
        types.Tool(
            name="find_test_cases_by_issue",
            description=(
                "Find all Allure test cases linked to a YouTrack ticket ID (e.g. TRD-11527). "
                "Uses the local index for case list — ensure it's fresh. "
                "Pass include_scenario=true to additionally fetch scenario steps for each case "
                "via live API (default false for speed). Capped at 20 cases when include_scenario=true."
            ),
            inputSchema={
                "type": "object",
                "properties": {
                    "ticket_id": {"type": "string", "description": "YouTrack ticket ID (e.g. TRD-11527)"},
                    "include_scenario": {"type": "boolean", "description": "When true, fetches scenario steps (incl. sub-steps) live for each linked case. Slower but complete. Default false."},
                    "max_cases": {"type": "integer", "description": "Max cases to fetch scenarios for when include_scenario=true. Default 20."},
                },
                "required": ["ticket_id"],
            },
        ),
        types.Tool(
            name="list_recent_test_cases",
            description=(
                "List the most recently modified test cases — live call. "
                "Useful when the local index is stale and you want a quick pulse."
            ),
            inputSchema={
                "type": "object",
                "properties": {
                    "limit": {"type": "integer", "default": 20, "maximum": 100},
                },
            },
        ),
        types.Tool(
            name="preview_test_case_payload",
            description=(
                "Build a create-test-case payload for human review. "
                "THIS TOOL NEVER SUBMITS. It returns the JSON that would be posted to "
                "POST /api/rs/testcase, so the QA can review and approve before any write. "
                "To put the new case in the same tree branch as existing sibling cases, "
                "pass `reference_case_id` — Feature/Story/Epic CFVs will be copied from it."
            ),
            inputSchema={
                "type": "object",
                "properties": {
                    "name":        {"type": "string", "description": "Test case title, e.g. '[TRD-11527] Language — DB persistence on Sign In'"},
                    "description": {"type": "string", "description": "Markdown description / context. Usually references the TRD URL."},
                    "precondition":{"type": "string", "description": "Optional preconditions"},
                    "scenario":    {"type": "array",  "items": {"type": "string"}, "description": "Flat list of scenario step names (root-level)"},
                    "issue_links": {"type": "array",  "items": {"type": "string"}, "description": "YouTrack ticket IDs to link, e.g. ['TRD-11527']"},
                    "tags":        {"type": "array",  "items": {"type": "string"}, "description": "Optional tags"},
                    "reference_case_id": {"type": "integer", "description": "Optional. ID of an existing sibling test case whose Feature/Story/Epic CFVs should be reused. Puts the new case in the same tree branch."},
                },
                "required": ["name", "scenario"],
            },
        ),
        types.Tool(
            name="create_test_case",
            description=(
                "Submit a test case to Allure TestOps. REQUIRES approved=True — otherwise "
                "refuses and returns the payload preview instead. Human-in-the-loop gate. "
                "If `reference_case_id` is provided, the new case's Feature/Story/Epic CFVs "
                "are copied from that reference so it lands in the same tree branch."
            ),
            inputSchema={
                "type": "object",
                "properties": {
                    "name":        {"type": "string"},
                    "description": {"type": "string"},
                    "precondition":{"type": "string"},
                    "scenario":    {"type": "array",  "items": {"type": "string"}},
                    "issue_links": {"type": "array",  "items": {"type": "string"}},
                    "tags":        {"type": "array",  "items": {"type": "string"}},
                    "reference_case_id": {"type": "integer", "description": "Optional. Copy Feature/Story/Epic CFVs from this existing case."},
                    "approved":    {"type": "boolean", "description": "Must be true. If false/missing, the tool refuses and returns the preview."},
                },
                "required": ["name", "scenario", "approved"],
            },
        ),
    ]


def _build_payload(args: dict) -> dict:
    """Normalize a test-case draft into an Allure create payload.

    Important Allure quirks captured here:
      - `scenario.steps` are included in the preview for readability but MUST be
        POSTed separately to /api/rs/testcase/{id}/scenario — the create endpoint
        silently drops them.
      - We intentionally DO NOT emit a `links` array. The generic `links` on a
        test case show up as a secondary "Links" section in the UI, not as the
        primary "Issues links". Proper Issues links are set via a separate POST
        to /api/testcase/{id}/issue — see AllureClient.set_issues.
      - `issue_links` from user input is preserved in the preview for readability
        and consumed by the submit flow to call set_issues.
    """
    steps = [{"name": s} for s in (args.get("scenario") or []) if s]
    payload = {
        "name": args["name"],
    }
    if args.get("description"):
        payload["description"] = args["description"]
    if args.get("precondition"):
        payload["precondition"] = args["precondition"]
    if steps:
        payload["scenario"] = {"steps": steps}
    if args.get("tags"):
        payload["tags"] = [{"name": t} for t in args["tags"]]
    # Keep issue_links visible in the preview (not submitted with the create call)
    if args.get("issue_links"):
        payload["_issues_will_be_attached"] = list(args["issue_links"])
    return payload


def _split_payload_for_submit(payload: dict) -> tuple[dict, list[dict]]:
    """Allure create endpoint rejects scenario in the body silently (returns
    200 but saves no steps). Split into (main_body, steps_list) so the caller
    can do a two-phase submit: POST /testcase, then POST /testcase/{id}/scenario.
    Also drop the preview-only `_issues_will_be_attached` field — it's not a
    real Allure field.
    """
    main = dict(payload)
    scenario = main.pop("scenario", None) or {}
    steps = scenario.get("steps", []) or []
    main.pop("_issues_will_be_attached", None)
    return main, steps


def render_steps(steps: list, prefix: str = "", indent: int = 0) -> list[str]:
    """Recursive rendering of nested scenario steps.

    Produces lines like:
      1. Step name
         _Expected:_ first line
                     second line
         1.1 Sub-step
            _Expected:_ ...
            1.1.1 Sub-sub-step
    """
    out = []
    indent_str = "   " * indent
    for i, s in enumerate(steps, 1):
        num = f"{prefix}{i}" if prefix else str(i)
        name = (s.get("name") or "").strip()
        expected = (s.get("expectedResult") or "").strip()
        sub = s.get("steps") or []
        out.append(f"{indent_str}{num}. {name}")
        if expected:
            for j, line in enumerate(expected.split("\n")):
                label = "_Expected:_ " if j == 0 else "             "
                out.append(f"{indent_str}   {label}{line[:200]}")
        if sub:
            out.extend(render_steps(sub, prefix=f"{num}.", indent=indent + 1))
    return out


@server.call_tool()
async def call_tool(name: str, arguments: dict) -> list[types.TextContent]:
    try:
        if name == "search_test_cases":
            q = arguments["query"]
            limit = arguments.get("max_results", 20)
            cases = search_index_by_name(q, limit)
            if not cases:
                idx = load_index()
                if not idx.get("cases"):
                    return [types.TextContent(type="text", text=(
                        "Local index is empty. Run:\n\n"
                        "  .venv/bin/python scripts/update-allure-index.py\n\n"
                        "This pulls all test cases from Allure TestOps (~2–5 min)."
                    ))]
                return [types.TextContent(type="text", text=f"No test cases matching '{q}'.")]
            lines = [f"## Test cases matching '{q}' ({len(cases)})\n"]
            for c in cases:
                issue_names = [l.get("name", "") for l in (c.get("links") or []) if l.get("type") == "ISSUE"]
                issues = f"  → {', '.join(issue_names)}" if issue_names else ""
                lines.append(f"- **{c.get('id')}** [{c.get('status', '?')}] {c.get('name', '')}{issues}")
            return [types.TextContent(type="text", text="\n".join(lines))]

        elif name == "get_test_case":
            tc_id = int(arguments["test_case_id"])
            c = client()
            tc = c.get_test_case(tc_id)
            if tc.get("_error"):
                return [types.TextContent(type="text", text=f"Error: {tc['_error']}")]
            scenario = c.get_test_case_scenario(tc_id)
            out = [f"# Allure Test Case #{tc.get('id')}: {tc.get('name', '')}\n"]
            status = (tc.get("status") or {}).get("name", "?")
            out.append(f"**Status:** {status} | **Automated:** {tc.get('automated', False)}")
            if tc.get("description"):
                out.append(f"\n**Description:**\n{tc['description']}")
            links = tc.get("links") or []
            if links:
                out.append("\n**Links:**")
                for l in links:
                    out.append(f"- [{l.get('type', '?')}] {l.get('name', '')} — {l.get('url', '')}")
            steps = (scenario or {}).get("steps", [])
            if steps:
                out.append("\n**Scenario:**")
                out.extend(render_steps(steps))
            return [types.TextContent(type="text", text="\n".join(out))]

        elif name == "find_test_cases_by_issue":
            tid = arguments["ticket_id"].strip().upper()
            include_scenario = bool(arguments.get("include_scenario", False))
            max_cases = int(arguments.get("max_cases", 20))

            cases = find_by_issue(tid)
            idx = load_index()
            if not idx.get("cases"):
                return [types.TextContent(type="text", text=(
                    "Local index is empty. Run `.venv/bin/python scripts/update-allure-index.py` first."
                ))]
            if not cases:
                return [types.TextContent(type="text", text=f"No test cases linked to {tid} in local index.")]

            lines = [f"## Test cases linked to {tid} ({len(cases)})\n"]

            if not include_scenario:
                # Fast list mode (legacy behavior)
                for c in cases:
                    lines.append(f"- **{c.get('id')}** [{c.get('status', '?')}] {c.get('name', '')}")
                lines.append("")
                lines.append("_Pass `include_scenario: true` to fetch step-by-step scenarios for each case._")
                return [types.TextContent(type="text", text="\n".join(lines))]

            # Scenario-enriched mode — live API call per case
            cl = client()
            cap_hit = len(cases) > max_cases
            cases_to_fetch = cases[:max_cases]

            for c in cases_to_fetch:
                tc_id = c.get("id")
                lines.append(f"\n### Case #{tc_id} [{c.get('status', '?')}] — {c.get('name', '')}")

                # Description (from index)
                desc = (c.get("description") or "").strip()
                if desc:
                    lines.append(f"\n_Description:_ {desc[:300]}")

                # Live scenario fetch
                try:
                    scenario = cl.get_test_case_scenario(int(tc_id))
                except Exception as e:
                    lines.append(f"\n⚠️  scenario fetch failed: {e}")
                    continue

                if scenario is None or scenario.get("_error"):
                    err = (scenario or {}).get("_error", "no data")
                    lines.append(f"\n⚠️  scenario unavailable: {err}")
                    continue

                steps = (scenario or {}).get("steps", [])
                if not steps:
                    lines.append(f"\n_(no scenario steps)_")
                    continue

                lines.append("\n**Scenario:**")
                lines.extend(render_steps(steps))

            if cap_hit:
                lines.append("")
                lines.append(f"⚠️  Showed first {max_cases} of {len(cases)} cases. Pass `max_cases: N` to extend, or fetch specific cases via `get_test_case(id)`.")

            return [types.TextContent(type="text", text="\n".join(lines))]

        elif name == "list_recent_test_cases":
            limit = min(arguments.get("limit", 20), 100)
            data = client().list_test_cases(page=0, size=limit)
            if data.get("_error"):
                return [types.TextContent(type="text", text=f"Error: {data['_error']}")]
            items = data.get("content", [])
            lines = [f"## {len(items)} most recently modified test cases\n"]
            for c in items:
                status = (c.get("status") or {}).get("name", "?")
                lines.append(f"- **{c.get('id')}** [{status}] {c.get('name', '')}")
            return [types.TextContent(type="text", text="\n".join(lines))]

        elif name == "preview_test_case_payload":
            payload = _build_payload(arguments)
            out = [
                "## 📋 Allure Test Case Payload Preview (NOT SUBMITTED)",
                "",
                "This is a preview only. Review the JSON below.",
                "To submit, call `create_test_case` with the same fields plus `approved: true`.",
                "",
                "```json",
                json.dumps(payload, indent=2, ensure_ascii=False),
                "```",
            ]
            return [types.TextContent(type="text", text="\n".join(out))]

        elif name == "create_test_case":
            if not arguments.get("approved"):
                payload = _build_payload(arguments)
                out = [
                    "## ❌ Create refused — `approved` is not True",
                    "",
                    "Human-in-the-loop gate: ask the QA to confirm before submitting.",
                    "Preview of the payload that would be posted:",
                    "",
                    "```json",
                    json.dumps(payload, indent=2, ensure_ascii=False),
                    "```",
                ]
                return [types.TextContent(type="text", text="\n".join(out))]

            full_payload = _build_payload(arguments)
            main_body, steps = _split_payload_for_submit(full_payload)
            c = client()
            create_result = c.create_test_case(main_body)
            status = create_result.get("_status")
            body = create_result.get("_body")
            if not (status and 200 <= status < 300):
                return [types.TextContent(type="text", text=(
                    f"❌ Create failed (HTTP {status}):\n\n"
                    f"```json\n{json.dumps(body, indent=2, ensure_ascii=False)}\n```"
                ))]

            new_id = (body or {}).get("id")
            base = (os.getenv("ALLURE_BASE_URL") or "").rstrip("/")
            pid = os.getenv("ALLURE_PROJECT_ID")
            url = f"{base}/project/{pid}/test-cases/{new_id}" if new_id else "(url unknown)"

            # Phase 2 — submit scenario steps separately (Allure quirk)
            scenario_note = ""
            if steps and new_id:
                scen_result = c.set_scenario(new_id, steps)
                scen_status = scen_result.get("_status")
                if scen_status and 200 <= scen_status < 300:
                    scenario_note = f"\n✅ Scenario: {len(steps)} steps attached."
                else:
                    scenario_note = (
                        f"\n⚠️  Scenario submit failed (HTTP {scen_status}). "
                        f"Test case exists but has no steps — retry manually:\n"
                        f"  POST /api/rs/testcase/{new_id}/scenario"
                    )

            # Phase 3 — attach Feature/Story/Epic CFVs so the case appears in the
            # right tree branch. Only runs if reference_case_id was provided.
            cfv_note = ""
            ref_id = arguments.get("reference_case_id")
            if ref_id and new_id:
                cfvs = c.find_cfv_from_reference_case(int(ref_id))
                if cfvs:
                    cfv_result = c.set_testcase_cfv(new_id, cfvs)
                    cs = cfv_result.get("_status")
                    if cs and 200 <= cs < 300:
                        names = ", ".join(f"{(v.get('customField') or {}).get('name')}={v.get('name')[:40]}" for v in cfvs)
                        cfv_note = f"\n✅ CFVs copied from case #{ref_id}: {names}"
                    else:
                        cfv_note = f"\n⚠️  CFV attach failed (HTTP {cs}). Set Feature/Story manually in Allure UI."
                else:
                    cfv_note = f"\n⚠️  Reference case #{ref_id} has no CFVs to copy."

            # Phase 4 — attach first-class Issues links (YouTrack tickets).
            # This is the "Issues links: TRD-XXXXX" block in the Allure UI.
            # It requires /api/testcase/{id}/issue (note: no /rs/ prefix).
            issues_note = ""
            yt_keys = arguments.get("issue_links") or []
            if yt_keys and new_id:
                refs = c.resolve_issue_refs(yt_keys)
                if refs and all(r.get("id") for r in refs):
                    issue_result = c.set_issues(new_id, refs)
                    istat = issue_result.get("_status")
                    if istat and 200 <= istat < 300:
                        issues_note = f"\n✅ Issues linked: {', '.join(r['name'] for r in refs)}"
                    else:
                        issues_note = (
                            f"\n⚠️  Issue link failed (HTTP {istat}). Body: "
                            f"{json.dumps(issue_result.get('_body'), ensure_ascii=False)[:300]}"
                        )
                else:
                    missing = [k for k, r in zip(yt_keys, refs) if not r.get("id")]
                    issues_note = (
                        f"\n⚠️  Could not resolve Allure issue ids for {missing}. "
                        f"Check ALLURE_INTEGRATION_ID in .env and that the issues exist in Allure's integration cache."
                    )

            return [types.TextContent(type="text", text=(
                f"✅ Test case created: #{new_id}\n{url}{scenario_note}{cfv_note}{issues_note}\n\n"
                f"```json\n{json.dumps(body, indent=2, ensure_ascii=False)}\n```"
            ))]

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
                server_name="allure-scalefinal",
                server_version="0.2.0",
                capabilities=server.get_capabilities(
                    notification_options=NotificationOptions(),
                    experimental_capabilities={},
                ),
            ),
        )


if __name__ == "__main__":
    import asyncio
    asyncio.run(main())
