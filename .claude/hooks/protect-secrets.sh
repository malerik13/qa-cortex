#!/bin/bash
# Hook: protect-secrets
# Blocks Write/Edit on secrets and credential files.
# CLAUDE.md rule #5: "Don't commit .env, qa_credentials.md, *_token*, *.ovpn"

INPUT=$(cat)
FILE=$(echo "$INPUT" | python3 -c "
import sys, json
try:
    d = json.load(sys.stdin)
    print(d.get('tool_input', {}).get('file_path', ''))
except:
    print('')
" 2>/dev/null)

# Bail early if no file path
if [ -z "$FILE" ]; then
    exit 0
fi

# Block write to secrets files
if echo "$FILE" | grep -qiE "(\.env$|\.env\.|qa_credentials|_token\.|_token$|secrets\.|\.ovpn$|\.pem$|\.key$|credentials\.json)"; then
    echo "🚫 BLOCKED — Writing to secrets/credentials file: $FILE" >&2
    echo "   These files must never be committed. Edit manually in your shell." >&2
    echo "   Ensure the file is in .gitignore before proceeding." >&2
    exit 2
fi

# Warn (not block) on CLAUDE.md direct write — it's Tier 3 (requires Yaroslav approval)
if echo "$FILE" | grep -qE "CLAUDE\.md$"; then
    echo "⚠️  WARN — Writing to CLAUDE.md (master prompt). Tier 3 protected." >&2
    echo "   Every CLAUDE.md change requires Yaroslav-approved diff. Proceeding, but confirm approval." >&2
    # exit 1 = warn but allow in Claude Code hooks
    exit 1
fi

exit 0
