#!/usr/bin/env bash
# ═══════════════════════════════════════════════════════════════
#  qa-orchestra plugin fix — manifest patch + sparse-checkout disable
# ═══════════════════════════════════════════════════════════════
#  Why this script exists (per 2026-05-06 diagnosis):
#
#  qa-orchestra is hosted at github.com/Anasss/qa-orchestra
#  but its plugin.json fails Claude Code's manifest validator:
#
#     ✘ Plugin qa-orchestra has an invalid manifest file
#     Validation errors:
#        - agents: Invalid input
#        - Unrecognized key: "screenshots"
#
#  Plus Claude Code installs plugins via sparse-checkout (12% of
#  files) — actual agent files in .claude/agents/ aren't materialised.
#
#  This script:
#    1. Disables sparse-checkout so all files are present
#    2. Removes "screenshots" + "agents" fields from manifest
#    3. Copies .claude/agents/ → agents/ (Claude Code's auto-discovery
#       expects plain agents/ dir, not hidden one)
#
#  Idempotent — safe to re-run.
# ═══════════════════════════════════════════════════════════════

set -euo pipefail

# ─── locate qa-orchestra cache ──────────────────────────────────
CACHE_PARENT="$HOME/.claude/plugins/cache/claude-code-workflows/qa-orchestra"

if [[ ! -d "$CACHE_PARENT" ]]; then
  echo "❌ qa-orchestra not installed yet."
  echo "   Run first: claude plugin install qa-orchestra@claude-code-workflows"
  exit 1
fi

# pick the highest version dir
VERSION=$(ls "$CACHE_PARENT" | sort -V | tail -1)
CACHE="$CACHE_PARENT/$VERSION"

echo "→ patching qa-orchestra v$VERSION at $CACHE"

# ─── 1. disable sparse-checkout ─────────────────────────────────
if [[ -d "$CACHE/.git" ]]; then
  cd "$CACHE"
  if git config core.sparseCheckout 2>/dev/null | grep -q true; then
    echo "  ✓ disabling sparse-checkout"
    git sparse-checkout disable
    git checkout HEAD -- .
  else
    echo "  ✓ sparse-checkout already disabled"
  fi
  cd - >/dev/null
fi

# ─── 2. patch manifest ──────────────────────────────────────────
MANIFEST="$CACHE/.claude-plugin/plugin.json"
if [[ ! -f "$MANIFEST" ]]; then
  echo "❌ manifest not found at $MANIFEST"
  exit 1
fi

python3 << PY
import json
from pathlib import Path
p = Path("$MANIFEST")
d = json.loads(p.read_text())
changed = False
if "screenshots" in d:
    d.pop("screenshots", None)
    changed = True
    print("  ✓ removed 'screenshots' field")
if "agents" in d:
    d.pop("agents", None)
    changed = True
    print("  ✓ removed 'agents' field (Claude Code auto-discovers from agents/)")
if changed:
    p.write_text(json.dumps(d, indent=2))
else:
    print("  ✓ manifest already patched")
PY

# ─── 3. mirror .claude/agents/ → agents/ ────────────────────────
HIDDEN="$CACHE/.claude/agents"
PUBLIC="$CACHE/agents"

if [[ -d "$HIDDEN" && ! -d "$PUBLIC" ]]; then
  cp -R "$HIDDEN" "$PUBLIC"
  echo "  ✓ copied 10 agents to agents/ (auto-discovery dir)"
elif [[ -d "$PUBLIC" ]]; then
  echo "  ✓ agents/ already exists"
else
  echo "  ⚠ no .claude/agents/ found — skipping"
fi

# ─── verify ─────────────────────────────────────────────────────
echo
echo "→ verify"
claude plugin list 2>&1 | grep -A2 'qa-orchestra' | head -5
echo
echo "✓ qa-orchestra patched. Restart Claude Code to apply."
