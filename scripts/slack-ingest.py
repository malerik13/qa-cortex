#!/usr/bin/env python3
"""
slack-ingest.py — One-time scrape of Slack dialogs you have access to.

Output: kb_cache/slack_raw/<channel_name>.jsonl (one message per line)

Then run scripts/slack-analyze.py to distill insights into
knowledge_base/slack_insights.md (human-review gate included).

Requires SLACK_USER_TOKEN (xoxp-...) in .env with scopes:
  channels:history, channels:read
  groups:history,   groups:read
  im:history,       im:read
  mpim:history,     mpim:read
  users:read

Usage:
  .venv/bin/python scripts/slack-ingest.py                   # all accessible, last 180 days
  .venv/bin/python scripts/slack-ingest.py --days 365        # custom window
  .venv/bin/python scripts/slack-ingest.py --channel qa-chat # one channel only
"""
from __future__ import annotations

import argparse
import json
import os
import sys
import time
from pathlib import Path

PLUGIN_ROOT = Path(__file__).resolve().parent.parent

try:
    from dotenv import load_dotenv
    load_dotenv(PLUGIN_ROOT / ".env")
except ImportError:
    sys.stderr.write("Missing python-dotenv. Run: pip install -r requirements.txt\n")
    sys.exit(1)

import requests

TOKEN = os.getenv("SLACK_USER_TOKEN", "")
OUT_DIR = PLUGIN_ROOT / "kb_cache" / "slack_raw"
API = "https://slack.com/api"


def slack_call(method: str, params: dict, post: bool = False) -> dict:
    headers = {"Authorization": f"Bearer {TOKEN}"}
    for _ in range(3):
        r = (requests.post if post else requests.get)(
            f"{API}/{method}", headers=headers, params=params, timeout=20
        )
        data = r.json()
        if data.get("ok"):
            return data
        if data.get("error") == "ratelimited":
            wait = int(r.headers.get("Retry-After", "2"))
            time.sleep(wait)
            continue
        sys.stderr.write(f"slack error ({method}): {data.get('error')}\n")
        return data
    return {"ok": False, "error": "exhausted_retries"}


def list_conversations() -> list[dict]:
    conversations = []
    cursor = ""
    while True:
        data = slack_call("conversations.list", {
            "types": "public_channel,private_channel,mpim,im",
            "limit": 200,
            "cursor": cursor,
        })
        if not data.get("ok"):
            break
        conversations.extend(data.get("channels", []))
        cursor = data.get("response_metadata", {}).get("next_cursor", "")
        if not cursor:
            break
    return conversations


def fetch_history(channel_id: str, oldest: float) -> list[dict]:
    messages = []
    cursor = ""
    while True:
        params = {"channel": channel_id, "limit": 200, "oldest": str(oldest)}
        if cursor:
            params["cursor"] = cursor
        data = slack_call("conversations.history", params)
        if not data.get("ok"):
            break
        messages.extend(data.get("messages", []))
        cursor = data.get("response_metadata", {}).get("next_cursor", "")
        if not cursor:
            break
        time.sleep(0.2)
    return messages


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--days", type=int, default=180)
    ap.add_argument("--channel", help="Limit to one channel name (without #)")
    args = ap.parse_args()

    if not TOKEN:
        sys.stderr.write("SLACK_USER_TOKEN not set in .env\n")
        return 1

    OUT_DIR.mkdir(parents=True, exist_ok=True)
    oldest = time.time() - args.days * 86400

    print(f"Window: last {args.days} days (oldest ts = {oldest:.0f})")
    print("Listing conversations...")
    convs = list_conversations()
    print(f"  {len(convs)} conversations accessible\n")

    written = 0
    for c in convs:
        name = c.get("name") or c.get("user") or c["id"]
        if args.channel and args.channel != name:
            continue

        print(f"  → {name} ({c['id']})", end=" ")
        msgs = fetch_history(c["id"], oldest)
        if not msgs:
            print("(0)")
            continue

        out_path = OUT_DIR / f"{name}.jsonl"
        with open(out_path, "w", encoding="utf-8") as f:
            for m in msgs:
                f.write(json.dumps({
                    "channel":   name,
                    "ts":        m.get("ts"),
                    "user":      m.get("user") or m.get("bot_id"),
                    "text":      m.get("text", ""),
                    "thread_ts": m.get("thread_ts"),
                }, ensure_ascii=False) + "\n")
        print(f"({len(msgs)} msgs)")
        written += len(msgs)

    print(f"\n✅ Wrote {written} messages → {OUT_DIR}")
    print("\nNext: open Claude Code and ask:")
    print("  'Analyze kb_cache/slack_raw/ and propose updates to knowledge_base/slack_insights.md'")
    print("  (Claude will show a diff before writing — human-review gate.)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
