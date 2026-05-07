# qa-cortex

> **Senior QA co-engineer for any stack.** Autonomous on routine, gated on critical.
> Trust-tiered, with flow cache + product map architecture.

[![Status](https://img.shields.io/badge/status-alpha-orange)]() [![License](https://img.shields.io/badge/license-MIT-blue)](LICENSE) [![Python](https://img.shields.io/badge/python-3.10+-blue)]() [![Tests](https://img.shields.io/badge/tests-78%20passing-brightgreen)]()

---

## What it is

`qa-cortex` is a Claude Code-powered QA co-engineer. Not a passive assistant — it's **extra hands and extra brain** for the QA workflow:

- 🔁 **Autonomous on routine** — login, navigate, test, log, draft. No approval-per-breath.
- 🛡 **Gated on critical** — bug filing, status transitions, comms — explicit human approval.
- 🔌 **Stack-agnostic** — Jira, TestRail, Confluence, Slack out-of-box. Pluggable for Linear, GitHub, Notion, etc.
- 🧠 **Self-improving** — learns your product as it works (flow cache + product map).

## Three core patterns

| Pattern | What it does | Token saving |
|---|---|---|
| **Trust tiering** | 3 tiers (auto / implicit / explicit-gate) calibrate autonomy by action category | qualitative — enables routine offload |
| **Flow cache** | 3-tier ladder: discovery → recipe → Playwright script — caches repetitive UI work | ~68% on UI-related tokens after warm-up |
| **Product map** | Module-organized KB index — brain queries one map node instead of N grep operations | ~15-25% on KB lookups |

Combined: **~77% reduction** in per-session token cost vs unaided baseline.

---

## Status

**🚧 alpha — Phase 3 complete**

What works:
- ✅ Adapter framework (4 Provider Protocol contracts)
- ✅ Default adapters: **Jira, TestRail, Confluence, Slack** + Playwright (built-in)
- ✅ Config-driven provider dispatch
- ✅ MCP servers exposing provider methods to brain
- ✅ Skills refactored to provider-agnostic tool names
- ✅ Setup wizard CLI (`python scripts/setup.py`)
- ✅ 78 unit tests + integration test scaffold
- ✅ Full documentation: architecture, trust tiering, adding providers, full walkthrough

What's pending:
- ⏳ Real-instance validation — two independent installers (Phase 4)
- ⏳ Linear / GitHub / Notion / Teams adapters (community contributions)
- ⏳ Public release decision (Phase 5)

See [`knowledge_base/design_docs/qa_cortex_v1.md`](knowledge_base/design_docs/qa_cortex_v1.md) for full architecture.
Phase 4 roadmap: [`knowledge_base/design_docs/phase_4_roadmap.md`](knowledge_base/design_docs/phase_4_roadmap.md).

---

## Quick start

**Prerequisites:** macOS or Linux, Python 3.10+, Claude Code installed.

```bash
# 1. Clone
git clone https://github.com/malerik13/qa-cortex.git ~/Documents/qa-cortex
cd ~/Documents/qa-cortex

# 2. Install Python deps
python3 -m venv .venv
source .venv/bin/activate
pip install -e ".[dev]"
pip install atlassian-python-api testrail-api slack-sdk  # adapter deps

# 3. Run setup wizard
python scripts/setup.py
# → answers questions, generates qa-cortex.config.toml + .env

# 4. Verify
pytest tests/                              # 78 unit tests
python scripts/setup.py --check            # config validation

# 5. Run
claude                                     # opens Claude Code
```

In Claude Code, try:
```
> Тестируем PROJ-123
```
(replace with your actual ticket prefix). Brain pulls ticket from configured ticketing provider, builds intake, asks before any write action.

For full walkthrough see [`HOWTO.md`](HOWTO.md).

---

## Architecture

Three-layer separation of concerns:

```
┌──────────────────────────────────────────────────┐
│ LAYER 1: qa-cortex CORE (this scaffold)          │
│  CLAUDE.md · skills/ · knowledge_base/ · flows/  │
│  Trust tiering · personas · workflows            │
└────────────────────────┬─────────────────────────┘
                         │
┌────────────────────────▼─────────────────────────┐
│ LAYER 2: PROVIDER ADAPTERS                       │
│  TicketingProvider, TestManagementProvider,      │
│  DocumentationProvider, ChatProvider             │
│  → JiraProvider, TestRailProvider, …             │
└────────────────────────┬─────────────────────────┘
                         │
┌────────────────────────▼─────────────────────────┐
│ LAYER 3: USER INSTANCE                           │
│  qa-cortex.config.toml + .env + own KB content   │
└──────────────────────────────────────────────────┘
```

See [`docs/architecture.md`](docs/architecture.md) for deep-dive.

---

## Documentation

| Doc | Topic |
|---|---|
| [`HOWTO.md`](HOWTO.md) | Daily playbook — common QA workflows |
| [`INSTALL.md`](INSTALL.md) | Detailed install steps (alternative to wizard) |
| [`docs/architecture.md`](docs/architecture.md) | Layer-by-layer architecture explanation |
| [`docs/trust-tiering.md`](docs/trust-tiering.md) | Trust tiers — what's auto / gated / why |
| [`docs/adding-providers.md`](docs/adding-providers.md) | Add new backend (Linear, Notion, etc.) |
| [`docs/testing.md`](docs/testing.md) | Test strategy + integration test setup |
| [`examples/jira-testrail.md`](examples/jira-testrail.md) | Full walkthrough on default stack |
| [`knowledge_base/design_docs/`](knowledge_base/design_docs/) | Architectural decision records |
| [`knowledge_base/design_docs/phase_4_roadmap.md`](knowledge_base/design_docs/phase_4_roadmap.md) | Phase 4 validation plan — what to do before v1.0.0-rc1 |

---

## Default backends (v1.0 ships)

| Category | Provider | Library | Status |
|---|---|---|---|
| Ticketing | Jira | `atlassian-python-api` | ✅ implemented |
| Test management | TestRail | `testrail-api` | ✅ implemented |
| Documentation | Confluence | `atlassian-python-api` (shared) | ✅ implemented |
| Chat | Slack | `slack-sdk` | ✅ implemented |
| Browser | Playwright | Claude Code built-in MCP | ✅ |

Adding a new backend: see [`docs/adding-providers.md`](docs/adding-providers.md).

---

## License

MIT — see [`LICENSE`](LICENSE).

Copyright (c) 2026 Yaroslav Shcherbinsky.

---

## Acknowledgements

- [Anthropic Claude Code](https://claude.ai/code) — agent runtime
- [`Anasss/qa-orchestra`](https://github.com/Anasss/qa-orchestra) — 10 generic QA agents (MIT)
- [`sooperset/mcp-atlassian`](https://github.com/sooperset/mcp-atlassian) — Jira+Confluence MCP reference
- [`bun913/mcp-testrail`](https://github.com/bun913/mcp-testrail) — TestRail MCP reference
- [`korotovsky/slack-mcp-server`](https://github.com/korotovsky/slack-mcp-server) — Slack MCP reference

## Status

Currently **PRIVATE** during Phase 1-4 development. Public release decision after Phase 4 validation.

External contributions: not yet accepted. See [`CONTRIBUTING.md`](CONTRIBUTING.md) for future plans.
