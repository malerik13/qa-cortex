#!/usr/bin/env python3
"""
slack-prepare-analyze.py — Pre-process raw JSONL scrape into analyzable chunks.

Why: `trading-dev-team` has ~7500 messages. A single subagent call with all that
as input will OOM its context window. We chunk per channel into 2500-message
chunks (approx 30k tokens each — safe for Sonnet subagents).

Also filters noise:
  - drops messages with only emoji / <3 chars
  - drops messages that are just :reaction: or GIF links
  - drops bot messages (Google Drive, Calendar, etc.) unless they contain URLs
    referring to YouTrack or docs
  - preserves threaded messages even if parent looks empty (they carry decisions)

Output: kb_cache/slack_chunks/<channel>__part{N}.md (markdown, analyzer-ready).
"""
from __future__ import annotations

import json
import re
import sys
from pathlib import Path
from collections import defaultdict

PLUGIN_ROOT = Path(__file__).resolve().parent.parent
SRC_DIR = PLUGIN_ROOT / "kb_cache" / "slack_raw"
OUT_DIR = PLUGIN_ROOT / "kb_cache" / "slack_chunks"
OUT_DIR.mkdir(parents=True, exist_ok=True)

# Tuning
CHUNK_MESSAGES = 2500       # messages per chunk
MIN_TEXT_LEN   = 4          # drop messages under this length
DROP_PATTERNS  = [
    re.compile(r"^:[\w_+\-]+:$"),              # pure single emoji
    re.compile(r"^https://\S+\.(gif|png|jpg|jpeg)$"),  # bare image/gif link
    re.compile(r"^<https://\S+>$"),             # bare link wrapped
]
BOT_PASS_PATTERNS = [
    re.compile(r"youtrack\.[company]\.io|TRD-\d+", re.I),
    re.compile(r"docs\.google\.com|sheets\.google\.com|drive\.google\.com", re.I),
]


def keep(msg: dict) -> bool:
    text = (msg.get("text") or "").strip()
    if len(text) < MIN_TEXT_LEN:
        return False
    for p in DROP_PATTERNS:
        if p.match(text):
            return False
    # Bot-like senders: only keep if they reference our systems
    user = msg.get("user", "")
    if user in {"Slackbot", "Google Calendar", "Google Drive"}:
        if not any(p.search(text) for p in BOT_PASS_PATTERNS):
            return False
    return True


def ts_to_date(ts: str) -> str:
    try:
        import datetime
        return datetime.datetime.utcfromtimestamp(float(ts)).strftime("%Y-%m-%d %H:%M")
    except Exception:
        return "?"


def format_message(msg: dict) -> str:
    date = ts_to_date(msg.get("ts", ""))
    user = msg.get("user", "?")
    kind = msg.get("kind", "root")
    prefix = "    ↳" if kind == "thread_reply" else ""
    txt = (msg.get("text") or "").replace("\n", " ").strip()
    reactions = msg.get("reactions") or []
    rx = f"  ({', '.join(':' + r + ':' for r in reactions)})" if reactions else ""
    return f"{prefix} [{date}] @{user}: {txt}{rx}"


def process_channel(jsonl_path: Path):
    messages_by_thread: dict[str, list[dict]] = defaultdict(list)
    root_order: list[str] = []

    with open(jsonl_path, encoding="utf-8") as f:
        for line in f:
            try:
                m = json.loads(line)
            except json.JSONDecodeError:
                continue
            if not keep(m):
                continue
            if m.get("kind") == "root":
                thread_key = m.get("ts") or f"_{len(root_order)}"
                messages_by_thread[thread_key].append(m)
                root_order.append(thread_key)
            else:
                thread_key = m.get("thread_ts") or ""
                messages_by_thread[thread_key].append(m)

    # Render conversations (each root + its thread replies together)
    lines = []
    chunk_idx = 1
    current_count = 0
    channel = jsonl_path.stem

    def flush():
        nonlocal chunk_idx, lines, current_count
        if not lines:
            return
        out = OUT_DIR / f"{channel}__part{chunk_idx:02d}.md"
        header = f"# Slack channel: #{channel}\n\n"
        header += f"Chunk {chunk_idx}. Messages: {current_count}.\n\n"
        header += "Format: `[YYYY-MM-DD HH:MM] @user: message`. Thread replies indented with `↳`.\n\n---\n\n"
        out.write_text(header + "\n".join(lines), encoding="utf-8")
        print(f"  → {out.name} ({current_count} msgs, {out.stat().st_size // 1024} KB)")
        chunk_idx += 1
        lines = []
        current_count = 0

    for key in root_order:
        conv = messages_by_thread.get(key, [])
        conv.sort(key=lambda m: float(m.get("ts") or 0))
        for m in conv:
            lines.append(format_message(m))
            current_count += 1
        lines.append("")  # blank line between conversations
        if current_count >= CHUNK_MESSAGES:
            flush()

    flush()


def main():
    jsonl_files = sorted(SRC_DIR.glob("*.jsonl"))
    if not jsonl_files:
        print(f"No JSONL files in {SRC_DIR}"); return 1
    print(f"Processing {len(jsonl_files)} channels...")
    for p in jsonl_files:
        with open(p) as f:
            n = sum(1 for _ in f)
        print(f"\n[{p.stem}] {n} raw records")
        process_channel(p)
    print("\n✅ Done. Chunks in kb_cache/slack_chunks/")


if __name__ == "__main__":
    sys.exit(main() or 0)
