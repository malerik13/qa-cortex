#!/bin/bash
# Hook: verify-journal-on-stop  (Stop event)
# Checks that if qa-output/ was written this session, the journal has a log entry for today.
# Enforces CLAUDE.md anti-pattern #4: "Don't skip journal entry after QA-significant action."
# Pattern from cwc-long-running-agents Default-FAIL contract.

TODAY=$(date +%Y-%m-%d)

# Resolve project root: prefer Claude Code's $CLAUDE_PROJECT_DIR, fall back to
# computing from this script's location (.claude/hooks/<this>.sh → ../..).
PROJECT_ROOT="${CLAUDE_PROJECT_DIR:-$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)}"

JOURNAL_FILE="${PROJECT_ROOT}/journal/${TODAY}.md"
QA_OUTPUT_DIR="${PROJECT_ROOT}/qa-output"

# Only enforce if qa-output has files modified today
RECENT_QA=$(find "$QA_OUTPUT_DIR" -name "*.md" -newer "$QA_OUTPUT_DIR" -maxdepth 2 2>/dev/null | head -1)

if [ -z "$RECENT_QA" ]; then
    # No qa-output written today — no journal required
    exit 0
fi

# qa-output was written — check journal exists and has content
if [ ! -f "$JOURNAL_FILE" ]; then
    echo "⚠️  Journal entry missing for today ($TODAY)." >&2
    echo "   qa-output/ was modified this session but journal/${TODAY}.md doesn't exist." >&2
    echo "   Run: bash scripts/journal.sh log '<verdict>'" >&2
    echo "   Or: bash scripts/journal.sh save" >&2
    # exit 1 = warn but allow session to end
    exit 1
fi

# Journal exists — check it has at least one log/bug entry (not just mission line)
LOG_ENTRIES=$(grep -cE "^- \[(log|bug|blocker|status)\]" "$JOURNAL_FILE" 2>/dev/null || echo 0)

if [ "$LOG_ENTRIES" -eq 0 ]; then
    echo "⚠️  Journal exists but has no log/bug/status entries for $TODAY." >&2
    echo "   Add a test verdict: bash scripts/journal.sh log 'TRD-XXXXX retest release: <verdict>'" >&2
    exit 1
fi

exit 0
