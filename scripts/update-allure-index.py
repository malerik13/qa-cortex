#!/usr/bin/env python3
"""
Pull all Allure TestOps test cases into knowledge_base/test_cases.json.

The local index is what `search_test_cases` and `find_test_cases_by_issue`
read. Run this periodically (like update-kb.py for YouTrack).

Usage:
    .venv/bin/python scripts/update-allure-index.py
    .venv/bin/python scripts/update-allure-index.py --fast   # skip per-case detail fetch
"""
import json
import os
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

try:
    from dotenv import load_dotenv
except ImportError:
    print("ERROR: python-dotenv not installed. Activate .venv first.", file=sys.stderr)
    sys.exit(1)

import requests

PLUGIN_ROOT = Path(__file__).resolve().parent.parent
load_dotenv(PLUGIN_ROOT / ".env")

BASE = (os.getenv("ALLURE_BASE_URL") or "").rstrip("/")
TOKEN = os.getenv("ALLURE_TOKEN") or ""
PROJECT_ID = int(os.getenv("ALLURE_PROJECT_ID") or "0")

if not BASE or not TOKEN or not PROJECT_ID:
    print("ERROR: ALLURE_BASE_URL / ALLURE_TOKEN / ALLURE_PROJECT_ID missing in .env", file=sys.stderr)
    sys.exit(1)

HEADERS = {
    "Authorization": f"Api-Token {TOKEN}",
    "Accept": "application/json",
}

OUT = PLUGIN_ROOT / "knowledge_base" / "test_cases.json"
FAST = "--fast" in sys.argv


def fetch_page(page: int, size: int = 200):
    url = f"{BASE}/api/rs/testcase?projectId={PROJECT_ID}&page={page}&size={size}&sort=id,asc"
    r = requests.get(url, headers=HEADERS, timeout=30)
    r.raise_for_status()
    return r.json()


def fetch_detail(tc_id: int):
    r = requests.get(f"{BASE}/api/rs/testcase/{tc_id}", headers=HEADERS, timeout=15)
    if r.status_code != 200:
        return None
    return r.json()


def fetch_cfvs(tc_id: int):
    """Return a slim list of [{'id','name','cf_id','cf_name'}] — enough to match
    TRD references buried in Story/Feature values. Expensive: 1 extra request per case."""
    r = requests.get(f"{BASE}/api/rs/testcase/{tc_id}/cfv", headers=HEADERS, timeout=15)
    if r.status_code != 200:
        return []
    slim = []
    for v in r.json() or []:
        cf = v.get("customField") or {}
        slim.append({
            "id": v.get("id"),
            "name": v.get("name", ""),
            "cf_id": cf.get("id"),
            "cf_name": cf.get("name", ""),
        })
    return slim


def main():
    print(f"Pulling Allure test cases from {BASE} (project {PROJECT_ID})...")
    all_cases = []
    page = 0
    while True:
        data = fetch_page(page)
        items = data.get("content", [])
        for it in items:
            all_cases.append({
                "id": it.get("id"),
                "name": it.get("name"),
                "status": (it.get("status") or {}).get("name"),
                "automated": it.get("automated", False),
                "lastModifiedDate": it.get("lastModifiedDate"),
                "links": [],  # filled in detail pass
            })
        total_pages = data.get("totalPages", 1)
        print(f"  page {page + 1}/{total_pages} — {len(all_cases)} cases so far")
        if page + 1 >= total_pages or data.get("last"):
            break
        page += 1

    print(f"Total list-view cases: {len(all_cases)}")

    if not FAST:
        print("Fetching per-case details (links + CFVs)... this may take ~5 minutes for ~2500 cases.")
        for i, c in enumerate(all_cases, 1):
            detail = fetch_detail(c["id"])
            if detail:
                c["links"] = detail.get("links", []) or []
                c["description"] = detail.get("description") or ""
            # CFVs — needed because Allure cases reference TRD-XXXXX via the
            # Story custom field, not always via the ISSUE link.
            c["cfvs"] = fetch_cfvs(c["id"])
            if i % 100 == 0:
                print(f"  {i}/{len(all_cases)} details+cfvs fetched")
            # Gentle on the server
            if i % 50 == 0:
                time.sleep(0.2)

    payload = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "base_url": BASE,
        "project_id": PROJECT_ID,
        "count": len(all_cases),
        "fast_mode": FAST,
        "cases": all_cases,
    }
    OUT.parent.mkdir(parents=True, exist_ok=True)
    with open(OUT, "w", encoding="utf-8") as f:
        json.dump(payload, f, ensure_ascii=False, indent=2)
    print(f"✅ Wrote {len(all_cases)} cases to {OUT}")


if __name__ == "__main__":
    main()
