#!/bin/bash
# Hook: warn-mcp-edit
# Triggered on PostToolUse for Edit/Write.
# When mcp/*/server.py is edited, surfaces reminder that Claude Code restart
# is required for the MCP server to pick up new code.
# Calibrated 2026-05-13 after TRD-12743 allure /step fix didn't activate in session.

INPUT=$(cat)
FILE=$(echo "$INPUT" | python3 -c "
import sys, json
try:
    d = json.load(sys.stdin)
    print(d.get('tool_input', {}).get('file_path', ''))
except:
    print('')
" 2>/dev/null)

if [ -z "$FILE" ]; then
    exit 0
fi

# Match mcp/*/server.py
if echo "$FILE" | grep -qE '/mcp/[^/]+/server\.py$'; then
    SERVER_NAME=$(echo "$FILE" | sed -E 's|.*/mcp/([^/]+)/server\.py$|\1|')
    cat >&2 <<EOF

⚠️  Edited MCP server: $SERVER_NAME ($FILE)
    Changes will NOT take effect in this session.
    To activate fix:
      1. Save context (journal.sh save / commit if needed)
      2. Quit Claude Code (Cmd+Q)
      3. Reopen — MCP servers restart with new code
    Calibration: TRD-12743 (2026-05-13) — yesterday's allure fix didn't fire today.

EOF
    # exit 0 — informational, don't block
fi

exit 0
