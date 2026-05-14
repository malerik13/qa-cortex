#!/usr/bin/env python3
"""
[COMPANY] QA — Release Schedule Cache Refresher

Fetches TRD-A-41287691 (release schedule article) from YouTrack,
parses the markdown release table, writes two cache files:
- knowledge_base/release_cadence_cache.md (human-readable, with Vietnam/Poland time anchors)
- knowledge_base/release_cadence.json (machine-readable)

Designed to run daily via scheduled-tasks at 12:30 Vietnam (07:30 Poland).
Idempotent — safe to run multiple times per day.

Exit codes:
  0 = cache refreshed
  1 = error (auth, network, parse failure)
  2 = no change (cache matched current content)
"""

import json
import os
import re
import sys
from datetime import datetime, date, timedelta, timezone
from pathlib import Path

try:
    from dotenv import load_dotenv
except ImportError:
    print("ERROR: python-dotenv not installed. Run: pip install python-dotenv requests", file=sys.stderr)
    sys.exit(1)

try:
    import requests
except ImportError:
    print("ERROR: requests not installed. Run: pip install requests", file=sys.stderr)
    sys.exit(1)

# ─── Config ───────────────────────────────────────────────────────────────────

PROJECT_ROOT = Path(__file__).resolve().parent.parent
load_dotenv(PROJECT_ROOT / ".env")

ARTICLE_ID = "TRD-A-41287691"
OUTPUT_MD = PROJECT_ROOT / "knowledge_base" / "release_cadence_cache.md"
OUTPUT_JSON = PROJECT_ROOT / "knowledge_base" / "release_cadence.json"

BASE_URL = os.environ.get("YOUTRACK_BASE_URL", "").rstrip("/")
TOKEN = os.environ.get("YOUTRACK_TOKEN")

if not BASE_URL or not TOKEN:
    print("ERROR: YOUTRACK_BASE_URL / YOUTRACK_TOKEN not set in .env", file=sys.stderr)
    sys.exit(1)


# ─── YouTrack fetch ───────────────────────────────────────────────────────────

def fetch_article(article_id: str) -> dict:
    """Fetch article content from YouTrack REST API."""
    url = f"{BASE_URL}/api/articles/{article_id}?fields=id,idReadable,summary,content"
    headers = {
        "Authorization": f"Bearer {TOKEN}",
        "Accept": "application/json",
    }
    r = requests.get(url, headers=headers, timeout=20)
    if r.status_code != 200:
        print(f"ERROR: YouTrack returned {r.status_code}: {r.text[:200]}", file=sys.stderr)
        sys.exit(1)
    return r.json()


# ─── Markdown table parsing ───────────────────────────────────────────────────

def parse_release_table(content: str) -> list:
    """
    Extract release rows from the main markdown table.

    Expected columns (8):
        Released | Version | Internal Demo | Business Demo | UAT | Production | Scope | Notes
    """
    releases = []
    in_table = False
    for raw_line in content.split("\n"):
        line = raw_line.strip()

        if not in_table:
            if "Version" in line and "Internal Demo" in line and "|" in line:
                in_table = True
            continue

        if not line.startswith("|"):
            if line == "":
                break
            continue

        if "---" in line:
            continue

        cells = [c.strip() for c in line.split("|")[1:-1]]
        if len(cells) < 6:
            continue

        status_raw = cells[0]
        version = cells[1]
        if not version or version.lower() == "version":
            continue

        status = classify_status(status_raw)
        releases.append({
            "status_emoji": status_raw,
            "status": status,
            "version": version,
            "internal_demo": extract_date(cells[2]),
            "business_demo": extract_date(cells[3]),
            "uat_scheduled": extract_date(cells[4]),
            "production_scheduled": extract_date(cells[5]),
        })
    return releases


def classify_status(emoji: str) -> str:
    """Map status emoji to phase label."""
    if "✅" in emoji:
        return "shipped"
    if "⏳" in emoji:
        return "in-progress"
    if "🗓️" in emoji or "🗓" in emoji:
        return "scheduled"
    return "unknown"


def extract_date(cell: str) -> str | None:
    """Parse DD/MM/YYYY from cell content."""
    if not cell:
        return None
    m = re.search(r"(\d{2})/(\d{2})/(\d{4})", cell)
    if not m:
        return None
    dd, mm, yyyy = m.groups()
    return f"{yyyy}-{mm}-{dd}"  # ISO format YYYY-MM-DD


# ─── Phase classification ─────────────────────────────────────────────────────

def feature_freeze_date(internal_demo_iso: str) -> str | None:
    """Feature freeze = Tuesday before Internal Demo Thursday (2 days earlier)."""
    if not internal_demo_iso:
        return None
    try:
        d = datetime.strptime(internal_demo_iso, "%Y-%m-%d").date()
        return (d - timedelta(days=2)).isoformat()
    except ValueError:
        return None


def classify_phase(release: dict, today: date) -> str:
    """Determine current phase of a release."""
    if release.get("status") == "shipped":
        return "shipped"

    freeze = feature_freeze_date(release.get("internal_demo"))
    internal = release.get("internal_demo")
    business = release.get("business_demo")
    uat = release.get("uat_scheduled")
    prod = release.get("production_scheduled")

    def lt(a_iso, b_date):
        if not a_iso:
            return False
        return datetime.strptime(a_iso, "%Y-%m-%d").date() <= b_date

    today_iso = today.isoformat()
    if prod and lt(prod, today):
        return "released"
    if uat and lt(uat, today):
        return "uat"
    if business and lt(business, today):
        return "business-validation"
    if internal and lt(internal, today):
        return "qa-active"
    if freeze and freeze <= today_iso < (internal or "9999-99-99"):
        return "qa-prep"
    if freeze and today_iso < freeze:
        return "feature-dev"
    return "future"


# ─── Cache writing ────────────────────────────────────────────────────────────

def write_json_cache(cache: dict) -> bool:
    """Write JSON cache. Returns True if content changed."""
    existing = None
    if OUTPUT_JSON.exists():
        try:
            existing = json.loads(OUTPUT_JSON.read_text())
            # Strip volatile timestamp before comparison
            ex = {k: v for k, v in existing.items() if k != "fetched_at"}
            new = {k: v for k, v in cache.items() if k != "fetched_at"}
            if ex == new:
                return False
        except Exception:
            pass

    OUTPUT_JSON.write_text(json.dumps(cache, indent=2, ensure_ascii=False) + "\n")
    return True


def write_md_cache(cache: dict):
    """Write human-readable markdown cache."""
    lines = [
        "# Release Cadence Cache",
        "",
        f"> **Source:** [{ARTICLE_ID}]({BASE_URL}/articles/{ARTICLE_ID})",
        f"> **Refreshed:** {cache['fetched_at']}",
        f"> **Today:** {cache['today']}",
        f"> **Current focus:** version `{cache['current_focus']['version']}` — phase `{cache['current_focus']['phase']}`",
        "",
        "## Release cycle anchors (per article)",
        "",
        "- **Tuesday** → Feature freeze (last commit for version)",
        "- **Thursday** → Internal Demo",
        "- **Friday (+1 week)** → Business Demo",
        "- **Monday** → UAT",
        "- **Saturday** → Production release",
        "",
        "## Upcoming releases",
        "",
        "| Status | Version | Feature Freeze | Internal Demo | Business Demo | UAT | Production | Phase |",
        "|---|---|---|---|---|---|---|---|",
    ]
    for r in cache["upcoming"]:
        lines.append(
            f"| {r['status_emoji']} | {r['version']} | "
            f"{r.get('feature_freeze') or '—'} | "
            f"{r['internal_demo'] or '—'} | "
            f"{r['business_demo'] or '—'} | "
            f"{r['uat_scheduled'] or '—'} | "
            f"{r['production_scheduled'] or '—'} | "
            f"`{r['phase']}` |"
        )

    lines.extend([
        "",
        "## All releases (recent history)",
        "",
        "| Status | Version | Production |",
        "|---|---|---|",
    ])
    for r in cache["all_releases"][:20]:
        lines.append(f"| {r['status_emoji']} | {r['version']} | {r['production_scheduled'] or '—'} |")

    lines.append("")
    lines.append("---")
    lines.append("")
    lines.append("**Auto-refreshed daily** at 12:30 Vietnam (07:30 Poland) by `scripts/refresh-release-schedule.py`.")
    lines.append("")

    OUTPUT_MD.write_text("\n".join(lines))


# ─── Main ─────────────────────────────────────────────────────────────────────

def main():
    article = fetch_article(ARTICLE_ID)
    content = article.get("content", "")
    if not content:
        print("ERROR: Article content empty", file=sys.stderr)
        sys.exit(1)

    releases = parse_release_table(content)
    if not releases:
        print("ERROR: No releases parsed from article", file=sys.stderr)
        sys.exit(1)

    today = date.today()

    # Annotate releases with feature_freeze + phase
    for r in releases:
        r["feature_freeze"] = feature_freeze_date(r.get("internal_demo"))
        r["phase"] = classify_phase(r, today)

    # Upcoming = non-shipped + currently-shipping
    upcoming = [r for r in releases if r["status"] != "shipped"][:5]

    # Current focus = release nearest to today by production date that hasn't shipped
    # (skips entries without dates; falls back to first upcoming if no dated candidates)
    def days_to_prod(r):
        prod = r.get("production_scheduled")
        if not prod:
            return 99999
        try:
            d = datetime.strptime(prod, "%Y-%m-%d").date()
            return abs((d - today).days)
        except ValueError:
            return 99999

    dated = [r for r in upcoming if r.get("production_scheduled")]
    if dated:
        current_focus = min(dated, key=days_to_prod)
    else:
        current_focus = upcoming[0] if upcoming else releases[0] if releases else None

    cache = {
        "fetched_at": datetime.now(timezone.utc).isoformat(),
        "source": ARTICLE_ID,
        "source_url": f"{BASE_URL}/articles/{ARTICLE_ID}",
        "today": today.isoformat(),
        "current_focus": current_focus,
        "upcoming": upcoming,
        "all_releases": releases,
    }

    changed = write_json_cache(cache)
    write_md_cache(cache)

    if changed:
        print(f"✓ Cache refreshed — {len(releases)} releases, focus={current_focus['version'] if current_focus else 'none'}")
        sys.exit(0)
    else:
        print(f"✓ Cache unchanged — {len(releases)} releases (content matched)")
        sys.exit(2)


if __name__ == "__main__":
    main()
