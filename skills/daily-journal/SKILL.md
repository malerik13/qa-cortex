---
name: daily-journal
description: Manage the daily QA standup journal — record QA-significant work only (tickets tested, bugs filed/closed/reopened, status changes, blockers, open questions). Triggers when Yaroslav says "save", "сохрани", "сохрани в дейлик", "сохраняй", "тестирование завершено", "конец тестирования", "чат завершен", "завершай чат", "стендап", "standup", "дейлик", "что я делал вчера", or asks to record a blocker. Also triggers when a bug is filed and needs to be logged. Filters out meta-build chatter (skill/plugin/persona/MCP work goes to `journal/dev/<DATE>.md` via `dev-log`, not the QA journal).
---

You manage the QA daily journal at `journal/`. **Single rule: every file op goes through `scripts/journal.sh`.** Never edit journal files directly.

## What this journal IS

A clean record of **QA-significant work** for daily standup speech. Format expected at standup:
- What I tested
- What bugs I filed / closed / reopened
- What status changes I made
- What's blocking me
- What questions need PO/dev answers

**Nothing else.**

## What this journal is NOT

NOT a meta-development log. Skill creation, plugin updates, MCP server work, persona drafts, KB edits, script writing — these belong in `journal/dev/<DATE>.md` via `journal.sh dev-log`. They do NOT pollute the QA standup.

---

## Allow-list — `journal.sh log`

Use `journal.sh log "<text>"` ONLY for these categories:

| Category | Example log line |
|---|---|
| **Ticket tested** | `Tested <TICKET>-13728 — Phase 3 PASS, all AC verified on release-ca` |
| **Re-test after fix** | `Re-tested <TICKET>-13752 fix — original Fail no longer reproduces, ready for Verified` |
| **Status change** | `Moved <TICKET>-11927 Reopen → In Progress (re-test scheduled)` |
| **Comment posted** | `Posted comment on <TICKET>-11636 to @Roman.Koliada — autofill bug request` |
| **Blocker discovered** | (use `journal.sh blocker` — separate command) |
| **Open question to PO** | `Open question: <TICKET>-11527 AC #5 lang priority logic — asked Timofei in Slack` |
| **Test plan finalized** | `Phase 1 complete for <TICKET>-13728 — 3 AC, 5 <test-mgmt> cases, 2 gaps, artefact written` |
| **<test-mgmt> case run outcome** | `<test-mgmt> case 312712 — PASS / FAIL_SUSPECT / NEEDS_REVIEW with brief reason` |

Format: short, factual, action verb + <TICKET>-ID + outcome.

## Bug filed — use `journal.sh bug` (NOT `log`)

```bash
journal.sh bug <TICKET>-XXXXX "<title from bug body>" <env> "<tags-csv-or-empty>"
```

Triggered automatically by bug-report skill Step 4 after `create_ticket` returns the new <TICKET>-ID.

## Disallow-list — these go to `dev-log`, NOT `log`

If you're about to log any of these, **use `journal.sh dev-log` instead**:

- Skill creation / SKILL.md edits / new skills registered
- Plugin version bumps (0.x.y → 0.x.z), `claude plugin update` runs
- MCP server work (<ticketing>/allure/etc — code edits, new tools, version bumps)
- Persona drafts / qa_persona / orchestrator_persona / mentor_persona edits
- CLAUDE.md edits / operative firewall changes
- KB file creation/edits (insights.md, business_rules.md, db_naming_map.md, etc.)
- Script creation/edits (`scripts/*.py`, `scripts/*.sh`)
- Infrastructure work (cleanup-zombies, brain-stats, hooks)
- Calibration rounds, persona refinements
- "Brain construction" in general

These ARE valuable to record — but in `journal/dev/<DATE>.md`, not the QA standup file.

## Save — what happens on trigger

Triggers: "save" / "сохрани" / "сохраняй" / "сохрани в дейлик" / "тестирование завершено" / "конец тестирования" / "чат завершен" / "завершай чат".

### Step 1 — Inventory check

```bash
scripts/journal.sh status
```

Look at `_active.md`. Items in "Done" — ALL must be QA-significant per allow-list. If there are meta-build entries (skill/plugin/persona/MCP/etc.) that slipped in:

1. Acknowledge the slip-up briefly to user.
2. Move them mentally to `dev-log` (write them via `journal.sh dev-log "..."` so they survive).
3. Ask user: «эти entries относятся к QA или к build? — выкину из save или оставить?» (default: drop them from QA save).

### Step 2 — Synthesize from chat context (gap-fill)

Even if `_active.md` looks complete, scan chat history for QA-significant facts that weren't logged:

- Tickets discussed → tested? logged?
- Bugs mentioned → filed? if yes, in `Bugs filed` section?
- Status changes → moved through Reopen/Verified?
- Blockers raised → captured?
- Open questions → captured?

If any gap, top it up via `log` / `bug` / `blocker` BEFORE save. Be quick — don't ask user to verify each, just close obvious gaps.

### Step 3 — Save

```bash
scripts/journal.sh save "<one-line summary, optional but recommended>"
```

Summary should describe the **QA outcome** of the session, not the activities:
- ✅ Good: «<TICKET>-13728 verified on release, <TICKET>-11927 re-tested, 1 new bug filed (<TICKET>-13800)»
- ❌ Bad: «meta-build session — added new tools, edited persona»

### Step 4 — Confirm to user

> «Сохранил Session N в `journal/<DATE>.md`. Tested: X tickets. Bugs filed: Y. Status changes: Z.»

If session was empty / non-QA → don't fabricate:
> «Сегодня QA-action не было — _active.md пуст. Build-работа осталась в `journal/dev/<DATE>.md` если использовали `dev-log`.»

## Standup — produce morning speech

Trigger: "стендап" / "дейлик" / "standup" / "что я делал вчера" / "готовь спич на стендап".

```bash
scripts/journal.sh standup
```

Polish the output into Slack-ready format. Three sections:
- **Вчера:** (from yesterday's QA journal — only QA-significant items)
- **Сегодня:** (from today's `_active.md` mission OR planned tickets)
- **Блокеры:** (carried over)

If yesterday's journal was empty (no QA work) → say honestly «вчера было meta-build, QA-action не было».

## Hard rules

1. **Bug filed = journal entry. Always.** When `bug-report` skill or `bug-writer` agent finalizes a bug, the very next action is `journal.sh bug`. No exceptions.

2. **Mission set on session start.** If the chat is QA work and `_active.md` has no mission, ask: «Какая миссия?». Set before continuing.

3. **No meta-build in QA log.** If brain accidentally writes meta-build to `journal.sh log`, must catch on save and migrate to `dev-log`.

4. **Don't edit past daily files.** History is immutable. Corrections — note in TODAY's file referencing past entry.

5. **Don't fabricate a Session.** If no QA work happened, say so. Empty save is fine.

## Self-check at session start

When new chat begins (or skill triggers first time):

```bash
scripts/journal.sh status
```

- **Mission set + recent items?** → continuing session. Ask: «Активная сессия с миссией X. Та же или новая?»
- **Empty (only placeholders)?** → fresh. Ask: «Какая миссия?»
- **Mission set but items from yesterday's chat?** → carry-over. Ask: «`_active.md` остался от вчера. Сохранить вчерашним числом или сбросить?»

## File reference

- `journal/<DATE>.md` — QA standup history (committed, immutable past dates)
- `journal/dev/<DATE>.md` — internal build log (kept separately, not in standup)
- `journal/_active.md` — current chat scratchpad (gitignored, reset on save)
- `journal/README.md` — full format spec
- `scripts/journal.sh help` — full command list
