# Daily Journal — Standup Notes

> Single source of truth for daily standup speeches.
> All file ops happen via `scripts/journal.sh` (one helper, no logic drift).

---

## How it works

### Concepts

- **Active session** (`_active.md`) — the current chat's scratchpad. Holds the
  mission, the running tally of what was done, bugs filed, blockers. One per
  chat session. Reset on `save`.
- **Daily file** (`YYYY-MM-DD.md`) — the aggregate for one day. Sessions are
  appended to it on `save`. Source for the next morning's standup speech.

### Lifecycle of a chat session

```
chat starts
     ↓
mission stated  →  journal.sh mission "..."   (or `/mission ...`)
     ↓
work happens, items logged as they finish:
     ↓     journal.sh log "..."        (significant achievement)
     ↓     journal.sh bug TRD-X "..."  (bug filed, RULE: always log)
     ↓     journal.sh blocker "..."    (anything that's stuck)
     ↓
mission achieved
     ↓
user says "save"  →  journal.sh save     (or `/save`)
     ↓
_active.md flushed into today's daily file as a Session
_active.md reset (empty for next chat)
```

### Morning standup

```
journal.sh standup    (or `/standup`)
```

Outputs three sections in Russian:
- **Вчера** — items from yesterday's daily file (Friday on Mondays)
- **Сегодня** — current active session's mission + missions of sessions saved today
- **Блокеры** — open blockers from today's file + active session

---

## Hard rules

1. **Every bug filed → must be logged.** When the QA approves a bug draft and
   it's posted to YouTrack, immediately call:
   ```
   journal.sh bug TRD-XXXXX "<title>" [env]
   ```
   This is non-negotiable — it's how the morning standup knows what shipped.

2. **One mission per chat.** State it explicitly at chat start. If the chat
   pivots, save the current mission and set a new one.

3. **Append-only.** Never edit past daily files manually. If a fact was wrong,
   add a correction note in today's file referencing the past entry.

4. **Save before ending the chat.** If `_active.md` has content when a chat ends
   without `save`, that work is invisible to standup until you save it.

---

## File format reference

### `_active.md`
```markdown
# Active session

_Started: 2026-04-29 13:51_

## Mission
<one-sentence mission>

## Done
- 13:51 — <achievement>
- 14:20 — <achievement>

## Bugs filed
- **TRD-13599** — Title _(env: staging-ca)_

## Blockers
- <blocker>
```

### `YYYY-MM-DD.md`
```markdown
# Daily 2026-04-29

## Session 1 — <mission> _(saved 14:50)_
_Started: 2026-04-29 13:51_

**Done:**
- 13:51 — <achievement>
...

**Bugs filed:**
- **TRD-13599** — ...

**Blockers:**
- ...

---

## Session 2 — ...
```

---

## Recovery / edge cases

- **Forgot to save.** `journal.sh status` shows current `_active.md`. Run `save`
  even later — items are timestamped, the chronology survives.
- **Wrong mission.** Run `journal.sh mission "..."` again — it replaces.
- **Bug logged twice.** That's fine; the daily file shows both. Add a correction
  note if it matters.
- **Two chats running in parallel.** Both write to the same `_active.md`. This
  is unsupported. Save and reset before starting the second chat.
