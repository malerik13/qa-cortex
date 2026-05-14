#!/usr/bin/env bash
# Daily journal — single source of truth for standup notes.
#
# Storage:
#   journal/_active.md        Current session scratchpad (mission, log, bugs, blockers).
#   journal/YYYY-MM-DD.md     Daily aggregate. Sessions appended on `save`.
#
# Subcommands:
#   journal.sh init                          Ensure dirs and today's file exist.
#   journal.sh status                        Show current active session.
#   journal.sh mission "<text>"              Set/replace the current session mission.
#   journal.sh log "<QA-action>"             Append "Done" item (QA-significant only — see allow-list below).
#   journal.sh dev-log "<build-action>"      Meta-build action → dev/<DATE>.md (kept OUT of QA standup).
#   journal.sh bug TRD-XXXXX "<title>" [env] [tags]  Log a filed bug.
#   journal.sh blocker "<text>"              Log a blocker.
#   journal.sh save ["<summary>"]            Flush _active to today's file, reset _active.
#   journal.sh standup                       Print yesterday/today/blockers as standup speech.
#   journal.sh today                         Show today's daily file.
#   journal.sh yesterday                     Show yesterday's daily file.
#   journal.sh which-yesterday               Print yesterday's date (Mon-Fri-aware).
#
# Allow-list for `log` (QA actions):
#   - Tickets tested (TRD-X — Phase N done, outcome)
#   - Status changes (TRD-X moved Reopen → In Progress)
#   - Bugs filed (use `bug` subcommand, not `log`)
#   - Comments posted to YouTrack
#   - Blockers (use `blocker` subcommand)
#   - Open questions to PO/dev
#
# Disallow-list for `log` (use `dev-log` instead):
#   - Skill / persona creation/updates
#   - Plugin version bumps, MCP server work
#   - CLAUDE.md / KB edits
#   - Script creation, infrastructure work
#   - "Brain" construction in general
#
# Design principles:
#   - Append-only. Never destructive. Save only RESETS _active after appending.
#   - All file ops here, never in skills/commands directly. One source of truth.
#   - Idempotent. Safe to call repeatedly.
#   - macOS BSD-date compatible (no GNU `date -d`).
#   - Multi-process safe (mkdir-based exclusive lock for mutating ops; reads lock-free).
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
JDIR="$ROOT/journal"
ACTIVE="$JDIR/_active.md"
LOCK_DIR="$JDIR/.lock"
LOCK_TIMEOUT="${JOURNAL_LOCK_TIMEOUT:-10}"  # seconds — wait before giving up
LOCK_STALE="${JOURNAL_LOCK_STALE:-5}"       # seconds — mtime fallback if no pid recorded
TODAY=$(date +%Y-%m-%d)
TODAY_FILE="$JDIR/$TODAY.md"
NOW_HHMM=$(date +%H:%M)

mkdir -p "$JDIR"

# ── locking ───────────────────────────────────────────────────
# Atomic mkdir-based mutex. Survives crashes via stale-lock timeout.
acquire_lock() {
  local elapsed=0
  while ! mkdir "$LOCK_DIR" 2>/dev/null; do
    # Stale-lock recovery: prefer pid-based liveness; fall back to mtime.
    if [[ -d "$LOCK_DIR" ]]; then
      local stale=0
      local pid_file="$LOCK_DIR/pid"
      if [[ -s "$pid_file" ]]; then
        local pid
        pid=$(cat "$pid_file" 2>/dev/null || echo "")
        if [[ -n "$pid" ]] && ! kill -0 "$pid" 2>/dev/null; then
          stale=1
          echo "⚠ journal: lock holder PID $pid is dead — reclaiming" >&2
        fi
      else
        # No pid recorded — race window during creation; check mtime.
        local age
        age=$(( $(date +%s) - $(stat -f %m "$LOCK_DIR" 2>/dev/null || echo 0) ))
        if (( age > LOCK_STALE )); then
          stale=1
          echo "⚠ journal: stale lock (${age}s, no pid) — reclaiming" >&2
        fi
      fi
      if (( stale )); then
        rm -f "$pid_file" 2>/dev/null || true
        rmdir "$LOCK_DIR" 2>/dev/null || true
        continue
      fi
    fi
    if (( elapsed >= LOCK_TIMEOUT )); then
      echo "❌ journal: could not acquire lock after ${LOCK_TIMEOUT}s." >&2
      echo "   Another journal.sh is actively writing, or a stale lock survived." >&2
      echo "   Inspect: ls -la $LOCK_DIR" >&2
      exit 2
    fi
    sleep 0.2
    elapsed=$((elapsed + 1))
  done
  # Record PID immediately so other waiters can liveness-check us.
  echo "$$" > "$LOCK_DIR/pid"
  trap 'rm -f "$LOCK_DIR/pid" 2>/dev/null; rmdir "$LOCK_DIR" 2>/dev/null || true' EXIT INT TERM
}

release_lock() {
  rm -f "$LOCK_DIR/pid" 2>/dev/null || true
  rmdir "$LOCK_DIR" 2>/dev/null || true
  trap - EXIT INT TERM
}

# ── helpers ───────────────────────────────────────────────────
ensure_today() {
  if [[ ! -f "$TODAY_FILE" ]]; then
    {
      echo "# Daily $TODAY"
      echo
      echo "_Sessions are appended below as they're saved with \`journal.sh save\` or \`/save\`._"
      echo
    } > "$TODAY_FILE"
  fi
}

ensure_active() {
  if [[ ! -f "$ACTIVE" ]] || ! grep -q '^## Mission' "$ACTIVE" 2>/dev/null; then
    {
      echo "# Active session"
      echo
      echo "_Started: $TODAY ${NOW_HHMM}_"
      echo
      echo "## Mission"
      echo "(not set — call \`journal.sh mission \"...\"\` or use \`/mission\`)"
      echo
      echo "## Done"
      echo
      echo "## Bugs filed"
      echo
      echo "## Blockers"
      echo
    } > "$ACTIVE"
  fi
}

# Replace the body of a section (lines between '## Section' and the next '## ')
# in $ACTIVE with the given text. Appends if section is currently empty/placeholder.
replace_section() {
  local section="$1"; shift
  local new_body="$*"
  python3 - "$ACTIVE" "$section" "$new_body" <<'PY'
import sys, pathlib, re
path = pathlib.Path(sys.argv[1])
section = sys.argv[2]
new_body = sys.argv[3].rstrip() + "\n"
text = path.read_text()
pattern = re.compile(rf"(^## {re.escape(section)}\n)(.*?)(?=^## |\Z)", re.DOTALL | re.MULTILINE)
m = pattern.search(text)
if not m:
    path.write_text(text.rstrip() + f"\n## {section}\n{new_body}\n")
else:
    text = text[: m.start(2)] + new_body + "\n" + text[m.end(2):]
    path.write_text(text)
PY
}

append_to_section() {
  local section="$1"; shift
  local line="$*"
  python3 - "$ACTIVE" "$section" "$line" <<'PY'
import sys, pathlib, re
path = pathlib.Path(sys.argv[1])
section = sys.argv[2]
line = sys.argv[3]
text = path.read_text()
pattern = re.compile(rf"(^## {re.escape(section)}\n)(.*?)(?=^## |\Z)", re.DOTALL | re.MULTILINE)
m = pattern.search(text)
new_line = f"- {line}\n"
if not m:
    path.write_text(text.rstrip() + f"\n## {section}\n{new_line}\n")
else:
    body = m.group(2).rstrip() + "\n" + new_line + "\n"
    # Strip leading blank-only state if it's a clean section
    if body.strip() == new_line.strip():
        body = new_line + "\n"
    path.write_text(text[: m.start(2)] + body + text[m.end(2):])
PY
}

read_section() {
  local file="$1"; local section="$2"
  python3 - "$file" "$section" <<'PY'
import sys, pathlib, re
path = pathlib.Path(sys.argv[1])
section = sys.argv[2]
if not path.exists():
    sys.exit(0)
text = path.read_text()
pattern = re.compile(rf"^## {re.escape(section)}\n(.*?)(?=^## |\Z)", re.DOTALL | re.MULTILINE)
m = pattern.search(text)
if m:
    print(m.group(1).rstrip())
PY
}

# Yesterday for standup: Friday on Monday, otherwise calendar yesterday.
which_yesterday() {
  local dow
  dow=$(date +%u)  # 1=Mon ... 7=Sun
  case "$dow" in
    1) date -v-3d +%Y-%m-%d ;;  # Mon → Fri
    7) date -v-2d +%Y-%m-%d ;;  # Sun → Fri
    *) date -v-1d +%Y-%m-%d ;;
  esac
}

# ── commands ──────────────────────────────────────────────────
cmd="${1:-help}"; shift || true

case "$cmd" in

  init)
    ensure_today
    ensure_active
    echo "✓ journal/ ready. Today: $TODAY_FILE  Active: $ACTIVE"
    ;;

  status)
    ensure_active
    echo "── Active session ────────────────────────────────────"
    cat "$ACTIVE"
    # Staleness check — warn if _active.md is from a different day (per {TICKET_PREFIX}-XXXXX/12743 calibration 2026-05-13)
    if [[ -f "$ACTIVE" ]]; then
      # macOS BSD stat: -f %Sm with date format
      active_date=$(stat -f "%Sm" -t "%Y-%m-%d" "$ACTIVE" 2>/dev/null || stat -c "%y" "$ACTIVE" 2>/dev/null | cut -d' ' -f1)
      if [[ -n "$active_date" && "$active_date" != "$TODAY" ]]; then
        # Calculate days difference (best-effort, BSD-compatible)
        active_epoch=$(stat -f "%m" "$ACTIVE" 2>/dev/null || stat -c "%Y" "$ACTIVE" 2>/dev/null)
        today_epoch=$(date +%s)
        diff_days=$(( (today_epoch - active_epoch) / 86400 ))
        echo ""
        echo "⚠️  STALE — _active.md last touched ${active_date} (${diff_days} day(s) ago)"
        echo "   Decide: (a) continue this mission · (b) save what's there → reset · (c) just reset"
        echo "   Commands: journal.sh save 'wrap-up' · journal.sh mission '<new>'"
      fi
    fi
    ;;

  mission)
    text="${*:-}"
    if [[ -z "$text" ]]; then
      echo "❌ Usage: journal.sh mission \"<text>\"" >&2; exit 1
    fi
    acquire_lock
    ensure_active
    replace_section "Mission" "$text"
    release_lock
    echo "✓ Mission set: $text"
    ;;

  log)
    # Append a "Done" item — QA-significant action only.
    # FORBIDDEN content: meta-build noise (skill creation, plugin updates, MCP work,
    # CLAUDE.md edits, persona drafts, etc.). Use `dev-log` for that.
    # ALLOWED: tickets tested, bugs filed/closed/reopened, status changes,
    # comments posted, blockers, open questions to PO.
    text="${*:-}"
    [[ -z "$text" ]] && { echo "❌ Usage: journal.sh log \"<QA-action>\"" >&2; exit 1; }
    acquire_lock
    ensure_active
    append_to_section "Done" "$NOW_HHMM — $text"
    release_lock
    echo "✓ Logged: $text"
    ;;

  dev-log)
    # Meta-build / qa-brain construction work — separate file, not in QA standup.
    # Use this for: skill creation, plugin updates, MCP work, persona drafts,
    # CLAUDE.md edits, internal infrastructure. Does NOT touch _active.md.
    text="${*:-}"
    [[ -z "$text" ]] && { echo "❌ Usage: journal.sh dev-log \"<build-action>\"" >&2; exit 1; }
    DEV_DIR="$JDIR/dev"
    mkdir -p "$DEV_DIR"
    DEV_FILE="$DEV_DIR/$TODAY.md"
    if [[ ! -f "$DEV_FILE" ]]; then
      {
        echo "# Dev/build log — $TODAY"
        echo
        echo "_Meta-work on qa-brain itself (skills, MCP, personas, scripts). NOT QA standup material._"
        echo
      } > "$DEV_FILE"
    fi
    echo "- $NOW_HHMM — $text" >> "$DEV_FILE"
    echo "✓ Dev-logged to $DEV_FILE"
    ;;

  bug)
    id="${1:-}"; shift || true
    title="${1:-}"; shift || true
    env="${1:-}"; shift || true
    tags="${1:-}"  # comma-separated, e.g. "1st cohort" or "1st cohort,regression"
    if [[ -z "$id" || -z "$title" ]]; then
      echo "❌ Usage: journal.sh bug TRD-XXXXX \"<title>\" [env] [tag1,tag2,...]" >&2
      echo "   Example: journal.sh bug {TICKET_PREFIX}-XXXXX \"Bulk send fails\" staging \"1st cohort\"" >&2
      exit 1
    fi
    acquire_lock
    ensure_active
    line="**$id** — $title"
    meta_parts=()
    [[ -n "$env" ]] && meta_parts+=("env: $env")
    [[ -n "$tags" ]] && meta_parts+=("tags: $tags")
    if [[ ${#meta_parts[@]} -gt 0 ]]; then
      meta_str="${meta_parts[0]}"
      for ((i=1; i<${#meta_parts[@]}; i++)); do meta_str="$meta_str, ${meta_parts[$i]}"; done
      line="$line _($meta_str)_"
    fi
    append_to_section "Bugs filed" "$line"
    release_lock
    echo "✓ Bug logged: $id — $title${tags:+ [tags: $tags]}"
    ;;

  blocker)
    text="${*:-}"
    [[ -z "$text" ]] && { echo "❌ Usage: journal.sh blocker \"<text>\"" >&2; exit 1; }
    acquire_lock
    ensure_active
    append_to_section "Blockers" "$text"
    release_lock
    echo "✓ Blocker logged: $text"
    ;;

  save)
    summary="${*:-}"
    acquire_lock
    ensure_today
    if [[ ! -f "$ACTIVE" ]]; then
      release_lock
      echo "ℹ️  No active session to save." >&2; exit 0
    fi
    mission=$(read_section "$ACTIVE" "Mission")
    # Normalise placeholder text — never bleed it into the daily file
    if [[ -z "$mission" || "$mission" == *"not set"* ]]; then
      mission="(no mission set)"
    fi
    done_items=$(read_section "$ACTIVE" "Done")
    bugs=$(read_section "$ACTIVE" "Bugs filed")
    blockers=$(read_section "$ACTIVE" "Blockers")
    started=$(grep -m1 '^_Started:' "$ACTIVE" | sed 's/_Started: //; s/_$//')

    # If both done items and bugs are empty, refuse to save empty session
    if [[ -z "$done_items" && -z "$bugs" ]]; then
      release_lock
      echo "ℹ️  Active session has no Done items and no bugs — skipping save (use 'journal.sh log' first)." >&2
      exit 0
    fi

    # Determine session number for today (grep -c returns exit 1 when no matches; mask with || true)
    session_n=$( { grep -c '^## Session ' "$TODAY_FILE" 2>/dev/null || true; } | head -1)
    session_n=${session_n:-0}
    session_n=$((session_n + 1))

    {
      echo "## Session $session_n — ${mission:-(no mission)} _(saved $NOW_HHMM)_"
      [[ -n "$started" ]] && echo "_Started: ${started}_"
      echo
      echo "**Done:**"
      if [[ -n "$done_items" ]]; then
        echo "$done_items"
      else
        echo "- (nothing logged)"
      fi
      echo
      if [[ -n "$bugs" ]]; then
        echo "**Bugs filed:**"
        echo "$bugs"
        echo
      fi
      if [[ -n "$blockers" ]]; then
        echo "**Blockers:**"
        echo "$blockers"
        echo
      fi
      if [[ -n "$summary" ]]; then
        echo "**Summary:** $summary"
        echo
      fi
      echo "---"
      echo
    } >> "$TODAY_FILE"

    # Reset _active
    rm -f "$ACTIVE"

    release_lock
    echo "✓ Session $session_n saved to $TODAY_FILE"
    echo "✓ _active.md reset"
    ;;

  standup)
    YDAY=$(which_yesterday)
    YFILE="$JDIR/$YDAY.md"
    echo "# Daily standup — $TODAY"
    echo
    echo "## Вчера ($YDAY)"
    if [[ -f "$YFILE" ]]; then
      python3 - "$YFILE" <<'PY'
import sys, pathlib, re
text = pathlib.Path(sys.argv[1]).read_text()
done_blocks = re.findall(r"\*\*Done:\*\*\n(.*?)(?=\n\*\*|\n---|\Z)", text, re.DOTALL)
items = []
for block in done_blocks:
    for line in block.strip().splitlines():
        line = line.strip()
        if line.startswith("- "):
            # strip leading time prefix like "14:30 — "
            cleaned = re.sub(r"^- \d{2}:\d{2} — ", "- ", line)
            items.append(cleaned)
print("\n".join(items) if items else "_(пусто)_")

# Bug summary (separate count for 1st cohort)
bug_blocks = re.findall(r"\*\*Bugs filed:\*\*\n(.*?)(?=\n\*\*|\n---|\Z)", text, re.DOTALL)
bug_lines = []
for block in bug_blocks:
    for line in block.strip().splitlines():
        line = line.strip()
        if line.startswith("- "):
            bug_lines.append(line)
if bug_lines:
    total = len(bug_lines)
    first_cohort = sum(1 for b in bug_lines if "1st cohort" in b.lower())
    print()
    if first_cohort > 0:
        print(f"**Заведено багов: {total}** (из них `1st cohort`: **{first_cohort}**)")
    else:
        print(f"**Заведено багов: {total}**")
    for b in bug_lines:
        print(b)
PY
    else
      echo "_(нет записей за $YDAY)_"
    fi
    echo
    echo "## Сегодня"
    # Full content: pull Done entries + bugs from today's daily file AND active session.
    # Calibrated 2026-05-13: previously printed only session titles — too terse for real standup.
    has_today_content=0
    if [[ -f "$TODAY_FILE" ]]; then
      python3 - "$TODAY_FILE" <<'PY'
import sys, pathlib, re
text = pathlib.Path(sys.argv[1]).read_text()

# Done entries — strip time prefix for cleaner standup speech
done_blocks = re.findall(r"\*\*Done:\*\*\n(.*?)(?=\n\*\*|\n---|\Z)", text, re.DOTALL)
items = []
for block in done_blocks:
    for line in block.strip().splitlines():
        line = line.strip()
        if line.startswith("- "):
            cleaned = re.sub(r"^- \d{2}:\d{2} — ", "- ", line)
            items.append(cleaned)

if items:
    print("\n".join(items))

# Bugs filed today
bug_blocks = re.findall(r"\*\*Bugs filed:\*\*\n(.*?)(?=\n\*\*|\n---|\Z)", text, re.DOTALL)
bug_lines = []
for block in bug_blocks:
    for line in block.strip().splitlines():
        line = line.strip()
        if line.startswith("- "):
            bug_lines.append(line)

if bug_lines:
    total = len(bug_lines)
    first_cohort = sum(1 for b in bug_lines if "1st cohort" in b.lower())
    print()
    if first_cohort > 0:
        print(f"**Заведено багов: {total}** (из них `1st cohort`: **{first_cohort}**)")
    else:
        print(f"**Заведено багов: {total}**")
    for b in bug_lines:
        print(b)
PY
      has_today_content=1
    fi

    # Active session content (not yet saved to daily)
    if [[ -f "$ACTIVE" ]]; then
      active_done=$(read_section "$ACTIVE" "Done")
      active_bugs=$(read_section "$ACTIVE" "Bugs filed")
      mission=$(read_section "$ACTIVE" "Mission")

      if [[ -n "$active_done" || -n "$active_bugs" ]] || [[ -n "$mission" && "$mission" != *"not set"* ]]; then
        if [[ $has_today_content -eq 1 ]]; then
          echo ""
          echo "**In progress (active session — not yet saved):**"
        fi
        if [[ -n "$mission" && "$mission" != *"not set"* ]]; then
          echo "- $mission (in progress)"
        fi
        if [[ -n "$active_done" ]]; then
          echo "$active_done" | while IFS= read -r line; do
            [[ -z "$line" ]] && continue
            cleaned=$(echo "$line" | sed -E 's/^- [0-9]{2}:[0-9]{2} — /- /')
            echo "$cleaned"
          done
        fi
        if [[ -n "$active_bugs" ]]; then
          echo ""
          echo "**Active session bugs:**"
          echo "$active_bugs"
        fi
        has_today_content=1
      fi
    fi

    if [[ $has_today_content -eq 0 ]]; then
      echo "_(пока без миссии — задай через \`/mission\`)_"
    fi
    echo
    echo "## Блокеры"
    blockers_combined=""
    if [[ -f "$ACTIVE" ]]; then
      b_active=$(read_section "$ACTIVE" "Blockers")
      [[ -n "$b_active" ]] && blockers_combined+="$b_active"$'\n'
    fi
    if [[ -f "$TODAY_FILE" ]]; then
      b_today=$(python3 - "$TODAY_FILE" <<'PY'
import sys, pathlib, re
text = pathlib.Path(sys.argv[1]).read_text()
blocks = re.findall(r"\*\*Blockers:\*\*\n(.*?)(?=\n\*\*|\n---|\Z)", text, re.DOTALL)
items = []
for block in blocks:
    for line in block.strip().splitlines():
        line = line.strip()
        if line.startswith("- "):
            items.append(line)
print("\n".join(items))
PY
)
      [[ -n "$b_today" ]] && blockers_combined+="$b_today"$'\n'
    fi
    if [[ -n "$blockers_combined" ]]; then
      printf '%s' "$blockers_combined"
    else
      echo "_(нет)_"
    fi
    ;;

  today)
    if [[ -f "$TODAY_FILE" ]]; then cat "$TODAY_FILE"
    else echo "_(сегодня нет записей)_"; fi
    ;;

  yesterday)
    YDAY=$(which_yesterday)
    YFILE="$JDIR/$YDAY.md"
    if [[ -f "$YFILE" ]]; then cat "$YFILE"
    else echo "_(нет записей за $YDAY)_"; fi
    ;;

  which-yesterday)
    which_yesterday
    ;;

  help|--help|-h)
    sed -n '2,30p' "$0"
    ;;

  *)
    echo "❌ Unknown command: $cmd" >&2
    sed -n '2,30p' "$0" >&2
    exit 1
    ;;
esac
