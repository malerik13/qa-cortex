#!/usr/bin/env python3
"""
doctor.py — Diagnose why the setup isn't working, and suggest fixes.

Run when verify.py fails. Each diagnostic prints:
  - what it checked
  - what it found
  - a concrete fix command (or next step)
"""
from __future__ import annotations

import os
import shutil
import subprocess
import sys
from pathlib import Path

PLUGIN_ROOT = Path(__file__).resolve().parent.parent

try:
    from dotenv import load_dotenv
    load_dotenv(PLUGIN_ROOT / ".env")
except ImportError:
    pass


def section(title: str):
    print(f"\n── {title} " + "─" * (68 - len(title)))


def ok(msg: str):
    print(f"  ✓ {msg}")


def problem(msg: str, fix: str):
    print(f"  ✗ {msg}")
    print(f"    → Fix: {fix}")


def main():
    print("[COMPANY] QA Assistant — doctor")
    print(f"Project root: {PLUGIN_ROOT}")

    # 1. Python + deps
    section("Python environment")
    v = sys.version_info
    if (v.major, v.minor) >= (3, 10):
        ok(f"Python {v.major}.{v.minor}.{v.micro}")
    else:
        problem(f"Python {v.major}.{v.minor} too old (MCP SDK needs 3.10+)",
                "rm -rf .venv && python3 -m venv .venv && .venv/bin/pip install -r requirements.txt")

    for pkg in ("requests", "dotenv", "mcp"):
        try:
            __import__(pkg)
            ok(f"{pkg} importable")
        except ImportError:
            problem(f"{pkg} not installed", "source .venv/bin/activate && pip install -r requirements.txt")

    # 2. .env
    section(".env file")
    env_path = PLUGIN_ROOT / ".env"
    if not env_path.exists():
        problem(".env missing", "cp templates/env.template .env; edit .env")
    else:
        ok(".env exists")
        url = os.getenv("YOUTRACK_BASE_URL", "")
        tok = os.getenv("YOUTRACK_TOKEN", "")
        if not url:
            problem("YOUTRACK_BASE_URL missing", "edit .env, set YOUTRACK_BASE_URL=https://[your-domain]")
        elif url:
            ok(f"YOUTRACK_BASE_URL = {url}")
        if not tok or "PASTE" in tok:
            problem("YOUTRACK_TOKEN missing/placeholder", "YouTrack → Profile → Authentication → New token → paste into .env")
        elif tok:
            ok(f"YOUTRACK_TOKEN present ({tok[:12]}…)")

    # 3. Connectivity
    section("YouTrack connectivity")
    try:
        import requests
        url = os.getenv("YOUTRACK_BASE_URL", "").rstrip("/")
        tok = os.getenv("YOUTRACK_TOKEN", "")
        if url and tok:
            r = requests.get(f"{url}/api/users/me?fields=login",
                             headers={"Authorization": f"Bearer {tok}", "Accept": "application/json"},
                             timeout=10)
            if r.status_code == 401:
                problem("401 Unauthorized", "regenerate token in YouTrack, update .env")
            elif r.ok:
                ok(f"authenticated as {r.json().get('login', '?')}")
            else:
                problem(f"HTTP {r.status_code}", "check VPN / network / corporate firewall")
    except Exception as e:
        problem(f"request failed: {e}", "check network, try curl $YOUTRACK_BASE_URL/api/users/me")

    # 4. KB files
    section("Knowledge base")
    idx = PLUGIN_ROOT / "knowledge_base" / "user_stories.json"
    if idx.exists():
        kb = idx.stat().st_size // 1024
        ok(f"user_stories.json ({kb} KB)")
    else:
        problem("user_stories.json missing", ".venv/bin/python scripts/update-kb.py")

    graph = PLUGIN_ROOT / "kb_cache" / "relationship_graph.json"
    if graph.exists():
        kb = graph.stat().st_size // 1024
        ok(f"relationship_graph.json ({kb} KB)")
    else:
        problem("relationship_graph.json missing", ".venv/bin/python scripts/build-graph.py")

    # 5. Claude CLI
    section("Claude Code CLI")
    claude_path = shutil.which("claude")
    if claude_path:
        ok(f"claude found at {claude_path}")
        try:
            out = subprocess.run(["claude", "--version"], capture_output=True, text=True, timeout=5)
            ok(f"version: {out.stdout.strip() or '?'}")
        except Exception:
            pass
    else:
        problem("claude CLI not installed", "npm install -g @anthropic-ai/claude-code")

    print("\nDone.")


if __name__ == "__main__":
    main()
