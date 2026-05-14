#!/usr/bin/env python3
"""
verify.py — Post-install verification.

Checks (each one prints PASS/FAIL):
  1. .env exists and has YOUTRACK_TOKEN + YOUTRACK_BASE_URL
  2. YouTrack API responds with the token
  3. A known anchor ticket ({TICKET_PREFIX}-XXXXX — 2FA UI/UX) is reachable
  4. KB index exists and has >50 stories
  5. Relationship graph exists and has nodes/edges
  6. MCP server module imports cleanly

Exit code: 0 = all green, 1 = any red.
"""
from __future__ import annotations

import importlib.util
import json
import os
import sys
from pathlib import Path

PLUGIN_ROOT = Path(__file__).resolve().parent.parent

try:
    from dotenv import load_dotenv
    load_dotenv(PLUGIN_ROOT / ".env")
except ImportError:
    pass

GREEN = "\033[0;32m" if sys.stdout.isatty() else ""
RED   = "\033[0;31m" if sys.stdout.isatty() else ""
DIM   = "\033[2m"    if sys.stdout.isatty() else ""
RESET = "\033[0m"    if sys.stdout.isatty() else ""

ANCHOR_TICKET = "{TICKET_PREFIX}-XXXXX"  # 2FA UI/UX unification — stable reference point

results: list[tuple[str, bool, str]] = []


def check(name: str):
    def decorator(fn):
        def wrapper():
            try:
                msg = fn()
                results.append((name, True, msg or ""))
            except Exception as e:
                results.append((name, False, str(e)))
        return wrapper
    return decorator


@check("env vars present")
def _env():
    url = os.getenv("YOUTRACK_BASE_URL", "")
    tok = os.getenv("YOUTRACK_TOKEN", "")
    if not url or not tok:
        raise RuntimeError("YOUTRACK_BASE_URL or YOUTRACK_TOKEN missing")
    if tok.startswith("perm:PASTE"):
        raise RuntimeError("token is still the placeholder — edit .env")
    return f"{url}"


@check("YouTrack API reachable")
def _api():
    import requests
    url = os.getenv("YOUTRACK_BASE_URL", "").rstrip("/")
    tok = os.getenv("YOUTRACK_TOKEN", "")
    r = requests.get(f"{url}/api/users/me?fields=login,fullName",
                     headers={"Authorization": f"Bearer {tok}", "Accept": "application/json"},
                     timeout=10)
    if r.status_code == 401:
        raise RuntimeError("401 Unauthorized — token invalid/expired")
    if not r.ok:
        raise RuntimeError(f"HTTP {r.status_code}")
    data = r.json()
    return f"as {data.get('login', '?')} ({data.get('fullName', '?')})"


@check("anchor ticket reachable")
def _anchor():
    import requests
    url = os.getenv("YOUTRACK_BASE_URL", "").rstrip("/")
    tok = os.getenv("YOUTRACK_TOKEN", "")
    r = requests.get(f"{url}/api/issues/{ANCHOR_TICKET}?fields=idReadable,summary",
                     headers={"Authorization": f"Bearer {tok}", "Accept": "application/json"},
                     timeout=10)
    if not r.ok:
        raise RuntimeError(f"{ANCHOR_TICKET} not reachable (HTTP {r.status_code})")
    data = r.json()
    return f"{data.get('idReadable')}: {(data.get('summary') or '')[:60]}"


@check("KB index built (≥50 stories)")
def _index():
    path = PLUGIN_ROOT / "knowledge_base" / "user_stories.json"
    if not path.exists():
        raise RuntimeError("user_stories.json missing — run scripts/update-kb.py")
    with open(path, encoding="utf-8") as f:
        data = json.load(f)
    n = len(data.get("stories", []))
    if n < 50:
        raise RuntimeError(f"only {n} stories indexed — expected ≥50")
    return f"{n} stories"


@check("relationship graph built")
def _graph():
    path = PLUGIN_ROOT / "kb_cache" / "relationship_graph.json"
    if not path.exists():
        raise RuntimeError("graph missing — run scripts/build-graph.py")
    with open(path, encoding="utf-8") as f:
        data = json.load(f)
    n, e = len(data.get("nodes", {})), len(data.get("edges", []))
    return f"{n} nodes, {e} edges"


@check("MCP server imports cleanly")
def _mcp():
    server_path = PLUGIN_ROOT / "mcp" / "youtrack" / "server.py"
    if not server_path.exists():
        raise RuntimeError("mcp/youtrack/server.py missing")
    spec = importlib.util.spec_from_file_location("_yt_server", server_path)
    mod = importlib.util.module_from_spec(spec)
    # Just import — don't run main()
    spec.loader.exec_module(mod)  # type: ignore
    if not hasattr(mod, "server"):
        raise RuntimeError("MCP server missing 'server' object")
    return "ok"


def main() -> int:
    print("Running verification checks...\n")

    _env()
    _api()
    _anchor()
    _index()
    _graph()
    _mcp()

    pad = max(len(name) for name, _, _ in results)
    all_ok = True
    for name, ok, msg in results:
        status = f"{GREEN}PASS{RESET}" if ok else f"{RED}FAIL{RESET}"
        detail = f" {DIM}→ {msg}{RESET}" if msg else ""
        print(f"  [{status}] {name:<{pad}}{detail}")
        if not ok:
            all_ok = False

    print()
    if all_ok:
        print(f"{GREEN}All checks passed.{RESET}")
        return 0
    else:
        print(f"{RED}Some checks failed. Run: python3 scripts/doctor.py{RESET}")
        return 1


if __name__ == "__main__":
    sys.exit(main())
