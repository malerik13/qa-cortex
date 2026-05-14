#!/usr/bin/env python3
"""Cleanup orphaned MCP server processes.

See scripts/cleanup-mcp-zombies.sh for context. This is the implementation.
"""
from __future__ import annotations

import os
import signal
import subprocess
import sys
import time

# Patterns to identify our MCP server subprocess command lines.
SERVER_PATTERNS = [
    "mcp/youtrack/server.py",
    "mcp/allure/server.py",
]

# Estimated RAM per orphaned python server — for the report only.
EST_RAM_MB_PER_PROC = 50


def find_mcp_processes() -> list[tuple[int, int, str]]:
    """Return list of (pid, ppid, command) for matching MCP servers."""
    out = subprocess.check_output(["ps", "-axo", "pid,ppid,command"], text=True)
    procs = []
    for line in out.splitlines()[1:]:
        parts = line.strip().split(None, 2)
        if len(parts) < 3:
            continue
        try:
            pid, ppid = int(parts[0]), int(parts[1])
        except ValueError:
            continue
        cmd = parts[2]
        if any(p in cmd for p in SERVER_PATTERNS):
            procs.append((pid, ppid, cmd))
    return procs


def parent_command(ppid: int) -> str:
    """Return parent's command line, empty string if parent is gone."""
    if ppid <= 1:
        return ""  # launchd or invalid
    try:
        out = subprocess.check_output(
            ["ps", "-o", "command=", "-p", str(ppid)],
            text=True,
            stderr=subprocess.DEVNULL,
        )
        return out.strip()
    except subprocess.CalledProcessError:
        return ""


def is_orphan(ppid: int) -> tuple[bool, str]:
    """Decide if an MCP process is orphaned. Returns (is_orphan, reason)."""
    if ppid == 1:
        return True, "parent=launchd"
    parent_cmd = parent_command(ppid)
    if not parent_cmd:
        return True, "parent=gone"
    if "claude" not in parent_cmd.lower():
        return True, f"parent_not_claude (cmd: {parent_cmd[:40]})"
    return False, f"parent=claude (PID {ppid})"


def shorten(cmd: str, length: int = 70) -> str:
    if len(cmd) <= length:
        return cmd
    # Show the tail (most informative part — script path)
    return "…" + cmd[-(length - 1):]


def main() -> int:
    dry_run = "--dry-run" in sys.argv or "-n" in sys.argv
    quiet = "--quiet" in sys.argv or "-q" in sys.argv

    procs = find_mcp_processes()

    if not procs:
        if not quiet:
            print("✓ No MCP server processes found at all.")
        return 0

    orphans = []
    live = []
    for pid, ppid, cmd in procs:
        orphan, reason = is_orphan(ppid)
        if orphan:
            orphans.append((pid, ppid, cmd, reason))
        else:
            live.append((pid, ppid, cmd, reason))

    if not quiet:
        print("── MCP server processes ──")
        print(f"  Total found:           {len(procs)}")
        print(f"  Live (parent=claude):  {len(live)}")
        print(f"  Orphaned (to clean):   {len(orphans)}")
        print()

        if live:
            print("Live (KEPT):")
            for pid, ppid, cmd, reason in live:
                print(f"  PID={pid:<6} PPID={ppid:<6} {shorten(cmd, 60)}")
            print()

        if orphans:
            print("Orphaned:")
            for pid, ppid, cmd, reason in orphans:
                print(f"  PID={pid:<6} PPID={ppid:<6} ({reason})")
                print(f"         {shorten(cmd, 70)}")
            print()

    if not orphans:
        if not quiet:
            print("✓ Nothing to clean.")
        return 0

    if dry_run:
        if not quiet:
            est_ram = len(orphans) * EST_RAM_MB_PER_PROC
            print(f"[dry-run] would kill {len(orphans)} process(es), "
                  f"~{est_ram} MB RAM to be freed")
        return 0

    # ── SIGTERM first (graceful) ──
    if not quiet:
        print(f"→ Sending SIGTERM to {len(orphans)} process(es)...")
    for pid, _, _, _ in orphans:
        try:
            os.kill(pid, signal.SIGTERM)
        except ProcessLookupError:
            pass
        except PermissionError:
            if not quiet:
                print(f"  ⚠ permission denied for PID {pid}")

    time.sleep(2)

    # ── SIGKILL stragglers ──
    survivors = []
    for pid, _, _, _ in orphans:
        try:
            os.kill(pid, 0)  # signal 0 = liveness check, no kill
            survivors.append(pid)
        except ProcessLookupError:
            pass

    killed_kill = 0
    if survivors:
        if not quiet:
            print(f"→ {len(survivors)} survived SIGTERM, sending SIGKILL...")
        for pid in survivors:
            try:
                os.kill(pid, signal.SIGKILL)
                killed_kill += 1
            except ProcessLookupError:
                pass

    est_ram = len(orphans) * EST_RAM_MB_PER_PROC
    if not quiet:
        print()
        print(f"✓ Cleaned {len(orphans)} orphaned MCP process(es) "
              f"(~{est_ram} MB freed)")
        if killed_kill:
            print(f"  ({killed_kill} required SIGKILL — server didn't honor SIGTERM)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
