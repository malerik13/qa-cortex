#!/usr/bin/env bash
# ═══════════════════════════════════════════════════════════════
#  qa-brain — portable bootstrap installer
# ═══════════════════════════════════════════════════════════════
#  Usage:
#      scripts/install.sh                       # auto-detect PROJECT_ROOT
#      scripts/install.sh /path/to/project      # explicit project root
#      PROJECT_ROOT=/path scripts/install.sh    # via env
#
#  What it does (idempotent — safe to re-run):
#    1. Resolves PROJECT_ROOT
#    2. Validates prerequisites (python3 3.10+, git, optional: claude, gh, psql)
#    3. Creates .venv + installs Python deps
#    4. Generates .mcp.json from templates/.mcp.json.template (path substitution)
#    5. Copies templates/env.template → .env (if missing, warns to fill tokens)
#    6. Validates .claude/settings.json hook paths (CLAUDE_PROJECT_DIR-based)
#    7. Prints next steps
#
#  Scope: Phase 0 portable bootstrap. Does NOT install qa-orchestra plugins or
#         build the YouTrack/Allure KB index — those are stack-specific and
#         live in scripts/setup.sh (legacy, stack-specific).
# ═══════════════════════════════════════════════════════════════

set -euo pipefail

# ─── Colors ─────────────────────────────────────────────────────
if [ -t 1 ]; then
  R='\033[0;31m'; G='\033[0;32m'; Y='\033[0;33m'; B='\033[0;34m'; X='\033[0m'
else
  R=''; G=''; Y=''; B=''; X=''
fi

ok()    { echo -e "${G}✓${X} $1"; }
info()  { echo -e "${B}ℹ${X} $1"; }
warn()  { echo -e "${Y}⚠${X} $1"; }
fail()  { echo -e "${R}✗${X} $1"; exit 1; }
step()  { echo ""; echo -e "${B}═══${X} $1 ${B}═══${X}"; }

# ─── Resolve PROJECT_ROOT ───────────────────────────────────────
# Priority: $1 arg > $PROJECT_ROOT env > auto-detect from this script's location.
if [ -n "${1:-}" ]; then
  PROJECT_ROOT="$(cd "$1" && pwd)"
elif [ -n "${PROJECT_ROOT:-}" ]; then
  PROJECT_ROOT="$(cd "$PROJECT_ROOT" && pwd)"
else
  PROJECT_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
fi

if [ ! -d "$PROJECT_ROOT" ]; then
  fail "PROJECT_ROOT does not exist: $PROJECT_ROOT"
fi

cd "$PROJECT_ROOT"

echo ""
echo "╔══════════════════════════════════════════════════════════════╗"
echo "║   qa-brain — Portable Bootstrap                              ║"
echo "╚══════════════════════════════════════════════════════════════╝"
echo "PROJECT_ROOT: $PROJECT_ROOT"

# ─── Sanity: this looks like a qa-brain repo ────────────────────
for required in CLAUDE.md scripts mcp templates requirements.txt; do
  [ -e "$PROJECT_ROOT/$required" ] || fail "Missing $required — is this a qa-brain repo?"
done
ok "Repo structure looks correct"

# ─── Step 1: Prerequisites ──────────────────────────────────────
step "1/6 Checking prerequisites"

command -v python3 >/dev/null || fail "python3 not found. Install Python 3.10+."
PY_VER=$(python3 -c "import sys; print(f'{sys.version_info.major}.{sys.version_info.minor}')")
PY_OK=$(python3 -c "import sys; print(1 if sys.version_info >= (3, 10) else 0)")
[ "$PY_OK" = "1" ] || fail "Python $PY_VER is too old. Need Python 3.10+ (MCP SDK requirement)."
ok "python3 found ($PY_VER)"

command -v git >/dev/null || fail "git not found. Install git."
ok "git found"

# Optional tools — warn but don't fail
if command -v claude >/dev/null; then
  CLAUDE_VER=$(claude --version 2>/dev/null || echo 'version unknown')
  ok "claude CLI found ($CLAUDE_VER)"
else
  warn "claude CLI not found. Install with: npm install -g @anthropic-ai/claude-code"
  warn "  (Required to actually run the brain. Continuing install so you can fix later.)"
fi

if command -v gh >/dev/null; then
  ok "gh CLI found"
else
  warn "gh CLI not found. Optional but used for PR workflows."
fi

if command -v psql >/dev/null; then
  ok "psql found"
else
  warn "psql not found. Optional — only needed if scripts/db-query.sh is used."
fi

# ─── Step 2: Python venv + deps ─────────────────────────────────
step "2/6 Setting up Python virtual environment"

if [ ! -d "$PROJECT_ROOT/.venv" ]; then
  python3 -m venv "$PROJECT_ROOT/.venv"
  ok "Created .venv"
else
  ok ".venv already exists"
fi

# shellcheck disable=SC1091
source "$PROJECT_ROOT/.venv/bin/activate"

pip install --quiet --upgrade pip
pip install --quiet -r "$PROJECT_ROOT/requirements.txt"

# Install MCP-specific deps too (mcp/*/requirements.txt — may differ from root)
for mcp_req in "$PROJECT_ROOT"/mcp/*/requirements.txt; do
  [ -f "$mcp_req" ] || continue
  pip install --quiet -r "$mcp_req"
done

ok "Installed Python dependencies"

# ─── Step 3: Generate .mcp.json from template ───────────────────
step "3/6 Generating .mcp.json"

TEMPLATE="$PROJECT_ROOT/templates/.mcp.json.template"
TARGET="$PROJECT_ROOT/.mcp.json"

if [ ! -f "$TEMPLATE" ]; then
  fail "Missing template: $TEMPLATE"
fi

# Use '|' as sed delimiter to avoid path-slash collisions
sed "s|{{PROJECT_ROOT}}|${PROJECT_ROOT}|g" "$TEMPLATE" > "$TARGET"

# Validate generated JSON
python3 -c "import json; json.load(open('$TARGET'))" >/dev/null 2>&1 \
  || fail "Generated .mcp.json is not valid JSON. Inspect $TARGET."

# Validate paths inside it actually exist (the python binary + the server.py files)
PY_BIN=$(python3 -c "import json; d=json.load(open('$TARGET')); print(d['mcpServers']['youtrack']['command'])")
[ -x "$PY_BIN" ] || fail "Generated .mcp.json references missing python: $PY_BIN"

for server in youtrack allure; do
  SERVER_PY=$(python3 -c "import json; d=json.load(open('$TARGET')); print(d['mcpServers']['$server']['args'][0])")
  [ -f "$SERVER_PY" ] || warn "MCP server file missing: $SERVER_PY (won't connect)"
done

ok "Generated .mcp.json (paths substituted, JSON valid)"

# ─── Step 4: .env from template (if missing) ────────────────────
step "4/6 Configuring .env"

ENV_TEMPLATE=""
if [ -f "$PROJECT_ROOT/templates/env.template" ]; then
  ENV_TEMPLATE="$PROJECT_ROOT/templates/env.template"
elif [ -f "$PROJECT_ROOT/templates/.env.example" ]; then
  ENV_TEMPLATE="$PROJECT_ROOT/templates/.env.example"
fi

if [ -f "$PROJECT_ROOT/.env" ]; then
  ok ".env already exists (not overwriting)"
elif [ -n "$ENV_TEMPLATE" ]; then
  cp "$ENV_TEMPLATE" "$PROJECT_ROOT/.env"
  warn ".env created from $(basename "$ENV_TEMPLATE") — fill in your tokens before using the brain"
else
  warn "No env template found in templates/. Skipping .env creation."
fi

# ─── Step 5: Validate .claude/settings.json portability ─────────
step "5/6 Validating .claude/settings.json"

SETTINGS="$PROJECT_ROOT/.claude/settings.json"
if [ ! -f "$SETTINGS" ]; then
  warn "$SETTINGS missing — hooks won't fire."
else
  # Reject any literal absolute paths to /Users/... or /home/... in the hooks section.
  # Hook commands should use $CLAUDE_PROJECT_DIR (set by Claude Code at runtime).
  if grep -E '"command":[[:space:]]*"[^"]*(/Users/|/home/)' "$SETTINGS" >/dev/null 2>&1; then
    warn "Found absolute home-style paths in settings.json hook commands."
    warn "  Hooks should use \$CLAUDE_PROJECT_DIR instead. Edit $SETTINGS."
  else
    ok "settings.json hook commands look portable"
  fi
fi

# ─── Step 6: Permissions ────────────────────────────────────────
step "6/6 Setting executable bits"

chmod +x "$PROJECT_ROOT"/scripts/*.sh 2>/dev/null || true
chmod +x "$PROJECT_ROOT"/.claude/hooks/*.sh 2>/dev/null || true
ok "Executable bits set on scripts/ and .claude/hooks/"

# ─── Done ───────────────────────────────────────────────────────
echo ""
echo "╔══════════════════════════════════════════════════════════════╗"
echo -e "║   ${G}✅ Phase 0 install complete${X}                                   ║"
echo "╚══════════════════════════════════════════════════════════════╝"
echo ""
echo "Next steps:"
echo ""
echo "  1. Fill .env with your tokens (if not already):"
echo "       \$EDITOR $PROJECT_ROOT/.env"
echo ""
echo "  2. Restart Claude Code (Cmd+Q + reopen) so it picks up the new"
echo "     .mcp.json with substituted paths."
echo ""
echo "  3. Verify MCP servers connected:"
echo "       claude mcp list"
echo ""
echo "  4. (Stack-specific) — build KB index if applicable:"
echo "       scripts/setup.sh    # legacy stack-specific bootstrap (qa-orchestra + KB)"
echo ""
echo "  5. (Optional) Install community sub-agents:"
echo "       git clone https://github.com/lst97/claude-code-sub-agents /tmp/lst97"
echo "       cp /tmp/lst97/agents/*.md ~/.claude/agents/"
echo ""
