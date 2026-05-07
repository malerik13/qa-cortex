# Changelog

All notable changes to qa-cortex will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

Pre-v1.0 releases are alpha — not for production use.

---

## [Unreleased]

### Planned (Phase 2 — Adapter framework)
- Abstract provider interfaces (`TicketingProvider`, `TestManagementProvider`, `DocumentationProvider`, `ChatProvider`)
- Default MCP server wrappers: Jira, TestRail, Confluence, Slack
- Skills refactored to provider-agnostic tool names
- Setup wizard CLI

### Planned (Phase 3 — Documentation + DX)
- Polished README + INSTALL + HOWTO
- Architecture documentation
- Trust tiering deep-dive doc
- Flow cache concept doc
- Adding-providers contribution guide

### Planned (Phase 4 — Validation)
- 2 real installs on different stacks
- Iteration based on friction points

### Planned (Phase 5 — Public release, optional)
- Public visibility
- Issue/PR templates
- Code of conduct

---

## [0.0.1-alpha] — 2026-05-07

### Added — Phase 1 skeleton

- Repo created: github.com/malerik13/qa-cortex (PRIVATE)
- LICENSE: MIT
- README.md with status & vision
- Directory structure (knowledge_base, skills, flows, scripts, templates, mcp, docs)
- Design docs ported from scalefinal-qa-assistant origin:
  - `knowledge_base/design_docs/qa_cortex_v1.md` — this product's architecture
  - `knowledge_base/design_docs/flow_cache_v1.md` — flow cache concept
  - `knowledge_base/design_docs/product_map_v1.md` — product map concept
- CLAUDE.md template (cleaned of ScaleFinal-specific references)
- Persona files: `qa_persona.md`, `orchestrator_persona.md`, `qa_workflow.md`
- KB skeleton: `_module_taxonomy.json`, `business_rules.md`, `insights.md`, `glossary.md`, `db_naming_map.md`, `ui_flows.md`
- Flow cache skeleton: `flows/_index.json`, `flows/_traps.json`, `flows/README.md`
- Generic scripts: `journal.sh`, `refresh-flows-index.py`, `refresh-product-map.py`
- Templates directory for instance customization
- Plugin manifest: `.claude-plugin/plugin.json`

### Architecture decisions captured

- Naming: qa-cortex
- Repo strategy: Two separate repos (qa-cortex public scaffold + scalefinal private instance)
- License: MIT
- Initial visibility: PRIVATE (until Phase 4 validation)
- Default backends: Jira, TestRail, Confluence, Slack, Playwright
- Phased rollout: 5 phases over 4-8 weeks

### Status notes

- Phase 1 deliverable: structural skeleton, no working brain yet
- Provider adapters pending (Phase 2)
- Setup wizard pending (Phase 3)
- Skills SKILL.md files contain ScaleFinal MCP tool references — to be refactored Phase 2 with abstract `mcp__qa_cortex_*` names
