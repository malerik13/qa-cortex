#!/bin/bash
# Hook: block-api-bypass
# Blocks direct curl/wget calls to YouTrack/Allure write API.
# These bypass the MCP approval gate (approved=True pattern) — always forbidden.
# Tier 3 rule from CLAUDE.md: "Don't use direct curl for writes if MCP tool exists."

INPUT=$(cat)
CMD=$(echo "$INPUT" | python3 -c "
import sys, json
try:
    d = json.load(sys.stdin)
    print(d.get('tool_input', {}).get('command', ''))
except:
    print('')
" 2>/dev/null)

# Direct API write bypass detection
if echo "$CMD" | grep -qiE "(curl|wget).*(youtrack|allure).*(api|rest).*(-X (POST|PUT|DELETE|PATCH)|--data|--data-raw|-d )"; then
    echo "🚫 BLOCKED — Direct API write bypasses the MCP approval gate." >&2
    echo "   Use MCP tools instead: youtrack:create_bug, youtrack:add_comment, allure:create_test_case" >&2
    echo "   These enforce the preview → approved=True flow (Tier 3, CLAUDE.md)." >&2
    exit 2
fi

# Also block if it looks like a youtrack/allure POST without explicit -X (curl default POST via -d)
if echo "$CMD" | grep -qiE "(curl|wget).*(youtrack|allure).*(api|rest).*(-d |--data )"; then
    echo "🚫 BLOCKED — Direct API POST to YouTrack/Allure bypasses MCP approval gate." >&2
    echo "   Use MCP tools instead." >&2
    exit 2
fi

exit 0
