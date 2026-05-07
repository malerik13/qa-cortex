# Trust Tiering

> The most important architectural concept. Determines what brain does autonomously vs what requires explicit approval.
> Reading time: ~7 min.

---

## TL;DR

Three tiers calibrate brain autonomy by action category:

| Tier | What it covers | Brain behavior |
|---|---|---|
| **1 — AUTO** | Read ops, journal logging, qa-output writes | Just does it |
| **2 — IMPLICIT APPROVAL** | UI clicks, recipe distill, index regeneration | Acts + briefly mentions |
| **3 — EXPLICIT GATE** | Bug filing, status changes, comms, KB edits | Preview → ask → execute on "yes" |

Goal: 70% of QA routine offloaded autonomously, 100% of critical actions gated. **Without this tiering, brain becomes either too cautious (asks every breath) or too eager (auto-files duplicates).**

---

## Why tiering matters

### Naïve approach #1 — paranoid mode

Without tiering, brain defaults to "ask before any side effect":

```
Brain: "Should I read PROJ-123?"
You: yes
Brain: "Should I get linked tickets?"
You: yes
Brain: "Should I get comments?"
You: yes
... 50 questions per session ...
```

Death by paper-cuts. 70% routine offload becomes impossible.

### Naïve approach #2 — auto-everything

Without tiering, brain auto-executes:

```
Brain: [auto-creates duplicate bug]
Brain: [auto-posts to #general about test results]
Brain: [auto-transitions ticket to "Done" without verification]
You: 😱
```

Trust evaporates after first incident.

### The middle path — tiering

Per CLAUDE.md, every action falls into one of three tiers based on:
1. Reversibility — can you undo it?
2. Audience — who sees the side effect?
3. Cost of error — what breaks?

---

## Tier 1 — AUTO (no approval, brain just acts)

**Criteria:** read-only OR self-affecting OR fully reversible.

**Includes:**

```
✓ Read tools — Read, Grep, Glob, LS
✓ MCP read methods:
  - mcp__qa_cortex_ticketing__get_ticket / search_tickets / get_linked_tickets / get_comments
  - mcp__qa_cortex_test_mgmt__get_test_case / search_test_cases / find_cases_by_linked_ticket / get_run
  - mcp__qa_cortex_docs__search / get_page / list_spaces
  - mcp__qa_cortex_chat__list_channels / get_channel_history / get_thread_replies / find_user
✓ journal.sh ops — log, mission, status, standup, save, bug (logs to disk, brain's audit trail)
✓ Read-only Bash — git status, git log, git diff, db-query.sh (read role)
✓ Idempotent regenerators — refresh-flows-index.py, refresh-product-map.py
✓ Playwright read-only — browser_snapshot, browser_evaluate (for queries),
                          browser_console_messages, browser_network_requests,
                          browser_take_screenshot
✓ ToolSearch — discovers deferred MCP tools
✓ Writes to qa-output/* — session artifacts (intake.md, scenarios.md)
✓ AskUserQuestion — asking is fine
```

**Brain behavior:** just does it. No surface text needed unless requested.

**Why safe:** none of these have lasting external side effects. Worst case — wasted tokens.

---

## Tier 2 — IMPLICIT APPROVAL (acts + briefly mentions)

**Criteria:** affects state but reversible OR affects only brain's working memory.

**Includes:**

```
✓ Playwright UI actions — browser_click, browser_type, browser_fill_form,
                           browser_navigate, browser_press_key, browser_wait_for
✓ Edit on flows/*.recipe.md — recipe distillation/refresh
✓ Edit on journal/dev/<DATE>.md — meta-build chronicle (brain may format)
✓ Auto-generated index regeneration:
  - flows/_index.json
  - knowledge_base/product_map.json
  - knowledge_base/bugs.json
```

**Brain behavior:** does it, mentions briefly:
```
> Saved intake to qa-output/intake.md
> Distilled recipe: flows/auth/login-default.recipe.md (verified path captured)
> Regenerated product_map.json (12 modules indexed)
```

**Why this tier:** affects browser state or brain's own memory. User sees what happened but doesn't need to approve each step.

---

## Tier 3 — EXPLICIT GATE (preview → ask → execute)

**Criteria:** external side effect, irreversible, or affects user's authentic record.

**Includes:**

### MCP write methods (all)

```
mcp__qa_cortex_ticketing__create_ticket     ← creates ticket on Jira/Linear/etc.
mcp__qa_cortex_ticketing__add_comment       ← adds comment
mcp__qa_cortex_ticketing__transition_ticket ← changes status
mcp__qa_cortex_ticketing__update_ticket     ← updates fields
mcp__qa_cortex_test_mgmt__create_test_case  ← creates TestRail case
mcp__qa_cortex_test_mgmt__add_result        ← records test result
mcp__qa_cortex_chat__post_message           ← posts to Slack
mcp__qa_cortex_chat__add_reaction           ← adds reaction (still external comms)
```

All of these accept `approved: bool = False`. Brain MUST call with `approved=False` first to get preview, then with `approved=True` after explicit user "yes".

### KB edits (hand-curated)

```
✗ knowledge_base/qa_persona.md, orchestrator_persona.md, qa_workflow.md
✗ knowledge_base/insights.md (your accumulated lessons — never auto-add)
✗ knowledge_base/business_rules.md
✗ knowledge_base/ui_flows.md
✗ knowledge_base/glossary.md
✗ knowledge_base/db_naming_map.md
✗ knowledge_base/_module_taxonomy.json
✗ knowledge_base/qa_brain_master_plan.md
✗ knowledge_base/design_docs/*.md
```

### Brain code

```
✗ CLAUDE.md (master prompt — every change requires user-approved diff)
✗ skills/*/SKILL.md
✗ scripts/* (executable code)
✗ qa_cortex/*.py
✗ .claude-plugin/plugin.json
✗ .gitignore
```

### Authentic user record

```
✗ journal/<DATE>.md — your QA standup. Brain prompts via journal.sh log
                       commands but content originates with you.
```

### Other

```
✗ git commit, git tag, git push (versioning is your signal)
✗ Production / live customer data
✗ Irreversible — rm -rf, git push --force, schema migration, destructive ops
✗ Anything tagged "blocker" — you decide severity
```

**Brain behavior:**
1. Build preview (`approved=False` call → returns dict with `preview: True`)
2. Surface to you with relevant context (idempotency check, similar tickets, env reasoning)
3. **STOP** and wait for "yes" / "да create" / "yes create"
4. On approval: re-call with `approved=True`
5. Surface result (URL, ID, etc.)

**Forbidden:** calling `approved=True` on first invocation. Tested at Protocol level — every write method has a `test_preview_does_not_post` test.

---

## When in doubt

**Default to Tier 3** if action category not obvious. False-positive ask is cheap; false-negative (auto-acting on Tier 3) erodes trust.

Brain should explicitly say:
> «Это похоже на Tier 3 (irreversible / external comms / user's authentic record). Покажу preview перед действием.»

---

## Concrete examples

### Example 1: Test a ticket (mostly Tier 1)

```
User: Тестируем PROJ-123

Brain: [Tier 1 — auto]
       1. Read knowledge_base/qa_persona.md (engineer persona load)
       2. journal.sh mission "test PROJ-123"
       3. PARALLEL: get_ticket / get_linked / get_comments / find_cases_by_linked_ticket
       4. Write qa-output/intake.md
       5. Cockpit summary

Brain: 🎯 Cockpit — PROJ-123 — Awaiting Phase 2 approval

User: Phase 2 go

Brain: [Tier 2 — UI execution, mentioned briefly]
       Navigating to staging login... clicked submit... dashboard verified.
       Recipe replay used: flows/auth/login-default.recipe.md

Brain: All scenarios passed.
```

Zero Tier 3 actions in this flow. Test passes, brain logs verdict.

### Example 2: File a bug (Tier 3 enforcement)

```
User: Оформи баг про 500 на edit profile

Brain: [Phase A — gather facts, all Tier 1 reads]
       Found parent: PROJ-100 (Edit Profile feature)

Brain: [Phase B — verbatim ask, Tier 3 prep]
       Этот баг — 1st cohort? Критерии (3 yes = yes):
       (1) главный AC — Edit Profile is core feature ✓
       (2) happy path — yes, user clicked Edit Profile ✓
       (3) 60-sec smoke — yes, dev would have caught ✓
       [yes / no / unsure]

User: yes

Brain: [Phase C — preview, approved=False, Tier 3 gate]
       Calling create_ticket(ticket_type="Bug", summary="...", approved=False)

       Preview:
       - Type: Bug
       - Title: "500 error on Edit Profile click"
       - Severity: Major (walked algorithm: domain=user-data, scope=all-users, impact=blocking)
       - Idempotency: 2 similar OPEN tickets found:
           PROJ-150: "Edit Profile loads slow" (different — perf not error)
           PROJ-201: "500 on profile save" (similar — review)

       Ready to create? [yes / edit / cancel]

User: yes

Brain: [Phase D — submit, approved=True]
       Created PROJ-456: https://your-org.atlassian.net/browse/PROJ-456

Brain: [Phase E — Tier 1 journal log, NON-NEGOTIABLE]
       journal.sh bug PROJ-456 "500 on Edit Profile" staging "regression,1st-cohort"
       ✅ Logged.
```

### Example 3: Tier violation example (DON'T do)

```
User: Закрой PROJ-200

Brain: [Tier 3 violation — auto-transitioned without preview]
       transition_ticket("PROJ-200", "Done", approved=True)
       Done.

User: Что?? А если я хотел сначала проверить?
```

Brain should have:
```
Brain: [Tier 3 prep]
       transition_ticket("PROJ-200", "Done", approved=False) — preview:
       Current status: In Review
       New status: Done
       Available transitions verified: yes

       Confirm transition? [yes / cancel]
```

---

## Tier ambiguity — surface, don't decide

If action category not obvious, brain should ASK before acting:

```
Brain: I'd consider this Tier 3 because: <reasoning>.
       But I'm not 100% — should I proceed with preview-then-ask, or do you
       consider this routine enough to auto-act?
```

User clarifies. Tier policy can evolve based on user preference.

---

## Verifying compliance

Tests guard the contract:

```bash
pytest tests/providers/test_protocols.py::TestApprovalGatePattern -v
```

This test fails if any write method on any Protocol doesn't have `approved: bool = False` default. **Cannot regress safety pattern.**

---

## Customizing tiers

If you need a custom tier policy (e.g. you trust brain to auto-comment on tickets in certain projects), edit `CLAUDE.md` "Trust tiering" section.

⚠ **Don't loosen Tier 3 lightly.** It's the load-bearing safety pattern. Loosening creates a class of incidents that are hard to recover from.

---

## See also

- `CLAUDE.md` — full operative section with anti-patterns
- `docs/architecture.md` — where tiering fits in the stack
- `qa_cortex/providers/base.py` — Protocol contracts (write methods all have `approved`)
- `tests/providers/test_protocols.py::TestApprovalGatePattern` — automated check
