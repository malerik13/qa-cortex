#!/usr/bin/env python3
"""Brain stats — measure Claude Code context cost per turn.

Layers:
  - "Always-loaded": injected into every API request (CLAUDE.md, MEMORY.md, ...)
  - "On-demand": loaded only when triggered (skills, commands, KB files)

Output: per-file size + estimated tokens, totals, % of context window, deltas vs baseline.

Snapshots are appended to kb_cache/brain-stats/snapshots.jsonl (one JSON per line).
Re-running takes a fresh snapshot automatically; trend uses the last snapshot >24h old.

Token estimate: chars / 4. This is approximate (Anthropic's BPE tokenizer is private).
For mixed RU/EN text, real ratio is ~3.5 chars/token, so we may UNDER-estimate by ~15%.
The estimate is consistent over time, so trends are reliable even if absolute numbers are rough.

Usage:
  brain-stats.py            (show — default)
  brain-stats.py snapshot   (force a fresh snapshot, no display)
  brain-stats.py history    (list past snapshots)
  brain-stats.py json       (machine-readable output)
"""
from __future__ import annotations

import json
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent

# ── tunables ──────────────────────────────────────────────
CHARS_PER_TOKEN = 4               # rough; consistent → trends reliable
CONTEXT_WINDOW = 200_000          # Sonnet 4.5
CLAUDE_MD_SOFT_LIMIT = 15_000     # tokens — project CLAUDE.md soft budget
SKILL_SOFT_LIMIT = 2_000          # tokens — individual skill body
ALWAYS_LOADED_BUDGET = 20_000     # tokens — total static brain target
SNAPSHOT_DEDUP_HOURS = 1          # don't snapshot if last one <1h ago
TREND_DAYS = 7                    # baseline window for "vs N days ago"

# ── what to measure ───────────────────────────────────────
ALWAYS_LOADED: list[tuple[str, Path]] = [
    ("CLAUDE.md (project)",     ROOT / "CLAUDE.md"),
    ("~/.claude/CLAUDE.md",     Path.home() / ".claude" / "CLAUDE.md"),
    (
        "MEMORY.md",
        Path.home() / ".claude" / "projects"
        / "-Users-[test-user]-Documents-[COMPANY]" / "memory" / "MEMORY.md",
    ),
]

ON_DEMAND_GLOBS: list[tuple[str, str]] = [
    ("Skills",         "skills/*/SKILL.md"),
    ("Commands",       "commands/*.md"),
    ("Subagents",      "agents/*.md"),
    ("Knowledge base", "knowledge_base/*.md"),
]

SNAPSHOTS = ROOT / "kb_cache" / "brain-stats" / "snapshots.jsonl"


# ── core ──────────────────────────────────────────────────
def measure(path: Path) -> dict | None:
    if not path.exists():
        return None
    chars = path.stat().st_size
    return {"chars": chars, "tokens": chars // CHARS_PER_TOKEN}


def collect_stats() -> dict:
    stats: dict = {
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "always_loaded": {},
        "on_demand": {},
        "totals": {},
    }

    static_total = 0
    for name, path in ALWAYS_LOADED:
        m = measure(path)
        if m:
            stats["always_loaded"][name] = m
            static_total += m["tokens"]
    stats["totals"]["always_loaded_tokens"] = static_total

    on_demand_total = 0
    on_demand_count = 0
    for category, glob_pattern in ON_DEMAND_GLOBS:
        items: dict = {}
        for f in sorted(ROOT.glob(glob_pattern)):
            rel = f.relative_to(ROOT).as_posix()
            m = measure(f)
            if m:
                items[rel] = m
                on_demand_total += m["tokens"]
                on_demand_count += 1
        stats["on_demand"][category] = items
    stats["totals"]["on_demand_tokens_if_all_loaded"] = on_demand_total
    stats["totals"]["on_demand_files"] = on_demand_count

    return stats


def save_snapshot(stats: dict, force: bool = False) -> bool:
    SNAPSHOTS.parent.mkdir(parents=True, exist_ok=True)
    if not force and SNAPSHOTS.exists():
        snaps = load_snapshots()
        if snaps:
            last_ts = datetime.fromisoformat(snaps[-1]["timestamp"])
            if last_ts.tzinfo is None:
                last_ts = last_ts.replace(tzinfo=timezone.utc)
            age = datetime.now(timezone.utc) - last_ts
            if age < timedelta(hours=SNAPSHOT_DEDUP_HOURS):
                return False
    with SNAPSHOTS.open("a") as f:
        f.write(json.dumps(stats) + "\n")
    return True


def load_snapshots() -> list[dict]:
    if not SNAPSHOTS.exists():
        return []
    return [json.loads(line) for line in SNAPSHOTS.read_text().splitlines() if line.strip()]


def find_baseline(snapshots: list[dict], days_ago: int) -> dict | None:
    """Return the snapshot closest to N days ago, but not the current/most recent one."""
    if len(snapshots) < 2:
        return None
    target = datetime.now(timezone.utc) - timedelta(days=days_ago)
    candidates = snapshots[:-1]  # exclude the just-saved current snapshot
    best = None
    best_delta = None
    for s in candidates:
        ts = datetime.fromisoformat(s["timestamp"])
        if ts.tzinfo is None:
            ts = ts.replace(tzinfo=timezone.utc)
        delta = abs((ts - target).total_seconds())
        if best is None or delta < best_delta:
            best = s
            best_delta = delta
    return best


# ── rendering ─────────────────────────────────────────────
def fmt_delta(curr: int, prev: int | None) -> str:
    if prev is None:
        return ""
    diff = curr - prev
    if diff == 0:
        return "no change"
    sign = "+" if diff > 0 else ""
    pct = (diff / prev * 100) if prev else 0
    icon = "🔺" if diff > 0 else "🔻"
    return f"{sign}{diff:,} ({sign}{pct:.1f}%) {icon}"


def render(stats: dict, baseline: dict | None) -> str:
    out: list[str] = []
    when = datetime.now().strftime("%Y-%m-%d %H:%M")
    out.append(f"🧠 Brain stats — {when}")
    if baseline:
        b_ts = baseline["timestamp"][:10]
        out.append(f"   (trend baseline: snapshot from {b_ts})")
    out.append("")

    # ── Always-loaded ──
    out.append("━━━ Always-loaded (every turn) ━━━")
    out.append("")
    out.append(f"{'File':<38} {'Bytes':>9} {'Tokens':>8}  {'Δ vs baseline':<25}")
    out.append("─" * 84)
    static_total = 0
    for name, m in stats["always_loaded"].items():
        prev = baseline["always_loaded"].get(name) if baseline else None
        delta = fmt_delta(m["tokens"], prev["tokens"] if prev else None)
        out.append(f"{name:<38} {m['chars']:>9,} {m['tokens']:>8,}  {delta}")
        static_total += m["tokens"]
    out.append("─" * 84)
    pct = static_total / CONTEXT_WINDOW * 100
    prev_total = baseline["totals"]["always_loaded_tokens"] if baseline else None
    out.append(
        f"{'TOTAL static':<38} {'':>9} {static_total:>8,}  "
        f"{fmt_delta(static_total, prev_total)}"
    )
    out.append(f"   = {pct:.1f}% of {CONTEXT_WINDOW//1000}K window")
    out.append("")

    # ── On-demand ──
    out.append("━━━ On-demand (loaded only when triggered) ━━━")
    out.append("")
    for cat, items in stats["on_demand"].items():
        if not items:
            continue
        cat_total = sum(m["tokens"] for m in items.values())
        out.append(f"  {cat} — {len(items)} files, total if all loaded: {cat_total:,} tok")
        for path, m in sorted(items.items(), key=lambda x: -x[1]["tokens"]):
            warn = ""
            if cat == "Skills" and m["tokens"] > SKILL_SOFT_LIMIT:
                warn = "  ⚠️ over skill soft limit"
            elif m["tokens"] > 10_000:
                warn = "  ⚠️ never auto-load — grep/Read offset only"
            out.append(f"    {path:<55} {m['tokens']:>7,} tok{warn}")
        out.append("")

    # ── Health ──
    out.append("━━━ Health ━━━")
    out.append("")
    project_md = stats["always_loaded"].get("CLAUDE.md (project)", {}).get("tokens", 0)
    if project_md > CLAUDE_MD_SOFT_LIMIT:
        out.append(
            f"  ⚠️  CLAUDE.md {project_md:,} tok > {CLAUDE_MD_SOFT_LIMIT:,} soft limit "
            "→ migrate verbose sections to knowledge_base/"
        )
    else:
        pct_of_limit = project_md / CLAUDE_MD_SOFT_LIMIT * 100
        out.append(
            f"  ✅ CLAUDE.md {project_md:,} tok "
            f"({pct_of_limit:.0f}% of {CLAUDE_MD_SOFT_LIMIT:,} soft limit)"
        )

    if static_total > ALWAYS_LOADED_BUDGET:
        out.append(f"  ⚠️  Static brain {static_total:,} > {ALWAYS_LOADED_BUDGET:,} budget")
    else:
        out.append(
            f"  ✅ Static brain {static_total:,} tok "
            f"(budget {ALWAYS_LOADED_BUDGET:,})"
        )

    big_skills = [
        (p, m["tokens"])
        for p, m in stats["on_demand"].get("Skills", {}).items()
        if m["tokens"] > SKILL_SOFT_LIMIT
    ]
    if big_skills:
        out.append(f"  ⚠️  Skills over {SKILL_SOFT_LIMIT:,} tok:")
        for p, t in big_skills:
            out.append(f"      {p}: {t:,} tok")
    else:
        out.append(f"  ✅ All skill bodies under {SKILL_SOFT_LIMIT:,} tok")

    huge_kb = [
        (p, m["tokens"])
        for p, m in stats["on_demand"].get("Knowledge base", {}).items()
        if m["tokens"] > 10_000
    ]
    if huge_kb:
        out.append("  ⚠️  KB files too big to auto-load (use grep / Read offset):")
        for p, t in huge_kb:
            out.append(f"      {p}: {t:,} tok")

    # ── Trend recommendations ──
    if baseline:
        out.append("")
        out.append("━━━ Trend ━━━")
        out.append("")
        prev_total = baseline["totals"]["always_loaded_tokens"]
        diff = static_total - prev_total
        if diff > 0:
            pct_growth = diff / prev_total * 100 if prev_total else 0
            out.append(
                f"  Static brain: {prev_total:,} → {static_total:,} "
                f"(+{diff:,} tok, +{pct_growth:.1f}%)"
            )
            # Per-file diffs
            for name, m in stats["always_loaded"].items():
                prev = baseline["always_loaded"].get(name)
                if prev and m["tokens"] - prev["tokens"] > 200:
                    pdiff = m["tokens"] - prev["tokens"]
                    out.append(f"    └─ {name}: +{pdiff:,} tok")
        elif diff < 0:
            out.append(f"  Static brain shrunk by {-diff:,} tok ✂️")
        else:
            out.append("  Static brain unchanged")

    out.append("")
    out.append("━━━ Notes ━━━")
    out.append("  Token estimate: chars/4 (approximate; trend is reliable).")
    out.append(f"  Snapshots: {SNAPSHOTS.relative_to(ROOT)} ({len(load_snapshots())} entries)")

    return "\n".join(out)


def cmd_show() -> None:
    stats = collect_stats()
    save_snapshot(stats)  # auto-snapshot (deduped to 1/hour)
    snapshots = load_snapshots()
    baseline = find_baseline(snapshots, days_ago=TREND_DAYS)
    print(render(stats, baseline))


def cmd_snapshot() -> None:
    stats = collect_stats()
    saved = save_snapshot(stats, force=True)
    if saved:
        print(f"✓ Snapshot saved to {SNAPSHOTS}")
    else:
        print("(no-op)")


def cmd_history() -> None:
    snaps = load_snapshots()
    if not snaps:
        print("No snapshots yet.")
        return
    print(f"{'Timestamp':<28} {'Static tok':>10} {'On-demand tok':>14} {'OD files':>9}")
    print("─" * 65)
    for s in snaps:
        ts = s["timestamp"][:19]
        static = s["totals"]["always_loaded_tokens"]
        od = s["totals"].get("on_demand_tokens_if_all_loaded", 0)
        odf = s["totals"].get("on_demand_files", 0)
        print(f"{ts:<28} {static:>10,} {od:>14,} {odf:>9,}")


def cmd_json() -> None:
    print(json.dumps(collect_stats(), indent=2))


def main() -> None:
    cmd = sys.argv[1] if len(sys.argv) > 1 else "show"
    handlers = {
        "show": cmd_show,
        "snapshot": cmd_snapshot,
        "history": cmd_history,
        "json": cmd_json,
        "help": lambda: print(__doc__),
        "--help": lambda: print(__doc__),
        "-h": lambda: print(__doc__),
    }
    fn = handlers.get(cmd)
    if not fn:
        print(f"Unknown command: {cmd}", file=sys.stderr)
        print(__doc__, file=sys.stderr)
        sys.exit(1)
    fn()


if __name__ == "__main__":
    main()
