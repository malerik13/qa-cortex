#!/usr/bin/env bash
# ═══════════════════════════════════════════════════════════════
#  QA Brain — stack-specific onboarding
# ═══════════════════════════════════════════════════════════════
#  Usage:
#      ./scripts/setup.sh
#
#  Idempotent — safe to re-run.
#  Prints each step, stops on first error.
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

PROJECT_DIR="$(cd "$(dirname "$0")/.." && pwd)"
cd "$PROJECT_DIR"

echo ""
echo "╔══════════════════════════════════════════════════════════════╗"
echo "║   QA Brain — Stack-specific Onboarding                       ║"
echo "╚══════════════════════════════════════════════════════════════╝"
echo "Project root: $PROJECT_DIR"

# ─── Step 1: Prerequisites ──────────────────────────────────────
step "1/7 Checking prerequisites"

command -v python3 >/dev/null || fail "python3 not found. Install Python 3.10+."
PY_OK=$(python3 -c "import sys; print(1 if sys.version_info >= (3, 10) else 0)")
PY_VER=$(python3 -c "import sys; print(f'{sys.version_info.major}.{sys.version_info.minor}')")
[ "$PY_OK" = "1" ] || fail "Python $PY_VER is too old. Need Python 3.10+ (MCP SDK requirement)."
ok "python3 found ($PY_VER)"

command -v git >/dev/null || fail "git not found. Install git."
ok "git found"

if ! command -v claude >/dev/null; then
  warn "Claude Code CLI not found."
  echo "    Install with: npm install -g @anthropic-ai/claude-code"
  echo "    (or from https://docs.claude.com/claude-code)"
  read -p "    Continue without Claude Code? [y/N] " reply
  [[ "$reply" =~ ^[Yy]$ ]] || fail "Aborted."
else
  ok "claude CLI found ($(claude --version 2>/dev/null || echo 'version unknown'))"
fi

# ─── Step 2: Python venv ────────────────────────────────────────
step "2/7 Setting up Python virtual environment"

if [ ! -d .venv ]; then
  python3 -m venv .venv
  ok "Created .venv"
else
  ok ".venv already exists"
fi

# shellcheck disable=SC1091
source .venv/bin/activate

pip install --quiet --upgrade pip
pip install --quiet -r requirements.txt
ok "Installed Python dependencies"

# ─── Step 3: .env file ──────────────────────────────────────────
step "3/7 Configuring .env"

if [ ! -f .env ]; then
  cp templates/env.template .env
  warn ".env created from template."
  echo ""
  echo "    Next: open .env and paste your YouTrack token."
  echo "    Get one: your YouTrack instance → Profile → Authentication → New token"
  echo ""
  read -p "    Press Enter once .env is filled in..."
fi

# Validate .env has a token
if grep -q "PASTE_YOUR_TOKEN_HERE" .env; then
  fail ".env still has PASTE_YOUR_TOKEN_HERE. Edit it and re-run setup."
fi
ok ".env configured"

# ─── Step 4a: Install qa-orchestra (foundation) ─────────────────
step "4a/7 Installing qa-orchestra plugin (foundation, MIT)"

if command -v claude >/dev/null; then
  # Add wshobson/agents marketplace (qa-orchestra hosted there)
  if claude plugin marketplace list 2>&1 | grep -q 'claude-code-workflows'; then
    ok "claude-code-workflows marketplace already added"
  else
    info "Adding claude-code-workflows marketplace..."
    claude plugin marketplace add wshobson/agents 2>&1 | tail -2 || warn "marketplace add failed"
  fi

  # Install qa-orchestra
  if claude plugin list 2>&1 | grep -q 'qa-orchestra'; then
    ok "qa-orchestra already installed"
  else
    info "Installing qa-orchestra..."
    claude plugin install 'qa-orchestra@claude-code-workflows' 2>&1 | tail -2 || warn "qa-orchestra install failed"
  fi

  # Apply manifest patch + sparse-checkout fix (REQUIRED — Anasss's manifest
  # fails Claude Code validation by default, see scripts/qa-orchestra-fix.sh)
  if [[ -x "$PROJECT_DIR/scripts/qa-orchestra-fix.sh" ]]; then
    info "Patching qa-orchestra manifest + sparse-checkout..."
    "$PROJECT_DIR/scripts/qa-orchestra-fix.sh" 2>&1 | grep -E '✓|⚠|❌' || true
    ok "qa-orchestra patched"
  else
    warn "qa-orchestra-fix.sh missing — qa-orchestra may fail to load"
  fi
else
  warn "Skipping qa-orchestra install (claude CLI missing)."
fi

# ─── Step 4b: Install this plugin (extension) ───────────────────
step "4b/7 Installing this plugin (extension layer)"

if command -v claude >/dev/null; then
  if claude plugin install "$PROJECT_DIR" 2>&1 | tee /tmp/claude-plugin-install.log | tail -2; then
    ok "Plugin installed"
  else
    warn "Plugin install failed (see /tmp/claude-plugin-install.log). Continuing — can be retried."
  fi
else
  warn "Skipping plugin install (claude CLI missing)."
fi

# ─── Step 5: Build KB index ─────────────────────────────────────
step "5/7 Building knowledge base index"

if python3 scripts/update-kb.py; then
  ok "KB index built"
else
  fail "KB build failed. Check .env token or network, then re-run."
fi

# ─── Step 6: Build relationship graph ───────────────────────────
step "6/7 Building relationship graph"

python3 scripts/build-graph.py
ok "Graph built"

# ─── Step 7: Verify ─────────────────────────────────────────────
step "7/7 Running verification"

if python3 scripts/verify.py; then
  ok "All checks passed"
else
  fail "Verification failed. Run: python3 scripts/doctor.py"
fi

# ─── Done ───────────────────────────────────────────────────────
echo ""
echo "╔══════════════════════════════════════════════════════════════╗"
echo -e "║   ${G}✅ Setup complete.${X}                                              ║"
echo "╚══════════════════════════════════════════════════════════════╝"
echo ""
echo "Next steps:"
echo "  1. Open Claude Code in this folder:   claude"
echo "  2. Try a command:                     /explore 2FA"
echo "  3. Or search a ticket:                /related {TICKET_PREFIX}-XXXXX"
echo "  4. Full guide:                        README.md"
echo ""
