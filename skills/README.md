# qa-cortex Skills

> ⚠ **Phase 2 refactor pending.** Skills currently reference instance-specific MCP tool names (e.g. `mcp__plugin_qa-cortex_<ticketing>__get_ticket`).
>
> **Phase 2 will replace these with abstract names** like `mcp__qa_cortex_ticketing__get_ticket` that dispatch to the configured provider (Jira / Linear / GitHub / etc.) at runtime.
>
> See `knowledge_base/design_docs/qa_cortex_v1.md` §7 for adapter architecture details.

## Skills in this directory

| Skill | Purpose | Phase 2 changes |
|---|---|---|
| `start-ticket-test/` | Full QA lifecycle on a ticket (Phases 1-6) | Provider-agnostic tool names |
| `bug-report/` | File a bug with two-step approval | Provider-agnostic create_ticket call |
| `test-planning/` | Generate test scenarios from AC | Provider-agnostic get_ticket |
| `daily-journal/` | Manage QA standup journal | No changes (already generic) |
| `kb-refresh/` | Refresh KB index from ticketing system | Provider-agnostic search |

## Trigger patterns (current)

Each `SKILL.md` has frontmatter `description:` field that defines triggers. These remain stack-specific until Phase 2 generalizes them.
