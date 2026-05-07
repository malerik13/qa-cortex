# Phase 2 — Detailed Roadmap (Steps 2-10)

> **Status:** PLAN · awaiting Yaroslav approval before each step
> **Created:** 2026-05-07
> **Scope:** Adapter framework + 4 default providers + dispatch + skill refactor + integration tests
> **Effort estimate:** 17-25h focused work, calendar 2-3 weeks
> **Parent:** `qa_cortex_v1.md` §12 Phase 2 (this doc expands the bullet list)
> **Reading time:** ~12 min

---

## Recap — where we are

Phase 1 (skeleton) and Phase 2 Step 1 (Protocol contracts) are **DONE**. Tagged `v0.0.1-alpha` and `v0.0.2-alpha`.

**Adapter contract is immutable.** All remaining work is implementation against the Protocols defined in `qa_cortex/providers/base.py`. No more architectural decisions — just mechanical execution + integration testing.

---

## Step 2 — JiraProvider (concrete) [HIGH PRIORITY]

**Goal:** First concrete TicketingProvider implementation. Default backend for v1.0.

### Deliverables

```
qa_cortex/providers/jira.py             ← JiraProvider class
qa_cortex/providers/_normalizers.py     ← shared shape conversion utilities
tests/providers/test_jira.py            ← unit tests with mock requests
docs/examples/jira-config.toml          ← example config snippet
```

### Implementation approach

**Option A (recommended): wrap `sooperset/mcp-atlassian` programmatically**
- Their library is mature (5.1k★, MIT, active)
- Don't reinvent Jira REST API client
- We add: canonical-shape conversion + two-step approval gate
- Dependency: `pip install mcp-atlassian` (or just `atlassian-python-api` if mcp-atlassian doesn't expose Python API cleanly — investigate first)

**Option B (fallback): direct atlassian-python-api**
- More control but more code
- Use if `sooperset/mcp-atlassian` is awkward as Python lib (it's primarily an MCP server)

### Steps

1. Investigate `sooperset/mcp-atlassian` Python API surface — is it usable as library or only as MCP server?
2. If lib usable: wrap via `JiraProvider(TicketingProvider)` class
3. If only MCP-server form: spawn it as subprocess, communicate via MCP protocol (more complex)
4. Implement methods one at a time:
   - `get_ticket` — easiest, just normalize Jira issue → canonical
   - `search_tickets` — pass JQL or convert free-text to JQL
   - `get_linked_tickets` — extract from `issuelinks` field
   - `get_comments` — separate REST call
   - `create_ticket` with two-step gate — preview, then on `approved=True` create
   - `add_comment` with two-step gate
   - `transition_ticket` — Jira workflow transitions
   - `update_ticket` — partial field updates
5. Idempotency check for `create_ticket` preview — JQL search for similar OPEN tickets in same project

### Edge cases to handle

- **Jira ADF (Atlassian Document Format)** — Jira Cloud uses ADF for description. Adapter must convert Markdown ↔ ADF.
- **Custom fields** — Jira has `customfield_NNNNN` IDs. Must map to human names.
- **Workflow transitions** — `transition_ticket("Done")` requires looking up transition ID for "Done" first.
- **Component / version handling** — these are Jira-specific structured fields.
- **Permissions** — `PermissionError` if user lacks issue creation permission in project.

### Validation

- `tests/providers/test_jira.py` with mock HTTP responses (use `responses` lib or `pytest-httpx`)
- Each public method has at least 1 happy path + 1 error path test
- Test approval gate: `create_ticket(approved=False)` returns preview, no HTTP write
- Test idempotency_check: returns similar OPEN tickets

### Effort: 3-4h
### Depends on: Step 1 (done)

---

## Step 3 — TestRailProvider [HIGH PRIORITY]

**Goal:** TestManagementProvider implementation for default backend.

### Deliverables

```
qa_cortex/providers/testrail.py
tests/providers/test_testrail.py
docs/examples/testrail-config.toml
```

### Implementation approach

**Option A (recommended): direct TestRail Python API**
- `pip install testrail-api` (community lib, well-maintained)
- More predictable than wrapping `bun913/mcp-testrail` (which is npm/Node-based)

**Option B: subprocess to Node-based MCP**
- Awkward — would need Node runtime as dep just for TestRail
- Avoid if possible

### Steps

1. `pip install testrail-api` — verify it works
2. Implement methods:
   - `get_test_case(case_id, include_steps=True)` — basic
   - `search_test_cases` — TestRail filter syntax
   - `find_cases_by_linked_ticket` — via custom field that links cases to tickets (project-specific config)
   - `get_run` — TestRail run / plan / milestone
   - `create_test_case` with two-step gate
   - `add_result` with two-step gate
3. Convert TestRail step format to canonical `[{step, expected}, ...]`

### Edge cases

- **Custom step formats** — TestRail supports separated_steps (structured) vs single_field (text). Adapter handles both.
- **Project-specific custom fields** — `find_cases_by_linked_ticket` needs to know which custom field has the ticket reference. Config: `linked_ticket_field = "custom_jira_id"`.
- **Sections vs Folders** — TestRail uses sections; adapter maps to canonical "section".

### Effort: 2-3h
### Depends on: Step 1 (done)

---

## Step 4 — ConfluenceProvider [MEDIUM PRIORITY]

**Goal:** DocumentationProvider for default backend. Read-only — no `create_page`/`update_page` methods.

### Deliverables

```
qa_cortex/providers/confluence.py
tests/providers/test_confluence.py
docs/examples/confluence-config.toml
```

### Implementation approach

**Option A (recommended): reuse `atlassian-python-api`** (already pulled in for Jira if Step 2 chose Option B)
- Confluence and Jira share auth and library
- Saves dependency

### Steps

1. Implement:
   - `search(query, space)` — Confluence CQL query
   - `get_page(page_id)` — fetch with body
   - `list_spaces()` — list user-accessible spaces
2. Convert Confluence storage format → Markdown
   - Use `atlassian-python-api`'s built-in conversion if available
   - Or `markdownify` lib

### Edge cases

- **Confluence has multiple body formats** — `storage`, `view`, `editor`, `export_view`. Use `view` for cleanest HTML, then convert to Markdown.
- **Spaces vs personal-spaces** — `list_spaces()` filters to user-accessible.
- **Permissions** — adapter respects view-only access (which is typical for QA reading product docs).

### Effort: 1-2h
### Depends on: Step 2 (shared deps + auth pattern)

---

## Step 5 — SlackProvider [MEDIUM PRIORITY]

**Goal:** ChatProvider for default backend.

### Deliverables

```
qa_cortex/providers/slack.py
tests/providers/test_slack.py
docs/examples/slack-config.toml
```

### Implementation approach

**Option A (recommended): direct `slack-sdk`**
- Official Slack Python SDK
- Mature, well-documented
- `pip install slack-sdk`

### Steps

1. Implement:
   - `list_channels(include_private=False)` — `client.conversations_list`
   - `get_channel_history` — `client.conversations_history`
   - `get_thread_replies` — `client.conversations_replies`
   - `find_user(username_or_email)` — `client.users_lookupByEmail` or `users_list` + filter
   - `post_message` with two-step gate
   - `add_reaction` with two-step gate

### Edge cases

- **Bot token vs User token scopes** — adapter needs to declare required scopes in docstring (`channels:history`, `chat:write`, etc.)
- **Rate limiting** — Slack tier-based; adapter needs retry-with-backoff on 429
- **Thread vs main channel** — `post_message` with `thread_ts` posts to thread

### Effort: 1-2h
### Depends on: Step 1 (done)

---

## Step 6 — Config loader [BLOCKING for Step 7+]

**Goal:** Parse `qa-cortex.config.toml`, resolve env-var substitutions, validate.

### Deliverables

```
qa_cortex/config/loader.py
qa_cortex/config/schema.py            ← validation schema (pydantic OR plain dict)
tests/config/test_loader.py
templates/qa-cortex.config.toml.tmpl  ← user-customizable template
docs/configuration.md                  ← config reference
```

### Steps

1. Choose validation approach: `pydantic-settings` (rich) vs plain dict + manual checks (lightweight). **Recommendation: pydantic-settings** — common in Python ecosystem, handles env vars naturally.
2. Define `QACortexConfig` model:
   ```python
   class ProvidersConfig(BaseSettings):
       ticketing: Literal["jira", "linear", "github", "youtrack"]
       test_management: Literal["testrail", "zephyr", "allure"]
       documentation: Literal["confluence", "notion"]
       chat: Literal["slack", "teams"]
       browser: Literal["playwright"] = "playwright"

   class JiraConfig(BaseSettings):
       url: HttpUrl
       email: EmailStr
       api_token: SecretStr
       ticket_prefix: str
       # ... etc
   ```
3. Loader function: read TOML → resolve `${VAR}` env-var substitutions → validate → return typed config
4. Connectivity test: `validate_config()` calls each provider's `__init__` and `get_*` lightly to verify reachability

### Edge cases

- Missing required keys → clear error pointing at which file/key
- Env var not set → surface clearly
- TOML parse errors → human-readable
- Network unreachable on connectivity test → don't fail config load, but log warning

### Effort: 1-1.5h
### Depends on: Step 1

---

## Step 7 — load_provider() dispatch [SHORT]

**Goal:** Implement the stub function in `qa_cortex/providers/base.py`.

### Deliverables

Update `qa_cortex/providers/base.py`:

```python
def load_provider(category: str, config: dict[str, Any]) -> Any:
    selected = config["providers"][category]  # e.g. "jira"

    # Lazy import — only loads provider module if it's selected
    if category == "ticketing":
        if selected == "jira":
            from .jira import JiraProvider
            return JiraProvider(config["ticketing"]["jira"])
        elif selected == "linear":
            from .linear import LinearProvider
            return LinearProvider(config["ticketing"]["linear"])
        # ... etc
    elif category == "test_management":
        # ... similar
    # ... etc

    raise ValueError(f"Unknown category {category!r} or provider {selected!r}")
```

Update tests:
```python
def test_load_provider_dispatches_jira(jira_config):
    provider = load_provider("ticketing", jira_config)
    assert isinstance(provider, JiraProvider)
```

### Effort: 30 min
### Depends on: Steps 2-6 (need implementations to dispatch to)

---

## Step 8 — Dispatch MCP servers [BLOCKING for Step 9]

**Goal:** 4 MCP server scripts. Each loads config, instantiates provider, exposes provider methods as MCP tools. Skills call these.

### Deliverables

```
qa_cortex/servers/ticketing_server.py
qa_cortex/servers/test_mgmt_server.py
qa_cortex/servers/docs_server.py
qa_cortex/servers/chat_server.py
```

Plus `.claude-plugin/plugin.json` updated:

```json
{
  "mcpServers": {
    "qa_cortex_ticketing": {
      "command": "${CLAUDE_PLUGIN_ROOT}/.venv/bin/python",
      "args": ["-m", "qa_cortex.servers.ticketing_server"]
    },
    "qa_cortex_test_mgmt": { ... },
    "qa_cortex_docs": { ... },
    "qa_cortex_chat": { ... }
  }
}
```

### Implementation

```python
# qa_cortex/servers/ticketing_server.py
from mcp.server import Server
from qa_cortex.config import load_config
from qa_cortex.providers import load_provider

config = load_config()
provider = load_provider("ticketing", config)
server = Server("qa-cortex-ticketing")

@server.tool("get_ticket")
def get_ticket(ticket_id: str) -> dict:
    return provider.get_ticket(ticket_id)

@server.tool("create_ticket")
def create_ticket(
    ticket_type: str,
    summary: str,
    description: str,
    custom_fields: dict | None = None,
    approved: bool = False,
) -> dict:
    return provider.create_ticket(ticket_type, summary, description, custom_fields, approved)

# ... etc for all 8 ticketing methods

if __name__ == "__main__":
    server.run()
```

### Effort: 3-4h (4 servers, similar boilerplate, but also testing infra)
### Depends on: Steps 2-7

---

## Step 9 — Skills SKILL.md refactor [BLOCKING for Step 10]

**Goal:** Replace ScaleFinal-specific tool names with abstract `mcp__qa_cortex_*` names.

### Deliverables

Updated:
- `skills/start-ticket-test/SKILL.md`
- `skills/bug-report/SKILL.md`
- `skills/test-planning/SKILL.md`
- `skills/daily-journal/SKILL.md` (likely no changes — already generic)
- `skills/kb-refresh/SKILL.md`

### Conversion rules

```
mcp__plugin_qa-cortex_<ticketing>__get_ticket       → mcp__qa_cortex_ticketing__get_ticket
mcp__plugin_qa-cortex_<ticketing>__search_tickets   → mcp__qa_cortex_ticketing__search_tickets
mcp__plugin_qa-cortex_<test-mgmt>__get_test_case    → mcp__qa_cortex_test_mgmt__get_test_case
... etc
```

Plus: remove banner «⚠ PORTED FROM scalefinal» — skills now first-class qa-cortex artifacts.

### Edge cases

- Skill `start-ticket-test` step 4.5 (recipe lookup) — works as is, references `flows/_index.json` which is universal
- Skill `bug-report` Phase B 1st cohort verbatim ask — works as is
- Skill PARALLEL pre-load batch — works (just rename tool names)

### Effort: 1.5-2h
### Depends on: Step 8 (need new tool names to reference)

---

## Step 10 — Integration tests [VALIDATION GATE]

**Goal:** Verify end-to-end on real test instance.

### Deliverables

```
tests/integration/test_jira_e2e.py
tests/integration/test_testrail_e2e.py
tests/integration/test_full_workflow.py     ← simulates Phase 1 of QA flow
.github/workflows/integration.yml           ← CI for tests (when public)
docs/testing.md                              ← how to run integration tests
```

### Test scope

- Connectivity to test Jira instance (free Atlassian Cloud trial)
- `get_ticket`, `search_tickets` work
- `create_ticket(approved=False)` returns valid preview with idempotency_check
- `create_ticket(approved=True)` actually creates a test ticket
- Cleanup: delete created tickets after test (or use dedicated test project that's wiped)

### Test instance setup

- Jira: free Atlassian Cloud trial, dedicated `QACT` project (qa-cortex test)
- TestRail: free trial or dedicated test project
- Confluence: same Atlassian Cloud as Jira
- Slack: dedicated test workspace

### Effort: 3h
### Depends on: Steps 2-9
### **CRITICAL: This is Phase 2 success gate.** If integration tests pass, Phase 2 done. Else iterate.

---

## Dependency graph

```
Step 1 (Protocol) ✅
   │
   ├──> Step 2 (JiraProvider)
   ├──> Step 3 (TestRailProvider)
   ├──> Step 4 (ConfluenceProvider) ← shares deps with Step 2
   ├──> Step 5 (SlackProvider)
   └──> Step 6 (Config loader)
              │
              └──> Step 7 (load_provider dispatch) ← needs Steps 2-6
                          │
                          └──> Step 8 (MCP servers) ← needs Step 7
                                      │
                                      └──> Step 9 (Skills refactor)
                                                 │
                                                 └──> Step 10 (Integration tests)
                                                            │
                                                            ▼
                                                     Phase 2 DONE
```

### Parallelization opportunities

- **Steps 2, 3, 4, 5, 6** are all independent — can be done in any order or parallel sessions
- **Step 7** is short, do after any provider is ready (just add dispatch as you go)
- **Step 8** can start after Step 7 has 1 dispatch case; add others as providers come online
- **Step 9** independent of provider implementations — can refactor skills using placeholder names ahead of Step 8 if needed

**Critical path: 1 → 2 → 6 → 7 → 8 → 9 → 10** (~12-15h serial work)
**Parallel scenarios save:** ~3-5h if user can do multiple concurrent sessions

---

## Honest "where I anticipate trouble"

1. **`sooperset/mcp-atlassian` Python API surface** (Step 2 dependency)
   - May not be cleanly callable from Python — designed primarily as MCP server
   - Fallback: `atlassian-python-api` direct
   - Decision needed in Step 2 first 30 min

2. **TestRail's `find_cases_by_linked_ticket`** (Step 3)
   - TestRail doesn't have native "linked ticket" field — relies on custom field
   - User must configure which custom field holds the link
   - Could be brittle if user's TestRail is configured differently

3. **Markdown ↔ ADF conversion** (Step 2 Jira)
   - Jira Cloud uses ADF for description; full conversion is complex
   - May need to limit Markdown subset supported (no nested tables, etc.)

4. **MCP server testing** (Step 8)
   - MCP servers are stdio-based; need test fixture to simulate MCP client
   - May need to mock the `mcp.server.Server` class or use real server in subprocess

5. **Integration test infrastructure** (Step 10)
   - Need free test Jira/TestRail/Confluence — easy via Atlassian Cloud trial but expires
   - Slack test workspace setup
   - Cleanup of test data — accidentally committing real test tickets to Jira would be ugly

---

## Decision points needed

### D8 (Step 2 first session): Library choice for Jira
- (a) Wrap `sooperset/mcp-atlassian` Python API if usable
- (b) Use `atlassian-python-api` direct
- Decide after 30-min investigation

### D9 (Step 6): Config validation library
- (a) `pydantic-settings` (rich, common)
- (b) Plain dict + manual checks (lightweight)
- **Recommend (a)** — pydantic ubiquitous in Python ecosystem

### D10 (Step 8): MCP server architecture
- (a) Each server is `python -m qa_cortex.servers.X` script (separate process per category)
- (b) Single MCP server with all categories combined
- **Recommend (a)** — separate processes = isolated failures, matches existing pattern

### D11 (Step 10): Test instance strategy
- (a) Free Atlassian Cloud trial — works, expires after 14 days unless paid
- (b) Use existing scalefinal Jira sandbox — more sustainable but mixes scalefinal data
- (c) Mock-only integration tests — no real backend, less confidence
- Decide closer to Step 10

---

## Validation criteria (per step)

| Step | Done when |
|---|---|
| Step 2 | JiraProvider passes 10+ unit tests, sample script reads/creates ticket on test instance |
| Step 3 | TestRailProvider passes 10+ unit tests |
| Step 4 | ConfluenceProvider passes 5+ unit tests |
| Step 5 | SlackProvider passes 8+ unit tests, can post test message to test channel |
| Step 6 | Config loader parses example TOML, resolves env vars, validates schema |
| Step 7 | `load_provider()` returns correct concrete class for each (category, provider) pair |
| Step 8 | All 4 dispatch servers run as `python -m qa_cortex.servers.X`, expose tools via MCP |
| Step 9 | Skills work end-to-end with new tool names, no broken references |
| Step 10 | E2E test: simulated QA flow on test Jira+TestRail completes — get_ticket → create_ticket(preview) → user approval → create_ticket(approved=True) → ticket exists in Jira |

### Phase 2 DONE = Step 10 passes + tag `v0.1.0-alpha`

---

## Risk register (Phase 2 specific)

| Risk | Likelihood | Impact | Mitigation |
|---|---|---|---|
| `sooperset/mcp-atlassian` doesn't work as Python lib | High | Medium | Step 2 first 30 min investigates; fallback to `atlassian-python-api` |
| Markdown↔ADF conversion brittle | High | Medium | Document supported Markdown subset; provide raw-ADF escape hatch |
| MCP server stdio testing complex | Medium | Medium | Mock at `Server` class level rather than subprocess |
| Integration test instance expires | Medium | Low | Free trial 14 days enough for Phase 2 completion; document setup |
| Provider deps conflict (versions) | Low | High | Use optional extras (pyproject `[jira]`, `[testrail]`, etc.) |
| Skill refactor breaks something subtle | Medium | High | Keep scalefinal-qa-assistant copy untouched; rollback path clear |

---

## Open questions

1. **Should `qa-cortex` package itself be installable via `pip install qa-cortex`?**
   - Pro: standard Python flow
   - Con: requires PyPI publication, more public surface
   - Decision: defer — for now, install via `git clone` only. Can add PyPI publication in v1.0.

2. **How to handle providers user adds via custom fork?**
   - E.g. user has YouTrack — they fork qa-cortex, add `qa_cortex/providers/youtrack.py` themselves
   - For now: documented in `docs/adding-providers.md`. No plugin system in v1.0.

3. **Should integration tests run in CI?**
   - Yes when public — credentials via GitHub Secrets
   - For now (private): manual run

4. **Async vs sync provider methods?**
   - All Protocols defined as sync currently
   - Async would be cleaner for I/O-heavy ops
   - Decision: sync for v1.0, async migration in v2.0 if perf becomes issue

---

## Phase 2 success metrics

When Phase 2 done (Step 10 passes), Yaroslav should be able to:

1. Clone qa-cortex on a fresh machine
2. Run `./scripts/setup.sh` (Phase 3 will add wizard; Phase 2 = manual config)
3. Edit `qa-cortex.config.toml` with Jira/TestRail/Confluence/Slack credentials
4. Run `claude` in the directory
5. Brain works — can fetch tickets, search, draft bug reports

If this works → tag `v0.1.0-alpha`, declare Phase 2 done, move to Phase 3 (DX/docs).

---

## Out of Phase 2 scope (Phase 3+ work)

- Setup wizard CLI (`scripts/setup.sh` interactive)
- Config validator with connectivity tests (`scripts/validate-config.py`)
- Polished README
- INSTALL.md final version
- Documentation deep-dives (`docs/architecture.md`, `docs/trust-tiering.md`, etc.)
- Examples directory with full walkthroughs
- Contributing guide
- Public release decision (Phase 5)

These are all important — but Phase 2 is about making the brain WORK on a default stack. Phase 3 is about making it INSTALL EASILY by anyone.

---

## Estimated calendar

Best case (focused sequential work, no blockers):
- Step 2: 4h → Day 1
- Step 3: 3h → Day 2
- Step 4: 2h → Day 2
- Step 5: 2h → Day 3
- Step 6: 1.5h → Day 3
- Step 7: 0.5h → Day 3
- Step 8: 4h → Day 4
- Step 9: 2h → Day 5
- Step 10: 3h → Day 5-6
- **Total: 22h, ~5-6 working days**

Realistic (with research, debugging, iteration):
- 1.5x multiplier → ~33h, ~2-3 weeks part-time

---

## What's the right next step from here?

Two reasonable paths:

**Path A — Sequential execution (clean, predictable):**
Step 2 → Step 3 → Step 4 → ... → Step 10. Each step's session ~1.5-3h.

**Path B — Parallel investigation first:**
Spend 30 min on each: investigate `sooperset/mcp-atlassian` API, `testrail-api` lib, `slack-sdk`, `pydantic-settings`. Resolve D8-D11 decisions. Then sequential implementation.

**Recommendation:** Path B — but only if multiple short sessions are feasible. If you have one 3h session, just start Step 2 directly.

This roadmap doc is reference. Future sessions can pick any step, read its section, execute. No need to re-establish context.
