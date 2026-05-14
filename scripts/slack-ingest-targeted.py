#!/usr/bin/env python3
"""
slack-ingest-targeted.py — Targeted Slack scrape for [COMPANY] QA KB enrichment.

Scrapes specific channels + one DM, with 180-day window, INCLUDING thread replies
(most decision context lives in threads).

Output: kb_cache/slack_raw/<channel_name>.jsonl (one message per line).

Also resolves user IDs to display names, so downstream analysis reads naturally.
"""
from __future__ import annotations

import json
import os
import sys
import time
from pathlib import Path

PLUGIN_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PLUGIN_ROOT))

try:
    from dotenv import load_dotenv
    load_dotenv(PLUGIN_ROOT / ".env")
except ImportError:
    print("ERROR: pip install python-dotenv requests", file=sys.stderr); sys.exit(1)

import requests

TOKEN = os.environ["SLACK_USER_TOKEN"]
OUT_DIR = PLUGIN_ROOT / "kb_cache" / "slack_raw"
OUT_DIR.mkdir(parents=True, exist_ok=True)

HEADERS = {"Authorization": f"Bearer {TOKEN}"}
API = "https://slack.com/api"

# ─── Target set ──────────────────────────────────────────────────────────────
TARGETS_CHANNELS = [
    "trading-dev-team",
    "trading-dev-team-internal",
    "trading-testing",
    "trading-qa-peer-review",
    "trading-testing-grooming",
]
TARGET_MPDM_MEMBERS = {"Maryna Melekhavets", "Igor Makushynsky", "Semen Kazantsev",
                       "Mikhail Dolgalev", "Ekaterina Nikitina"}
TARGET_DM_USER = "Ekaterina Nikitina"

WINDOW_DAYS = 180
OLDEST = time.time() - WINDOW_DAYS * 86400


# ─── Slack helpers ───────────────────────────────────────────────────────────

def sl_call(method: str, params: dict, post=False) -> dict:
    for attempt in range(5):
        r = (requests.post if post else requests.get)(
            f"{API}/{method}", headers=HEADERS, params=params, timeout=30
        )
        if r.status_code == 429:
            wait = int(r.headers.get("Retry-After", "3"))
            print(f"  rate limited, sleep {wait}s", file=sys.stderr)
            time.sleep(wait); continue
        try:
            d = r.json()
        except Exception:
            time.sleep(2); continue
        if d.get("ok") or d.get("error") in ("not_in_channel", "channel_not_found"):
            return d
        if d.get("error") == "ratelimited":
            time.sleep(3); continue
        return d
    return {"ok": False, "error": "exhausted"}


# ─── User name cache ─────────────────────────────────────────────────────────

_user_cache: dict[str, str] = {}

def user_name(uid: str) -> str:
    if not uid:
        return "?"
    if uid in _user_cache:
        return _user_cache[uid]
    d = sl_call("users.info", {"user": uid})
    if d.get("ok"):
        p = d["user"].get("profile", {})
        name = p.get("display_name_normalized") or p.get("real_name_normalized") or uid
    else:
        name = uid
    _user_cache[uid] = name
    return name


def resolve_users_in_message(text: str) -> str:
    """Replace <@UXXXX> with @name in message body."""
    import re
    def repl(m):
        uid = m.group(1)
        return "@" + user_name(uid)
    return re.sub(r"<@([UW][A-Z0-9]+)>", repl, text or "")


# ─── Target discovery ────────────────────────────────────────────────────────

def discover_targets() -> list[dict]:
    """Return list of {name, id, type, window_oldest}."""
    print("Discovering conversations...")
    all_convs = []
    cursor = ""
    while True:
        params = {"types": "public_channel,private_channel,mpim,im", "limit": 200}
        if cursor:
            params["cursor"] = cursor
        d = sl_call("conversations.list", params)
        if not d.get("ok"):
            print("ERROR:", d.get("error")); break
        all_convs.extend(d.get("channels", []))
        cursor = d.get("response_metadata", {}).get("next_cursor", "")
        if not cursor:
            break
        time.sleep(0.2)

    name_to_conv = {c.get("name"): c for c in all_convs if c.get("name")}

    targets = []

    # Named channels
    for name in TARGETS_CHANNELS:
        c = name_to_conv.get(name)
        if c:
            targets.append({"name": name, "id": c["id"], "type": "channel"})
        else:
            print(f"  WARN: channel '{name}' not found")

    # Group DM (mpim) — match by member names
    for c in all_convs:
        if not c.get("is_mpim"):
            continue
        m = sl_call("conversations.members", {"channel": c["id"], "limit": 100})
        if not m.get("ok"):
            continue
        member_names = {user_name(uid) for uid in m.get("members", [])}
        if TARGET_MPDM_MEMBERS.issubset(member_names):
            targets.append({"name": "group-dm-qa-team", "id": c["id"], "type": "mpim"})
            break

    # 1:1 DM with Ekaterina
    for c in all_convs:
        if not c.get("is_im"):
            continue
        uid = c.get("user")
        if user_name(uid) == TARGET_DM_USER:
            targets.append({"name": "dm-ekaterina", "id": c["id"], "type": "im"})
            break

    return targets


# ─── Fetch ───────────────────────────────────────────────────────────────────

def fetch_history(channel_id: str) -> list[dict]:
    msgs = []
    cursor = ""
    while True:
        params = {"channel": channel_id, "limit": 200, "oldest": f"{OLDEST:.6f}"}
        if cursor:
            params["cursor"] = cursor
        d = sl_call("conversations.history", params)
        if not d.get("ok"):
            print(f"  history error: {d.get('error')}")
            break
        msgs.extend(d.get("messages", []))
        cursor = d.get("response_metadata", {}).get("next_cursor", "")
        if not cursor:
            break
        time.sleep(0.3)
    return msgs


def fetch_thread(channel_id: str, thread_ts: str) -> list[dict]:
    replies = []
    cursor = ""
    while True:
        params = {"channel": channel_id, "ts": thread_ts, "limit": 200}
        if cursor:
            params["cursor"] = cursor
        d = sl_call("conversations.replies", params)
        if not d.get("ok"):
            break
        replies.extend(d.get("messages", []))
        cursor = d.get("response_metadata", {}).get("next_cursor", "")
        if not cursor:
            break
        time.sleep(0.3)
    # Exclude the parent (first message) — we already have it in history
    return replies[1:] if replies else []


def write_record(f, channel_name: str, m: dict, kind: str):
    f.write(json.dumps({
        "channel":   channel_name,
        "kind":      kind,                    # "root" | "thread_reply"
        "ts":        m.get("ts"),
        "thread_ts": m.get("thread_ts"),
        "user":      user_name(m.get("user") or m.get("bot_id") or ""),
        "text":      resolve_users_in_message(m.get("text", "")),
        "reactions": [r.get("name") for r in m.get("reactions", [])] or None,
        "reply_count": m.get("reply_count", 0),
    }, ensure_ascii=False) + "\n")


# ─── Main ────────────────────────────────────────────────────────────────────

def main():
    targets = discover_targets()
    print(f"\n{len(targets)} targets resolved:")
    for t in targets:
        print(f"  → {t['name']} ({t['type']}, {t['id']})")
    print()

    total_root = 0
    total_reply = 0

    for t in targets:
        out_path = OUT_DIR / f"{t['name']}.jsonl"
        print(f"[{t['name']}] fetching history...", flush=True)

        hist = fetch_history(t["id"])
        n_thread_parents = sum(1 for m in hist if m.get("reply_count", 0) >= 2)
        print(f"[{t['name']}]   {len(hist)} root messages, {n_thread_parents} with threads (≥2 replies)", flush=True)

        with open(out_path, "w", encoding="utf-8") as f:
            replies_count = 0
            for m in hist:
                write_record(f, t["name"], m, "root")
                total_root += 1
                if m.get("reply_count", 0) >= 2 and m.get("ts"):
                    try:
                        replies = fetch_thread(t["id"], m["ts"])
                        for rm in replies:
                            write_record(f, t["name"], rm, "thread_reply")
                            replies_count += 1
                            total_reply += 1
                    except Exception as e:
                        print(f"    thread fetch error at {m.get('ts')}: {e}", flush=True)
            print(f"[{t['name']}]   wrote {len(hist) + replies_count} records → {out_path.name}", flush=True)

    print(f"\n✅ Total: {total_root} root + {total_reply} thread replies = {total_root + total_reply} records")


if __name__ == "__main__":
    main()
