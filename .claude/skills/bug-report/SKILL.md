---
name: bug-report
description: File a [COMPANY] bug. Triggers when user asks "оформи баг", "напиши баг-репорт", "log a bug", "log this as a bug", "create bug for X", or describes broken behavior wanting to report it. Two-step approval (preview → "да create" → submit) + journal log + 1st cohort verbatim ask. English only per qa_persona §7 language matrix.
---

You produce a [COMPANY] bug. **English body**, regardless of input language.

**Pre-conditions checked by CLAUDE.md firewall (already enforced):**
- Anti-pattern #5: 1st cohort verbatim ask (this skill surfaces it explicitly at Phase B)
- Anti-pattern #4: journal log after creation (Phase E)
- Two-step approval gate (Phases C+D)

This skill organizes the flow into 5 phases: **A) Prepare → B) Classify → C) Preview → D) Approve+Submit → E) Journal+Notify**.

---

## Phase A — Prepare draft

Gather (one-by-one only if missing from context / `qa-output/*.md`):

```
☐ Parent User Story (TRD-X — find via youtrack:search_tickets if not given)
☐ Environment (staging | staging-ca | release | [release-alt] | demo | prod)
☐ Steps to reproduce (exact clicks/actions, no shortcuts)
☐ Expected per AC (cite AC verbatim if possible)
☐ Actual observed
☐ Client/Account/Entity IDs involved
☐ Visual evidence (screenshot path / video URL / console log / DB rows)
```

**Optional:** delegate to `Task(subagent_type="qa-orchestra:bug-reporter")` for draft generation if `qa-output/functional-review.md` or `qa-output/browser-validation.md` exists. Otherwise draft inline.

**Style requirements** (per accumulated calibration):
- Title: `verb + object + condition` (no `[TRD-X]` prefix — added by MCP)
- Body: clinical engineering EN, no "I think" / hedging
- One symptom = one bug (Daily Rule 6 — never combine)
- One role per bug (not «aaa or qatestbot»)
- Env links inline (not in separate "Links" section — per `feedback_bug_env_links`)
- Visual evidence references in body (per `feedback_bug_screenshots`)

---

## Phase B — Classify (HARD CHECKPOINTS)

### B1 — 1st cohort verbatim ask

```
STOP — surface to Yaroslav exactly:

  «Этот баг — `1st cohort` (очевидное нарушение главного AC, dev не сделал smoke перед stage)?» [yes / no / unsure]

  Критерии (все три = yes):
  (1) главный AC,
  (2) happy path с первого раза,
  (3) 60-секундный smoke поймал бы.
```

**Forbidden:** silently decide «not 1st cohort because edge case». Decision is Yaroslav's, not brain's.

### B2 — Severity (walk qa_persona §11 algorithm — don't gut-pick)

```
1. Domain check (money / security / compliance / tenancy)? → apply floor
2. Scope check (only Super Admin / one browser / one env)? → apply ceiling
3. Functional impact (blocking / degraded / cosmetic)?
4. Result = MAX(scale, floor), then MIN(that, ceiling)
```

Surface the walked reasoning briefly (1-2 lines), not just the final value.

---

## Phase C — Preview (no submit)

```
mcp__youtrack__create_bug(
  parent_trd     = "{TICKET_PREFIX}-XXXXX",
  summary        = "<verb + object + condition>",
  description    = "<full EN body, env links inline, visual evidence refs>",
  severity       = "<Critical | Major | Normal | Minor | Trivial>",
  priority       = "<Critical | High | Normal | Low>",
  subsystem      = "CRM",
  affected_version = "<e.g. '3.0'>",
  release_version  = "<target fix version>",
  tags           = [<list incl '1st cohort' if Phase B1 = yes>],
  bsource        = "feature-test"
  # approved param OMITTED → returns preview + idempotency check
)
```

**Forbidden:** calling with `approved=true` on first invocation. Always preview first.

Surface preview to Yaroslav with explicit env reasoning:

```
**Env choice:** Release (because {TICKET_PREFIX}-11636 ships in v3.0 demo tomorrow). Override?

[Preview body shown here]

**Idempotency:** [N similar OPEN bugs found / no duplicates]

**Ready to create?** [yes / edit / cancel]
```

---

## Phase D — Approve + submit

Wait for explicit `yes` / «да create» / «yes create».

Possible responses + actions:
- `yes` → Phase D submit (below)
- `edit <section>` → revise, re-Phase C
- `cancel` → STOP, no submit
- Classification question → answer, re-Phase C

On approval:
```
mcp__youtrack__create_bug(
  ...same fields as Phase C...,
  approved = true
)
```

If duplicate-warning raised in C but Yaroslav confirmed separate symptom → add `force=true`.

Returns new TRD-ID + URL.

---

## Phase E — Journal + notify

### E1 — Journal (NON-NEGOTIABLE per CLAUDE.md anti-pattern #4)

```bash
scripts/journal.sh bug TRD-NEWID "<title from draft>" <env> "<tags-csv-or-empty>"
```

Without this — morning standup doesn't know the bug exists.

### E2 — Tell Yaroslav

```
✅ Создал TRD-NEWID. URL: https://[your-domain]/issue/TRD-NEWID

Severity: <X>. Priority: <Y>. Tags: <list>.
Journal: записал в `journal/<DATE>.md`.
```

### E3 — Propose auto-retest scheduled task (calibrated 2026-05-13)

После filing предложи Yaroslav поставить retest watcher:

```
🔁 Auto-retest watcher для TRD-NEWID?

Brain будет каждые 2ч (Mon-Fri рабочие часы) проверять статус через
youtrack:get_ticket. Когда dev переведёт в `Ready for QA` →
запишет в journal "TRD-NEWID ready for retest" и уведомит при
следующем открытии Claude Code.

Поставить? [yes / no / другой интервал]
```

После «yes» — `mcp__scheduled-tasks__create_scheduled_task`:

```javascript
{
  taskId: "retest-watch-TRD-NEWID",
  cronExpression: "0 7-15/2 * * 1-5",  // every 2h, 07:00-15:00 Poland (12:00-20:00 Vietnam), Mon-Fri
  description: "Watch TRD-NEWID for Ready for QA status",
  prompt: `Check YouTrack ticket TRD-NEWID status via youtrack:get_ticket.

If state == "Ready for QA":
  1. journal.sh log "TRD-NEWID moved to Ready for QA — retest scheduled"
  2. Output one-line notification: "🔔 TRD-NEWID ready for retest — dev fixed it"
  3. Suggest user to start Phase 5 validation session

If state != "Ready for QA" (still in dev / submitted / etc):
  - No-op. Don't log to journal (would be spam).
  - Next fire in 2h continues watching.

If state == "Verified" / "Done":
  - Task done, propose user disable via mcp__scheduled-tasks__update_scheduled_task.
`,
  notifyOnCompletion: false  // только при значимом state change
}
```

**Что Yaroslav получит:**
- Каждые 2ч в фоне проверка
- Notification только когда dev реально передал на retest
- В журнале появится «TRD-NEWID ready for retest» — видно в standup speech, в control center
- Не нужно manually проверять YouTrack — просто открыл brain и увидел

**Skip если:**
- Bug filed как «won't fix» candidate
- Long-term backlog item
- Bonus finding с Severity Minor

---

## Hard rules

1. **Two-step approval always.** Phase C (preview) → Phase D (submit). No bypass.
2. **EN body strict.** Chat with Yaroslav RU, bug body EN. Per language matrix.
3. **One symptom = one bug.** Daily Rule 6 — never combine.
4. **Walk severity algorithm.** Don't gut-pick — show the walk.
5. **No UI invention in Steps.** Anti-pattern #6 in CLAUDE.md (verify ladder).
6. **Journal Phase E1 is non-negotiable.** Bug filed without journal = process violation.
7. **1st cohort = Yaroslav's call** (verbatim ask, B1) — not brain's silent reasoning.

---

## Failure modes

- **`qa-orchestra:bug-reporter` not loaded** → draft inline per CLAUDE.md template, skip optional delegation in Phase A.
- **`create_bug` returns 401/5xx** → tell Yaroslav, log as failed attempt, retry once after pause.
- **Duplicate warning** → present similar bug to Yaroslav: link as Duplicate / file separate symptom (`force=true`) / cancel.
- **Custom-field commands fail post-create** → bug exists but fields wrong; tell Yaroslav, give URL for manual fix.
