# qa-cortex Skills

Skills are activated by user phrases (defined in each SKILL.md `description:` frontmatter) and orchestrate complex QA workflows by combining provider tools.

All provider tool calls use abstract names that dispatch to the configured backend at runtime:

```
mcp__qa_cortex_ticketing__<method>      → JiraProvider / LinearProvider / etc.
mcp__qa_cortex_test_mgmt__<method>      → TestRailProvider / AllureProvider / etc.
mcp__qa_cortex_docs__<method>           → ConfluenceProvider / NotionProvider / etc.
mcp__qa_cortex_chat__<method>           → SlackProvider / TeamsProvider / etc.
mcp__playwright__browser_*              → Playwright (built-in Claude Code MCP)
```

Configuration in `qa-cortex.config.toml` selects which concrete provider answers
each category. Skills don't care which.

## Skills in this directory

| Skill | Purpose | Triggers |
|---|---|---|
| `start-ticket-test/` | Full QA lifecycle on a ticket (Phases 1-6) | "Тестируем TICKET-X", URL paste |
| `bug-report/` | File a bug with two-step approval gate | "оформи баг", "log a bug" |
| `test-planning/` | Generate test scenarios from AC | "составь тест-план", "разбери AC" |
| `daily-journal/` | Manage QA standup journal | "save", "стендап", "тестирование завершено" |
| `kb-refresh/` | Refresh KB index from ticketing system | "обнови индекс", "refresh the KB" |

## Trust tiering

Skills follow CLAUDE.md trust tiering:
- **Tier 1 (auto)**: read operations, journal logging, qa-output writes
- **Tier 2 (implicit)**: Playwright UI actions, recipe distillation, index regeneration
- **Tier 3 (explicit gate)**: ticket creation, status changes, comments, Slack posts —
  always preview → ask → write
