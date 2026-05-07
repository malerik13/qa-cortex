---
name: test-planning
description: Build test scenarios from a YouTrack ticket's AC. Fetches AC + existing <test-mgmt> cases via our MCPs, generates scenario list (4 categories — Happy/Negative/Boundary/Edge), surfaces top risks. Triggers when the user says "составь тест-план для <TICKET>-X", "what should I test for <TICKET>-X", "разбери AC <TICKET>-X", "напиши сценарии для <TICKET>-X", or names a ticket and asks specifically for test cases (NOT full lifecycle — for full pipeline use start-ticket-test).
---

You produce test scenarios for a single ticket. **Lighter than `start-ticket-test`** — no Phase 1.5, no full Cockpit, focus on scenario design only.

## When this vs start-ticket-test

| Situation | Skill |
|---|---|
| Full QA lifecycle (Phase 0-6) including scenario design | `start-ticket-test` |
| ONLY scenarios — no QA subtask, no Cockpit, no journal mission setup | THIS skill |
| Mid-execution: refresh scenarios for one specific AC | THIS skill |

If trigger ambiguous → ask: «полный test cycle (start-ticket-test) или только сценарии (test-planning)?»

---

## Step 1 — Identify ticket

If <TICKET>-ID in message → use it. Else STOP, ask: «Какой тикет? Например <TICKET>-12345».

---

## Step 2 — Fetch AC + <test-mgmt> (PARALLEL batch)

```
PARALLEL tool calls in one message:
- mcp__qa_cortex_ticketing__get_ticket(ticket_id="<TICKET>-XXXXX")
- mcp__qa_cortex_ticketing__get_comments(ticket_id="<TICKET>-XXXXX", max_results=20)
- mcp__qa_cortex_test_mgmt__find_cases_by_linked_ticket(
    issue_id="<TICKET>-XXXXX",
    include_scenario=true     ← MANDATORY (boolean)
  )
```

Extract from results:
- AC (verbatim, numbered)
- Custom fields (Type, Release Version, Subsystem)
- Linked tickets (parent Epic + sibling [BE]/[FE]/[CR])
- PO clarifications from comments
- Existing <test-mgmt> cases with scenario steps

**Conditional KB reads** (only if AC area matches):
- `knowledge_base/insights.md` — if topic touches accumulated lessons (2FA → Insight 5, Email counter → Insight 12, etc.)
- `knowledge_base/business_rules.md` — if 2FA / hierarchy / export / role keywords
- `knowledge_base/db_naming_map.md` — if AC touches data layer

---

## Step 3 — Generate scenarios (inline, brain-driven)

Build a structured list across 4 categories:

```
## Happy path
1. <Primary AC compliance — verbatim AC #1>
2. ...

## Negative
1. <Invalid input X — expected error Y>
2. <Missing permission — expected denial>
3. ...

## Boundary
1. <Empty state>
2. <Max values / overflow>
3. <Race condition / concurrency if applicable>

## Edge
1. <Unusual combo of state X + role Y>
2. ...
```

**Rules:**
- Don't duplicate existing <test-mgmt> coverage (Step 2 results) — focus on **gaps**
- Don't invent AC — if AC missing, mark as «AC not provided — ask PO»
- Cross-reference `insights.md` if relevant area (cite Insight # in scenario)

**Optional delegation** (when scenario design is non-trivial — multi-role flows, complex business logic):

```
Task(subagent_type="qa-orchestra:test-scenario-designer", prompt="<pass AC + existing coverage as context>")
```

Agent writes to `qa-output/test-scenarios.md`. Read result, present to Yaroslav. Default: brain generates inline (faster, qa-orchestra delegation only when complexity justifies).

---

## Step 4 — Save artefact + present

Write `qa-output/test-scenarios.md` (regardless of inline vs delegated):

```markdown
# <TICKET>-XXXXX — Test scenarios

## Coverage matrix
| AC # | Existing <test-mgmt> | New scenarios needed |
|------|-----------------|----------------------|
| 1    | case-2544       | (covered)            |
| 2    | (none)          | Happy + Negative     |
| ...  | ...             | ...                  |

## Scenarios
[full list, structured per Step 3]

## Open questions to PO
- [list]

## Risk-prioritised top 3
1. <Most likely fail / highest blast radius>
2. ...
3. ...
```

Surface to Yaroslav (don't re-summarize whole file):

```
📋 Test scenarios — <TICKET>-XXXXX

Coverage: N AC → M new scenarios (K existing <test-mgmt> cases reused)
Top risks: [3 prioritised]
PO open questions: [list]
File: qa-output/test-scenarios.md
```

---

## Step 5 — Offer next step

```
Дальше:
- «Phase 2 / browser-validator» → invoke Task(qa-orchestra:browser-validator) для автоматического прогона
- «создай <test-mgmt> cases» → invoke Task(qa-orchestra:automation-writer) для генерации тестов + allure:create_test_case
- «manually» → guidance for manual run
- «сохрани» → save journal session, конец
```

Wait for explicit choice. Don't auto-proceed.

---

## Hard rules

1. **Don't invent AC.** Missing → list as «ask PO», don't fabricate.
2. **Always end with explicit next-step offer** — don't dangle.
3. **Don't duplicate existing <test-mgmt> coverage** — Step 2 result is anti-duplication input.
4. **`include_scenario=true` mandatory** — boolean true, not string.
5. **Default = brain-inline** for simple AC. **Delegate to qa-orchestra:test-scenario-designer** only when complexity justifies (multi-role, complex state machine, race conditions).

---

## Failure modes

- **AC missing in ticket** → mark «AC not provided — ask PO», save partial artefact.
- **<test-mgmt> index stale** (no cases found but comments mention them) → suggest `python3 scripts/update-allure-index.py`, proceed without <test-mgmt> context.
- **YouTrack MCP unavailable** → ask Yaroslav to paste AC, proceed.
- **`qa-orchestra:test-scenario-designer` not loaded** when delegation attempted → fall back to brain-inline generation.
