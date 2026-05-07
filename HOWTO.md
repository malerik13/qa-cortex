# qa-cortex — Daily Playbook

> Common QA workflows, what to type, what brain does, what's auto vs gated.

Brain operates by **trust tiering** (see `docs/trust-tiering.md`):
- **Tier 1 (auto)** — read ops, journal, brain doesn't ask
- **Tier 2 (implicit)** — UI clicks, recipe distillation — brain mentions briefly
- **Tier 3 (gate)** — bug filing, status changes, comms — brain shows preview, asks "yes"

---

## Morning routine — start of day

```
доброе утро
```

Brain:
- Loads orchestrator persona
- Reads journal status
- Outputs morning briefing: yesterday's progress + today's mission

If empty journal:
```
> доброе утро
> Какая миссия сегодня?
```

Reply with focus area: "Regression for v3.0 release" or "Sprint 12 testing".

---

## Test a ticket — full lifecycle

```
Тестируем PROJ-123
```

Or paste URL:

```
https://your-org.atlassian.net/browse/PROJ-123
```

Brain executes Phase 1:
1. Loads engineer persona
2. Sets journal mission
3. **PARALLEL pre-load batch** (4 MCP calls in single message):
   - `mcp__qa_cortex_ticketing__get_ticket`
   - `mcp__qa_cortex_ticketing__get_linked_tickets`
   - `mcp__qa_cortex_ticketing__get_comments`
   - `mcp__qa_cortex_test_mgmt__find_cases_by_linked_ticket`
4. Conditional KB reads (insights, business_rules) if relevant
5. Recipe lookup in `flows/_index.json`
6. Bugs index grep for defect cluster
7. Writes `qa-output/intake.md`
8. **Phase 1.5** — QA subtask idempotency check (if ticket type = User Story)
9. Outputs Cockpit § 0-5 summary
10. **STOPS** — waits for your "Phase 2 go" approval

You review, then approve or push back.

---

## File a bug

```
Оформи баг: при клике на Edit Profile появляется 500 на staging
```

Or just describe behavior — brain detects bug-filing intent.

Brain executes 5 phases:

**A. Prepare draft** — gather facts (env, steps, expected, actual, evidence)

**B. Classify (HARD CHECKPOINT)**:
- B1: **1st cohort verbatim ask** — brain surfaces:
  ```
  Этот баг — `1st cohort` (очевидное нарушение главного AC,
  dev не сделал smoke перед stage)? [yes / no / unsure]
  ```
- B2: Severity walk (qa_persona §11 algorithm) — not gut-pick

**C. Preview** — `mcp__qa_cortex_ticketing__create_ticket(approved=False)`:
- Returns idempotency check (similar OPEN tickets)
- Returns full payload preview

**D. Approve + submit**:
- You say "yes" / "да create"
- Brain calls with `approved=True`
- Returns new ticket ID + URL

**E. Journal log** (NON-NEGOTIABLE):
```
journal.sh bug PROJ-456 "Edit profile 500 error" staging "regression,1st-cohort"
```

Without this, morning standup misses evidence chain.

---

## Build test plan (without full lifecycle)

```
Составь тест-план для PROJ-123
```

Brain:
1. Fetches ticket via MCP
2. Generates 4-category scenarios (Happy / Negative / Boundary / Edge)
3. Cross-references existing test cases (don't duplicate)
4. Writes `qa-output/test-scenarios.md`
5. Surfaces top-3 risk-prioritised scenarios + open questions to PO
6. Offers next steps: browser-validator / generate Allure cases / manual / save

---

## Save journal session

```
save
```

Or `сохрани`, `тестирование завершено`. Brain flushes `_active.md` to today's daily file.

---

## Standup

```
стендап
```

Brain runs `journal.sh standup`, polishes output for chat, surfaces:
- Yesterday: what was tested / filed / closed
- Today: planned mission
- Blockers / open questions

---

## Test outcome verdicts (non-negotiable journal log per CLAUDE.md anti-pattern #4)

After any test session, before save:

```
journal.sh log "PROJ-123 retest staging: passed (5 AC verified, 12 scenarios green)"
journal.sh log "PROJ-456 retest release: not reproducible (evidence: qa-output/...)"
journal.sh log "PROJ-789 retest staging: blocked — 2FA Telegram bot down"
journal.sh log "PROJ-100 retest staging: regression-found (filed PROJ-NEW)"
journal.sh log "PROJ-200 retest staging: by-design (cited AC #3)"
```

Brain enforces this — won't let you `save` without verdict logged.

---

## Browser token economy patterns

When brain runs Phase 3 browser validation, follow these patterns to save tokens:

1. **Refs > re-snapshot** — snapshot once per page, then click/fill via `ref` IDs
2. **`browser_evaluate` for targeted reads** — `document.querySelector('.counter').textContent` returns 50 bytes vs 5K for snapshot
3. **`browser_network_requests` for API verification** — don't snapshot to verify XHR worked
4. **Screenshot vs snapshot** — visual check uses screenshot (1.5K), interaction uses snapshot+ref

Brain has these in CLAUDE.md as anti-patterns. If brain re-snapshots after every click, push back: "use ref instead".

---

## Recipe replay

If `flows/<area>/<id>.recipe.md` exists for the flow you're testing, brain proposes using it:

```
🔍 Flow recipe lookup:
   Found 1 candidate for PROJ-123:
     ✓ auth.login-default (verified 3 days ago, replayed 5×)

   Estimated savings: ~12K tokens vs full discovery.

   [yes use it / discover anyway / refresh stale]
```

Reply `yes use it` → recipe replay (Tier 2 ~1K tokens). Brain follows verified path, just verifies state at end.

If recipe stale (selectors drifted) → brain enters mini-discovery, updates recipe.

---

## Common pitfalls

### "Why is brain re-asking for approval on read?"
Reads are **Tier 1 (auto)**. If brain asks approval on `get_ticket` — bug, push back.

### "Brain skipped Phase 1.5 idempotency check"
Anti-pattern #9 forbids silent reasoning. Brain MUST call `mcp__qa_cortex_ticketing__search_tickets` (or equivalent) and surface bracket-format. If it didn't, file an issue.

### "Brain invented UI navigation path"
Anti-pattern #6 forbids fabrication. Brain must verify via `flows/`, then test cases, then live Playwright, OR say "не знаю". Push back: "verify via Playwright".

### "Brain auto-posted to Slack"
Anti-pattern: Tier 3 violation. Slack post is Tier 3 (explicit gate). Brain should always preview + ask before `post_message(approved=True)`.

---

## Calibration loop

If brain regresses on any of these:
1. Log in `journal.sh dev-log "<observation>"`
2. Diagnose: was it a) skill prose ignored, b) CLAUDE.md anti-pattern not strong enough, c) provider adapter bug?
3. Fix in CLAUDE.md / SKILL.md / provider — one fix per regression
4. Re-test in fresh chat
5. Tag if it's a structural fix worth versioning

See `knowledge_base/design_docs/qa_cortex_v1.md` for the original v0.5 hardening playbook.

---

## Where to next

- Full architecture: `docs/architecture.md`
- Trust tiers deep-dive: `docs/trust-tiering.md`
- Adding new providers: `docs/adding-providers.md`
- Testing: `docs/testing.md`
- Examples: `examples/jira-testrail.md`
