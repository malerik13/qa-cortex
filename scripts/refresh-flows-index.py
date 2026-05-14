#!/usr/bin/env python3
"""
refresh-flows-index.py — rebuild flows/_index.json from filesystem state

Walks flows/ directory, parses YAML frontmatter from each *.recipe.md,
and writes consolidated _index.json with lookup maps (by_trd, by_area, by_tag).

Usage:
    python3 scripts/refresh-flows-index.py [--check]

  --check : exit non-zero if index would change (CI/git-hook use)

Per design doc §5 (knowledge_base/design_docs/flow_cache_v1.md).
"""

import json
import sys
import os
import re
from pathlib import Path
from datetime import datetime, timezone
from collections import defaultdict

REPO_ROOT = Path(__file__).resolve().parent.parent
FLOWS_DIR = REPO_ROOT / "flows"
INDEX_PATH = FLOWS_DIR / "_index.json"


def parse_frontmatter(text: str) -> dict | None:
    """Extract YAML frontmatter between leading --- markers. Minimal parser
    (no full YAML — just key: value lines, with simple list support)."""
    if not text.startswith("---"):
        return None

    end = text.find("\n---", 4)
    if end == -1:
        return None

    fm_text = text[4:end].strip()
    result: dict = {}

    for line in fm_text.split("\n"):
        line = line.strip()
        if not line or line.startswith("#"):
            continue

        m = re.match(r"^([a-zA-Z_][\w]*)\s*:\s*(.*)$", line)
        if not m:
            continue
        key, val = m.group(1), m.group(2).strip()

        # Strip wrapping quotes
        if (val.startswith('"') and val.endswith('"')) or (val.startswith("'") and val.endswith("'")):
            val = val[1:-1]

        # Handle list: [a, b, c]
        if val.startswith("[") and val.endswith("]"):
            inner = val[1:-1].strip()
            if not inner:
                result[key] = []
            else:
                result[key] = [x.strip().strip('"').strip("'") for x in inner.split(",")]
            continue

        # Handle null / none
        if val.lower() in ("null", "none", "~", ""):
            result[key] = None
            continue

        # Handle int
        if re.fullmatch(r"-?\d+", val):
            result[key] = int(val)
            continue

        result[key] = val

    return result


def collect_recipes(flows_dir: Path) -> list[dict]:
    recipes = []
    for recipe_path in flows_dir.rglob("*.recipe.md"):
        rel_path = recipe_path.relative_to(REPO_ROOT)
        try:
            text = recipe_path.read_text(encoding="utf-8")
        except Exception as e:
            print(f"⚠ Could not read {rel_path}: {e}", file=sys.stderr)
            continue

        fm = parse_frontmatter(text)
        if not fm:
            print(f"⚠ No frontmatter in {rel_path}", file=sys.stderr)
            continue

        if "flow_id" not in fm:
            print(f"⚠ Missing flow_id in {rel_path}", file=sys.stderr)
            continue

        # Derive area from path: flows/<area>/<file>.recipe.md
        parts = rel_path.parts
        area = parts[1] if len(parts) >= 3 and parts[0] == "flows" else "misc"

        entry = {
            "flow_id": fm["flow_id"],
            "path": str(rel_path),
            "area": area,
            "tags": fm.get("tags") or [],
            "envs": fm.get("env") or [],
            "roles": [fm["role"]] if isinstance(fm.get("role"), str) else (fm.get("role") or []),
            "last_verified": fm.get("last_verified"),
            "verification_count": fm.get("verification_count", 0) or 0,
            "estimated_replay_tokens": fm.get("estimated_replay_tokens"),
            "related_trd": fm.get("related_trd") or [],
            "playwright_spec": fm.get("playwright_spec"),
            "status": fm.get("status", "active"),
        }
        recipes.append(entry)

    recipes.sort(key=lambda r: r["flow_id"])
    return recipes


def build_lookup_maps(recipes: list[dict]) -> tuple[dict, dict, dict]:
    by_trd = defaultdict(list)
    by_area = defaultdict(list)
    by_tag = defaultdict(list)

    for r in recipes:
        for trd in r.get("related_trd", []):
            by_trd[trd].append(r["flow_id"])
        by_area[r["area"]].append(r["flow_id"])
        for tag in r.get("tags", []):
            by_tag[tag].append(r["flow_id"])

    # Stable ordering
    return (
        {k: sorted(v) for k, v in sorted(by_trd.items())},
        {k: sorted(v) for k, v in sorted(by_area.items())},
        {k: sorted(v) for k, v in sorted(by_tag.items())},
    )


def main() -> int:
    check_only = "--check" in sys.argv

    if not FLOWS_DIR.exists():
        print(f"⚠ flows/ does not exist at {FLOWS_DIR}", file=sys.stderr)
        return 1

    recipes = collect_recipes(FLOWS_DIR)
    by_trd, by_area, by_tag = build_lookup_maps(recipes)

    new_index = {
        "version": "1.0",
        "generated_at": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "recipe_count": len(recipes),
        "recipes": recipes,
        "by_trd": by_trd,
        "by_area": by_area,
        "by_tag": by_tag,
    }

    new_text = json.dumps(new_index, indent=2, ensure_ascii=False) + "\n"

    if check_only:
        # Compare ignoring generated_at (which always changes)
        if INDEX_PATH.exists():
            try:
                existing = json.loads(INDEX_PATH.read_text(encoding="utf-8"))
                cmp_existing = {k: v for k, v in existing.items() if k != "generated_at"}
                cmp_new = {k: v for k, v in new_index.items() if k != "generated_at"}
                if cmp_existing == cmp_new:
                    print(f"✓ flows/_index.json up-to-date ({len(recipes)} recipes)")
                    return 0
            except (json.JSONDecodeError, KeyError):
                pass
        print("✗ flows/_index.json out of sync — run without --check to fix", file=sys.stderr)
        return 1

    INDEX_PATH.write_text(new_text, encoding="utf-8")
    print(f"✓ Wrote flows/_index.json with {len(recipes)} recipes")
    return 0


if __name__ == "__main__":
    sys.exit(main())
