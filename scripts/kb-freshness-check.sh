#!/usr/bin/env bash
# Non-blocking freshness check. Runs at SessionStart via plugin hook.
# Only PRINTS a reminder — never auto-refreshes.

set -e

PLUGIN_ROOT="${CLAUDE_PLUGIN_ROOT:-$(cd "$(dirname "$0")/.." && pwd)}"
INDEX="$PLUGIN_ROOT/knowledge_base/user_stories.json"
META="$PLUGIN_ROOT/kb_cache/last_sync.json"

# Load .env for KB_STALE_DAYS
[ -f "$PLUGIN_ROOT/.env" ] && set -a && . "$PLUGIN_ROOT/.env" && set +a
STALE_DAYS="${KB_STALE_DAYS:-7}"

if [ ! -f "$INDEX" ]; then
  cat <<EOF
{"hookSpecificOutput": {"hookEventName": "SessionStart", "additionalContext": "⚠️ KB index not built yet. Run: python3 scripts/update-kb.py"}}
EOF
  exit 0
fi

# macOS stat uses -f, Linux uses -c
if stat -f "%m" "$INDEX" >/dev/null 2>&1; then
  MTIME=$(stat -f "%m" "$INDEX")
else
  MTIME=$(stat -c "%Y" "$INDEX")
fi

NOW=$(date +%s)
AGE_DAYS=$(( (NOW - MTIME) / 86400 ))

if [ "$AGE_DAYS" -gt "$STALE_DAYS" ]; then
  cat <<EOF
{"hookSpecificOutput": {"hookEventName": "SessionStart", "additionalContext": "ℹ️ KB index is ${AGE_DAYS} days old (threshold: ${STALE_DAYS}). Consider refreshing: /refresh-kb"}}
EOF
fi

exit 0
