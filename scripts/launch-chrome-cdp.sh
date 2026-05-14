#!/usr/bin/env bash
# launch-chrome-cdp.sh — start Chrome with CDP debugging port 9222
#
# Purpose: spawn a Chrome instance that chrome-devtools-mcp can attach to.
# Uses a dedicated profile dir so it doesn't clash with the daily-driver Chrome.
#
# Usage:
#   ./scripts/launch-chrome-cdp.sh            # start (background)
#   ./scripts/launch-chrome-cdp.sh --status   # check if port 9222 is alive
#   ./scripts/launch-chrome-cdp.sh --kill     # kill the CDP Chrome only
#
# After start: brain can call mcp__chrome-devtools__* tools (load via ToolSearch).
# Login is preserved between sessions because profile dir is persistent.

set -euo pipefail

PORT=9222
PROFILE_DIR="${HOME}/.chrome-cdp-profile"
CHROME_BIN="/Applications/Google Chrome.app/Contents/MacOS/Google Chrome"

is_running() {
  curl -sf "http://127.0.0.1:${PORT}/json/version" >/dev/null 2>&1
}

case "${1:-start}" in
  --status|status)
    if is_running; then
      echo "✓ Chrome CDP alive on port ${PORT}"
      curl -s "http://127.0.0.1:${PORT}/json/version" | head -5
      exit 0
    else
      echo "✗ Chrome CDP not running on port ${PORT}"
      exit 1
    fi
    ;;
  --kill|kill)
    pkill -f "remote-debugging-port=${PORT}" || true
    echo "Killed CDP Chrome (if it was running)."
    exit 0
    ;;
  start|--start|"")
    if is_running; then
      echo "Chrome CDP already running on port ${PORT}."
      exit 0
    fi
    if [[ ! -x "${CHROME_BIN}" ]]; then
      echo "ERROR: Chrome not found at: ${CHROME_BIN}" >&2
      exit 1
    fi
    mkdir -p "${PROFILE_DIR}"
    echo "Starting Chrome with CDP on port ${PORT}…"
    echo "  Profile: ${PROFILE_DIR}"
    "${CHROME_BIN}" \
      --remote-debugging-port=${PORT} \
      --user-data-dir="${PROFILE_DIR}" \
      --no-first-run \
      --no-default-browser-check \
      >/dev/null 2>&1 &
    disown
    # Poll a few seconds for the endpoint to come up
    for _ in 1 2 3 4 5 6 7 8 9 10; do
      sleep 0.5
      if is_running; then
        echo "✓ Chrome CDP up on http://127.0.0.1:${PORT}"
        echo "Brain: load tools via ToolSearch(query=\"select:mcp__chrome-devtools__navigate_page,mcp__chrome-devtools__list_pages,mcp__chrome-devtools__click,mcp__chrome-devtools__fill,mcp__chrome-devtools__evaluate_script,mcp__chrome-devtools__take_screenshot,mcp__chrome-devtools__list_console_messages,mcp__chrome-devtools__list_network_requests,mcp__chrome-devtools__wait_for\")"
        exit 0
      fi
    done
    echo "✗ Started Chrome but CDP endpoint did not respond in 5s." >&2
    exit 2
    ;;
  *)
    echo "Usage: $0 [start|--status|--kill]" >&2
    exit 1
    ;;
esac
