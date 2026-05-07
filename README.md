# qa-cortex

> **Senior QA co-engineer for any stack.** Autonomous on routine, gated on critical.
> Trust-tiered, with flow cache + product map architecture.

**Status:** 🚧 `alpha` — actively in development. Skeleton scaffold + design docs are ready. Provider adapters (Phase 2) and full setup flow (Phase 3) coming. **Do not install for production use yet.**

---

## What is this

`qa-cortex` is an open-source scaffold for building a Senior QA co-engineer powered by Claude Code. It's not a passive assistant — it's **extra hands and extra brain** for the QA workflow:

- **Autonomous on routine** — login, navigate, test, log, draft. No approval-per-breath.
- **Gated on critical** — bug filing, status transitions, comms — explicit human approval.
- **Stack-agnostic** — Jira, TestRail, Confluence, Slack out-of-box. Pluggable for Linear, GitHub Issues, Notion, etc.
- **Self-improving** — learns your product as it works (flow cache + product map).

Built around three core architectural patterns:

| Pattern | What it does |
|---|---|
| **Trust tiering** | 3 tiers (auto / implicit / explicit-gate) — calibrates autonomy by action category |
| **Flow cache** | 3-tier amortization (discovery → recipe → Playwright script) — turns repetitive UI work into cheap replays |
| **Product map** | Module-organized KB index — brain queries one map node instead of 8 grep operations |

These three combined: ~77% reduction in per-session token cost vs unaided baseline.

---

## Status & roadmap

This repo is in **Phase 1 — skeleton creation.** What's here right now:

- ✅ Directory structure
- ✅ Design docs (`knowledge_base/design_docs/`)
- ✅ License (MIT)
- ✅ Trust tiering codified in CLAUDE.md (template)
- ✅ Persona files (engineer + orchestrator)
- ✅ KB skeleton templates
- ✅ Generic scripts (journal, refresh-flows-index, refresh-product-map)
- ⏳ **Phase 2:** Provider adapter framework (TicketingProvider, TestMgmtProvider, etc.)
- ⏳ **Phase 2:** Default MCP servers wrapping community providers (Jira, TestRail, Confluence, Slack)
- ⏳ **Phase 3:** Setup wizard + complete docs
- ⏳ **Phase 4:** Validation on 2 real stacks
- ⏳ **Phase 5:** Public release (currently private)

See `knowledge_base/design_docs/qa_cortex_v1.md` for full architecture and phased plan.

---

## Architecture (3 layers)

```
┌─────────────────────────────────────────────────────────────────────┐
│                LAYER 1: qa-cortex CORE (this scaffold)              │
│  CLAUDE.md, skills/, knowledge_base/, flows/, scripts/, templates/  │
│  Owns: WHAT brain does, HOW it reasons, WHEN to gate                │
└─────────────────────────────────────────────────────────────────────┘
                             │
                             ▼
┌─────────────────────────────────────────────────────────────────────┐
│                LAYER 2: PROVIDER ADAPTERS (Phase 2)                 │
│  TicketingProvider, TestManagementProvider, DocumentationProvider,  │
│  ChatProvider — abstract interfaces with concrete implementations   │
│  per backend (Jira, TestRail, Confluence, Slack, etc.)              │
│  Owns: HOW to talk to specific backend                              │
└─────────────────────────────────────────────────────────────────────┘
                             │
                             ▼
┌─────────────────────────────────────────────────────────────────────┐
│                LAYER 3: USER INSTANCE (configured fork)             │
│  Clone qa-cortex → fill .env + qa-cortex.config.toml + KB content   │
│  → working brain on your stack                                      │
└─────────────────────────────────────────────────────────────────────┘
```

---

## Install (when Phase 2 ships)

> ⚠ **Currently in Phase 1.** Install path will look like this once Phase 2 ships. Don't try to follow it yet — adapter layer doesn't exist.

```bash
git clone https://github.com/malerik13/qa-cortex.git
cd qa-cortex
./scripts/setup.sh                   # interactive wizard
# (asks: which providers, tokens, project IDs, etc.)
claude                               # done — brain operational
```

---

## Documentation

- `knowledge_base/design_docs/qa_cortex_v1.md` — full architecture (read this first)
- `knowledge_base/design_docs/flow_cache_v1.md` — flow cache & recipe library
- `knowledge_base/design_docs/product_map_v1.md` — product map & KB knowledge graph
- `INSTALL.md` — install walkthrough (alpha — Phase 2/3 work)
- `HOWTO.md` — daily playbook (alpha)
- `CHANGELOG.md` — version history

---

## License

MIT — see `LICENSE` file.

Copyright (c) 2026 Yaroslav Shcherbinsky.

---

## Contributing

Currently private repo, not accepting external contributions yet. Once public (Phase 5):

- Issue templates for bugs / feature requests
- PR template
- `CONTRIBUTING.md` with code of conduct
- Provider adapter contribution guide (`docs/adding-providers.md`)

---

## Acknowledgements

Built on top of:
- [`Anasss/qa-orchestra`](https://github.com/Anasss/qa-orchestra) — 10 generic QA agents (MIT)
- [`sooperset/mcp-atlassian`](https://github.com/sooperset/mcp-atlassian) — Jira + Confluence MCP (MIT)
- [`bun913/mcp-testrail`](https://github.com/bun913/mcp-testrail) — TestRail MCP
- [`korotovsky/slack-mcp-server`](https://github.com/korotovsky/slack-mcp-server) — Slack MCP
- [Playwright MCP](https://github.com/microsoft/playwright) — browser automation
- Anthropic [Claude Code](https://claude.ai/code) — agent runtime
