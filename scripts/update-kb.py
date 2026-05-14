#!/usr/bin/env python3
"""
update-kb.py — Refresh the local [COMPANY] indexes (User Stories + Bugs).

Fetches User Stories and/or Bugs from YouTrack (project TRD) and rebuilds:
  - knowledge_base/user_stories.json  (existing)
  - knowledge_base/bugs.json          (new)

Idempotent. Safe to run anytime.

Usage:
    .venv/bin/python scripts/update-kb.py                  # both (default)
    .venv/bin/python scripts/update-kb.py --stories-only
    .venv/bin/python scripts/update-kb.py --bugs-only
    .venv/bin/python scripts/update-kb.py --bugs-recent N  # bugs from last N days only
"""
from __future__ import annotations

import argparse
import json
import os
import re
import sys
import time
from pathlib import Path
from urllib.parse import quote

PLUGIN_ROOT = Path(__file__).resolve().parent.parent

try:
    from dotenv import load_dotenv
    load_dotenv(PLUGIN_ROOT / ".env")
except ImportError:
    print("ERROR: python-dotenv not installed. Run: pip install -r requirements.txt", file=sys.stderr)
    sys.exit(1)

import requests

BASE_URL    = os.getenv("YOUTRACK_BASE_URL", "https://[your-domain]").rstrip("/")
TOKEN       = os.getenv("YOUTRACK_TOKEN", "")
PROJECT     = os.getenv("YOUTRACK_PROJECT", "TRD")
KB          = PLUGIN_ROOT / "knowledge_base"
OUT_STORIES = KB / "user_stories.json"
OUT_BUGS    = KB / "bugs.json"
BATCH_SIZE  = 50
AC_CHARS    = 1000
MAX_KW      = 25

HEADERS = {"Authorization": f"Bearer {TOKEN}", "Accept": "application/json"}

STOPWORDS = {
    "that", "this", "with", "from", "have", "been", "will", "when", "then",
    "must", "should", "their", "there", "also", "only", "after", "before",
    "which", "would", "could", "where", "what", "does", "into", "over",
    "some", "more", "such", "each", "even", "both", "very",
}


# ── helpers ──────────────────────────────────────────────────
def get_field(custom_fields: list, name: str) -> str:
    for f in custom_fields or []:
        if f.get("name") != name:
            continue
        val = f.get("value")
        if not val:
            return ""
        if isinstance(val, dict):
            return val.get("name") or val.get("text") or ""
        if isinstance(val, list):
            return ", ".join(v.get("name", "") for v in val if v)
        return str(val)
    return ""


def extract_keywords(text: str) -> list[str]:
    clean = re.sub(r"[#*`\[\]|!\n{}()\-_/\\]", " ", text.lower())
    seen, result = set(), []
    for w in clean.split():
        if len(w) >= 4 and w not in STOPWORDS and w not in seen and w.isalpha():
            seen.add(w)
            result.append(w)
        if len(result) >= MAX_KW:
            break
    return result


def extract_links(raw_links: list) -> tuple[list, list]:
    children, related = [], []
    for link in raw_links or []:
        ltype = (link.get("linkType") or {}).get("name", "").lower()
        direction = link.get("direction", "")
        for issue in link.get("issues", []):
            iid = issue.get("idReadable", "")
            if not iid:
                continue
            if "parent" in ltype or direction == "OUTWARD":
                children.append(iid)
            else:
                related.append(iid)
    return children[:15], related[:15]


def ac_preview(description: str) -> str:
    if not description:
        return ""
    return re.sub(r"\s+", " ", re.sub(r"[#*`\[\]!\|]", "", description[:AC_CHARS])).strip()


# ── generic fetcher ──────────────────────────────────────────
def fetch_by_query(query: str, label: str) -> list[dict]:
    """Pull all issues matching YQL query, paginated."""
    fields = (
        "id,idReadable,summary,description,"
        "customFields(name,value(name,text)),"
        "links(direction,linkType(name),issues(idReadable,summary))"
    )
    all_issues, skip = [], 0
    while True:
        url = f"{BASE_URL}/api/issues?query={quote(query)}&fields={fields}&$top={BATCH_SIZE}&$skip={skip}"
        r = requests.get(url, headers=HEADERS, timeout=30)
        if r.status_code == 401:
            raise RuntimeError("401 Unauthorized — check YOUTRACK_TOKEN in .env")
        if not r.ok:
            print(f"  WARN {r.status_code} at skip={skip}, stopping.")
            break
        batch = r.json()
        if not batch:
            break
        all_issues.extend(batch)
        print(f"  [{label}] fetched {len(all_issues)}...", end="\r")
        if len(batch) < BATCH_SIZE:
            break
        skip += BATCH_SIZE
        time.sleep(0.2)
    print()
    return all_issues


# ── processors ───────────────────────────────────────────────
def process_story(raw: dict) -> dict | None:
    iid = raw.get("idReadable", "")
    if not iid:
        return None
    cf = raw.get("customFields", [])
    desc = raw.get("description") or ""
    summary = raw.get("summary", "")
    children, related = extract_links(raw.get("links", []))
    return {
        "id":               iid,
        "summary":          summary,
        "status":           get_field(cf, "State"),
        "priority":         get_field(cf, "Priority"),
        "version":          get_field(cf, "Release Version"),
        "sprint":           get_field(cf, "Sprint"),
        "to_release_notes": get_field(cf, "To Release Notes"),
        "assignee":         get_field(cf, "Assignee"),
        "ac_preview":       ac_preview(desc),
        "keywords":         extract_keywords(summary + " " + desc[:600]),
        "children":         children,
        "related":          related,
    }


def process_bug(raw: dict) -> dict | None:
    """Build a bug index entry. Bug-specific fields focus on what QA needs to
    answer 'был ли уже такой баг?' offline."""
    iid = raw.get("idReadable", "")
    if not iid:
        return None
    cf = raw.get("customFields", [])
    desc = raw.get("description") or ""
    summary = raw.get("summary", "")
    children, related = extract_links(raw.get("links", []))
    tags = get_field(cf, "Tags")
    return {
        "id":                 iid,
        "summary":            summary,
        "status":             get_field(cf, "State"),
        "priority":           get_field(cf, "Priority"),
        "subsystem":          get_field(cf, "Subsystem"),
        "stack":              get_field(cf, "Stack"),
        "release_version":    get_field(cf, "Release Version"),
        "affected_version":   get_field(cf, "Affected version"),
        "assignee":           get_field(cf, "Assignee"),
        "tags":               tags,
        "is_first_cohort":    "1st cohort" in tags.lower() if tags else False,
        "bsource":            get_field(cf, "BSource"),
        "to_release_notes":   get_field(cf, "To Release Notes"),
        "preview":            ac_preview(desc),
        "keywords":           extract_keywords(summary + " " + desc[:600]),
        "parent_stories":     children,  # parent links — usually the User Story this bug is against
        "related":            related,
    }


# ── orchestration ────────────────────────────────────────────
def update_stories() -> int:
    query = f"#{{User Story}} project: {PROJECT}"
    raw = fetch_by_query(query, "stories")
    print(f"Processing {len(raw)} stories...")
    stories = []
    for r in raw:
        try:
            rec = process_story(r)
            if rec:
                stories.append(rec)
        except Exception as e:
            print(f"  WARN failed {r.get('idReadable', '?')}: {e}")
    stories.sort(key=lambda s: int(s["id"].replace("{TICKET_PREFIX}-", "") or 0), reverse=True)
    OUT_STORIES.parent.mkdir(parents=True, exist_ok=True)
    with open(OUT_STORIES, "w", encoding="utf-8") as f:
        json.dump({
            "meta": {
                "generated_at": time.strftime("%Y-%m-%d %H:%M UTC", time.gmtime()),
                "source":       BASE_URL,
                "project":      PROJECT,
                "type":         "User Story",
                "total":        len(stories),
            },
            "stories": stories,
        }, f, ensure_ascii=False, indent=2)
    kb = OUT_STORIES.stat().st_size // 1024
    print(f"✅ Stories: {len(stories)} → {OUT_STORIES.name} ({kb} KB)")
    return len(stories)


def update_bugs(recent_days: int | None = None) -> int:
    query = f"#{{Bug}} project: {PROJECT}"
    if recent_days:
        query += f" created: -{recent_days}d .. Today"
    raw = fetch_by_query(query, "bugs")
    print(f"Processing {len(raw)} bugs...")
    bugs = []
    for r in raw:
        try:
            rec = process_bug(r)
            if rec:
                bugs.append(rec)
        except Exception as e:
            print(f"  WARN failed {r.get('idReadable', '?')}: {e}")
    bugs.sort(key=lambda s: int(s["id"].replace("{TICKET_PREFIX}-", "") or 0), reverse=True)
    OUT_BUGS.parent.mkdir(parents=True, exist_ok=True)

    # Aggregate stats for fast access
    by_status = {}
    by_subsystem = {}
    first_cohort_count = 0
    for b in bugs:
        by_status[b["status"] or "(none)"] = by_status.get(b["status"] or "(none)", 0) + 1
        by_subsystem[b["subsystem"] or "(none)"] = by_subsystem.get(b["subsystem"] or "(none)", 0) + 1
        if b.get("is_first_cohort"):
            first_cohort_count += 1

    with open(OUT_BUGS, "w", encoding="utf-8") as f:
        json.dump({
            "meta": {
                "generated_at":       time.strftime("%Y-%m-%d %H:%M UTC", time.gmtime()),
                "source":             BASE_URL,
                "project":            PROJECT,
                "type":               "Bug",
                "total":              len(bugs),
                "first_cohort_count": first_cohort_count,
                "by_status":          by_status,
                "by_subsystem":       by_subsystem,
                "scope":              f"created last {recent_days}d" if recent_days else "all-time",
            },
            "bugs": bugs,
        }, f, ensure_ascii=False, indent=2)
    kb = OUT_BUGS.stat().st_size // 1024
    print(f"✅ Bugs: {len(bugs)} → {OUT_BUGS.name} ({kb} KB)")
    print(f"   1st cohort: {first_cohort_count}, by_status: {by_status}")
    return len(bugs)


def update_freshness_marker(stories: int, bugs: int) -> None:
    (PLUGIN_ROOT / "kb_cache").mkdir(exist_ok=True)
    with open(PLUGIN_ROOT / "kb_cache" / "last_sync.json", "w") as f:
        json.dump({
            "generated_at": time.time(),
            "stories":      stories,
            "bugs":         bugs,
        }, f)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--stories-only", action="store_true", help="Skip bugs index")
    parser.add_argument("--bugs-only", action="store_true", help="Skip stories index")
    parser.add_argument("--bugs-recent", type=int, default=None, metavar="DAYS",
                        help="Only fetch bugs created in the last N days (default: all-time)")
    args = parser.parse_args()

    if not TOKEN:
        print("ERROR: YOUTRACK_TOKEN not set in .env", file=sys.stderr)
        return 1

    print(f"Source : {BASE_URL}")
    print(f"Project: {PROJECT}\n")

    stories_count = 0
    bugs_count = 0

    if not args.bugs_only:
        stories_count = update_stories()
        print()

    if not args.stories_only:
        bugs_count = update_bugs(recent_days=args.bugs_recent)
        print()

    update_freshness_marker(stories_count, bugs_count)
    print(f"✓ Done. Stories={stories_count}, Bugs={bugs_count}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
