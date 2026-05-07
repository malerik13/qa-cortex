# Architecture

> Layer-by-layer breakdown of qa-cortex internals.
> Reading time: ~10 min.

---

## Three-layer separation

```
┌─────────────────────────────────────────────────────────────────────┐
│ LAYER 1 — qa-cortex CORE (this scaffold)                            │
│   What brain does, how it reasons, when to gate                     │
│                                                                     │
│   • CLAUDE.md (always-loaded master prompt)                         │
│   • knowledge_base/                                                 │
│       ├── qa_persona.md, orchestrator_persona.md, qa_workflow.md    │
│       ├── design_docs/ (architectural decisions)                    │
│       ├── insights.md, business_rules.md, glossary.md (KB content)  │
│       └── product_map.json (auto-generated module index)            │
│   • skills/ (5 skills with checkpoint-based workflow definitions)   │
│   • flows/ (recipe library — cached UI flows)                       │
│   • scripts/ (journal.sh, refresh-*.py)                             │
└──────────────────────────────────┬──────────────────────────────────┘
                                   │ skills call abstract tool names:
                                   │ mcp__qa_cortex_<category>__<method>
                                   ▼
┌─────────────────────────────────────────────────────────────────────┐
│ LAYER 2 — PROVIDER ADAPTERS                                         │
│   How brain talks to specific backends                              │
│                                                                     │
│   • qa_cortex/providers/                                            │
│       ├── base.py (4 Protocol contracts)                            │
│       ├── jira.py, testrail.py, confluence.py, slack.py             │
│       └── _normalizers.py (shape conversion utilities)              │
│   • qa_cortex/servers/ (4 dispatch MCP servers)                     │
│       ├── ticketing_server.py                                       │
│       ├── test_mgmt_server.py                                       │
│       ├── docs_server.py                                            │
│       └── chat_server.py                                            │
│   • qa_cortex/config/ (TOML loader + env var resolution)            │
└──────────────────────────────────┬──────────────────────────────────┘
                                   │ config selects provider
                                   ▼
┌─────────────────────────────────────────────────────────────────────┐
│ LAYER 3 — USER INSTANCE (your customized fork)                      │
│   Your stack, your secrets, your KB                                 │
│                                                                     │
│   • qa-cortex.config.toml (which providers, which URLs)             │
│   • .env (tokens — gitignored)                                      │
│   • knowledge_base/ (your business_rules, ui_flows, insights)       │
│   • flows/<area>/*.recipe.md (your accumulated flows)               │
│   • journal/<DATE>.md (your QA standup history)                     │
└─────────────────────────────────────────────────────────────────────┘
```

---

## Layer 1: Core scaffold

### CLAUDE.md — always-loaded master prompt

Defines:
- **Persona routing** (engineer / orchestrator) by trigger phrase
- **Trust tiering** (3 tiers: auto / implicit / explicit-gate)
- **Anti-patterns** (don't invent AC, don't skip 1st cohort verbatim ask, etc.)
- **Capability declaration** (what brain does itself vs delegates)
- **Lazy-load reference table** (which file when needed)
- **Response closing rules** (recommendation block + AskUserQuestion)

Target size: ~5-7K tokens. Larger = expensive on every chat turn.

### Knowledge base

| File | Content | Audience |
|---|---|---|
| `qa_persona.md` | Engineer mode rules, severity rubric, daily rules, anti-patterns | Brain (lazy-loaded on TRD trigger) |
| `orchestrator_persona.md` | Day-management, ISTQB foundation, model recommendations | Brain (lazy-loaded on morning trigger) |
| `qa_workflow.md` | 6-phase ticket lifecycle | Brain |
| `business_rules.md` | Product-specific domain rules | Brain (conditional load) |
| `insights.md` | Accumulated lessons | Brain (conditional load) |
| `glossary.md` | Terminology UI ↔ DB ↔ customer | Brain |
| `db_naming_map.md` | UI labels ↔ DB tables | Brain |
| `ui_flows.md` | Verified UI navigation paths | Brain (anti-hallucination) |
| `product_map.json` | Auto-generated module index aggregating all KB | Brain (lazy-loaded module slice) |
| `design_docs/` | Architectural decision records | Both brain and humans |

### Skills

5 skills, each defined in `skills/<name>/SKILL.md` with frontmatter `description:` for trigger detection:

| Skill | Triggers |
|---|---|
| `start-ticket-test` | "Тестируем PROJ-X", URL paste, "протестировать тикет" |
| `bug-report` | "оформи баг", "log a bug", broken behavior description |
| `test-planning` | "составь тест-план", "разбери AC" |
| `daily-journal` | "save", "стендап", "тестирование завершено" |
| `kb-refresh` | "обнови индекс", "rebuild knowledge base" |

Each SKILL.md is structured with:
- Numbered steps
- HARD CHECKPOINTS where brain must stop (e.g. Phase 1.5 idempotency call)
- Tool call templates with abstract names
- Failure modes documented

Skills don't reference specific provider implementations — they call `mcp__qa_cortex_<category>__<method>` which dispatches at runtime.

### Flows (recipe library)

3-tier amortization ladder:

```
Tier 1 — DISCOVERY (~30K tokens) — first time on a UI flow
  ↓ (auto-distill at end of successful Phase 3)
Tier 2 — RECIPE REPLAY (~1K tokens) — cached path
  ↓ (after N successful uses + manual approval)
Tier 3 — PLAYWRIGHT (~200 tokens) — compiled .spec.ts
```

Recipes live in `flows/<area>/<flow-id>.recipe.md` with YAML frontmatter (selectors, last_verified, traps, token estimates).

See [`knowledge_base/design_docs/flow_cache_v1.md`](../knowledge_base/design_docs/flow_cache_v1.md) for full design.

### Scripts

| Script | Purpose |
|---|---|
| `journal.sh` | Daily journal management — `mission`, `log`, `bug`, `save`, `standup`, `dev-log` |
| `refresh-flows-index.py` | Rebuilds `flows/_index.json` from recipe frontmatter |
| `refresh-product-map.py` | Crawls KB sources, generates `knowledge_base/product_map.json` |
| `setup.py` | Interactive setup wizard |

---

## Layer 2: Provider adapters

### Protocol contracts (`qa_cortex/providers/base.py`)

4 abstract Protocol classes:

| Protocol | Methods | Write methods (with `approved` gate) |
|---|---|---|
| `TicketingProvider` | get/search/get_linked/get_comments + writes | create_ticket, add_comment, transition_ticket, update_ticket |
| `TestManagementProvider` | get/search/find_by_ticket/get_run + writes | create_test_case, add_result |
| `DocumentationProvider` | search, get_page, list_spaces | (read-only) |
| `ChatProvider` | list/history/replies/find_user + writes | post_message, add_reaction |

**Two-step approval gate** is load-bearing: every write method accepts `approved: bool = False`. When False, returns preview. When True, executes. Brain (and tests) verify this contract.

**Canonical schemas** — every method returns normalized dict shape, not raw provider JSON. Adapters convert at their boundary.

### Concrete adapters

Each adapter wraps a third-party Python library:

| Adapter | Library | License |
|---|---|---|
| `JiraProvider` | `atlassian-python-api` | Apache 2.0 |
| `TestRailProvider` | `testrail-api` | Apache 2.0 |
| `ConfluenceProvider` | `atlassian-python-api` (shared) | Apache 2.0 |
| `SlackProvider` | `slack-sdk` (official) | MIT |

Adapters handle:
- Authentication
- Pagination
- Error normalization (HTTP 404 → `LookupError`, etc.)
- Schema conversion (provider native → canonical)

### Dispatch MCP servers

`qa_cortex/servers/<category>_server.py` — one server per provider category. Each:

1. Loads `qa-cortex.config.toml` at startup
2. Calls `load_provider(category, config)` to get configured adapter
3. Exposes adapter methods as MCP tools via `FastMCP`
4. Wraps each call with `safe_invoke` to normalize errors to dict responses

`.claude-plugin/plugin.json` registers all 4 servers under `mcpServers`. Claude Code spawns them as subprocesses on session start.

Skills call e.g. `mcp__qa_cortex_ticketing__get_ticket("PROJ-123")` → ticketing server receives → calls `provider.get_ticket("PROJ-123")` → returns canonical dict → brain uses.

### Config loader

`qa_cortex/config/loader.py`:
- Reads TOML (Python 3.11+ stdlib `tomllib`)
- Resolves `${VAR}` env var substitutions
- Validates required sections + provider value whitelist
- Searches default paths: `./qa-cortex.config.toml`, `./.qa-cortex/config.toml`, `~/.config/qa-cortex/config.toml`

Pure stdlib — no `pydantic-settings` dep (D9 decision: minimal surface).

---

## Layer 3: User instance

### Per-instance files

| File | Purpose | Gitignored? |
|---|---|---|
| `qa-cortex.config.toml` | Provider selection + connection details | ❌ commit (with `${VAR}` placeholders) |
| `.env` | Tokens, secrets | ✅ never commit |
| `knowledge_base/business_rules.md` | Your domain rules | Commit |
| `knowledge_base/insights.md` | Your accumulated lessons | Commit |
| `knowledge_base/_module_taxonomy.json` | Your product modules | Commit |
| `flows/<area>/*.recipe.md` | Your discovered flows | Commit |
| `journal/<DATE>.md` | QA standup history | Commit (your own decision) |
| `journal/_active.md` | Per-session scratchpad | ✅ never commit |
| `qa-output/` | Session artifacts (intake, scenarios) | Commit selectively |

### Customization seam

When you fork qa-cortex for your stack:

1. **Don't touch** `qa_cortex/` (Python code), `skills/` (workflow definitions), `CLAUDE.md` core sections — those are upstream
2. **Customize** KB content, taxonomy, flows, journal — those are yours
3. **Configure** providers via `qa-cortex.config.toml`

To absorb upstream changes:
```bash
git fetch origin
git merge origin/main           # might need conflict resolution in your KB
```

---

## Why this architecture

### Why three layers?

- **Layer 1 (core)** — universal. Same across all instances. Updates flow downstream.
- **Layer 2 (adapters)** — pluggable. Choose backends per stack.
- **Layer 3 (instance)** — yours. Domain content + secrets + accumulated knowledge.

If we collapsed layers, every stack would need its own fork of skills/CLAUDE.md. With three layers, one fork ships customization without rebuild.

### Why Protocol-based contracts?

- **Strong typing** — `runtime_checkable` Protocols, `mypy` validation
- **Multiple implementations** — Jira / Linear / GitHub all satisfy `TicketingProvider`, brain doesn't care which
- **Testable** — mock the Protocol, run skill logic in isolation

### Why dispatch MCP servers vs direct in skills?

- **Tool name stability** — skills reference `mcp__qa_cortex_ticketing__get_ticket` regardless of backend
- **Process isolation** — adapter crash doesn't take down brain
- **Lazy import** — only configured providers load (don't import Linear lib if user picked Jira)

### Why two-step approval gate?

Single most important safety feature. Brain has been observed to:
- Auto-create duplicate tickets
- Post to Slack channels accidentally
- Transition tickets to wrong status

`approved: bool = False` default prevents all of this. Brain MUST surface preview, get explicit "yes", then call again with `approved=True`. Tested at Protocol level — cannot regress.

---

## Where to learn more

- **Trust tiering** — `docs/trust-tiering.md`
- **Adding a new provider** — `docs/adding-providers.md`
- **Flow cache** — `knowledge_base/design_docs/flow_cache_v1.md`
- **Product map** — `knowledge_base/design_docs/product_map_v1.md`
- **Phase 2 roadmap** — `knowledge_base/design_docs/phase_2_roadmap.md` (now closed)
- **Original product design** — `knowledge_base/design_docs/qa_cortex_v1.md`
