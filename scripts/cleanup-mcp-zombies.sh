#!/usr/bin/env bash
# Cleanup orphaned MCP server processes.
#
# Why this exists:
#   Claude Code spawns MCP servers (youtrack, allure) as stdio subprocesses
#   per chat session. When the chat closes, Claude Code is supposed to
#   terminate them — but doesn't reliably (likely because python's stdio
#   loop doesn't wake up cleanly when the parent dies). Result: orphaned
#   processes, parented by launchd (PID 1), eating ~50MB RAM each.
#
#   After 7 closed sessions you have ~700MB leaked. This script finds and
#   kills only the orphans, leaving live (currently attached) MCP servers
#   alone.
#
# Algorithm:
#   1. Find all `mcp/youtrack/server.py` and `mcp/allure/server.py` processes
#   2. For each, check parent PID
#   3. If parent is launchd (PPID=1) OR parent isn't `claude` → orphan, kill
#   4. If parent IS `claude` → live, leave alone
#
# Usage:
#   scripts/cleanup-mcp-zombies.sh             # find + kill
#   scripts/cleanup-mcp-zombies.sh --dry-run   # just report, no kills
#
# Wrapper for the Python implementation. Python keeps the logic readable.

set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
exec python3 "$ROOT/scripts/cleanup-mcp-zombies.py" "$@"
