#!/usr/bin/env python3
"""
refresh-product-map.py — generate knowledge_base/product_map.json from sources.

Phase A scope (per knowledge_base/design_docs/product_map_v1.md §11):
- Parses TWO sources only: flows/_index.json + bugs.json
- Classifies entries to modules via _module_taxonomy.json (keyword scoring)
- Writes product_map.json with per-module nodes (recipes + recent_bugs)
- Writes product_map_unclassified.md audit log

Phase B will extend to: business_rules, ui_flows, glossary, db_naming_map,
insights, db_diff, Allure cases.

Usage:
    python3 scripts/refresh-product-map.py [--check]
"""

import json
import sys
import re
import hashlib
from pathlib import Path
from datetime import datetime, timezone
from collections import defaultdict

REPO_ROOT = Path(__file__).resolve().parent.parent
KB_DIR = REPO_ROOT / "knowledge_base"
TAXONOMY_PATH = KB_DIR / "_module_taxonomy.json"
MAP_PATH = KB_DIR / "product_map.json"
UNCLASSIFIED_PATH = KB_DIR / "product_map_unclassified.md"
FLOWS_INDEX_PATH = REPO_ROOT / "flows" / "_index.json"
BUGS_JSON_PATH = KB_DIR / "bugs.json"

RECENT_BUGS_LIMIT = 10  # per module, most recent OPEN/Submitted


def load_taxonomy() -> dict:
    if not TAXONOMY_PATH.exists():
        sys.exit(f"❌ {TAXONOMY_PATH} missing")
    return json.loads(TAXONOMY_PATH.read_text(encoding="utf-8"))


def file_sha(path: Path) -> str | None:
    if not path.exists():
        return None
    return "sha256:" + hashlib.sha256(path.read_bytes()).hexdigest()[:16]


def classify(text: str, taxonomy: dict) -> tuple[str, int, dict]:
    """Return (module_id, score, all_scores) using keyword + synonym scoring."""
    text_lc = text.lower()
    scores: dict[str, int] = {}

    for mod_id, mod_def in taxonomy["modules"].items():
        if mod_id == taxonomy.get("default_module", "misc"):
            continue
        score = 0
        for kw in mod_def.get("keywords", []) + mod_def.get("synonyms", []):
            # Word-boundary match to avoid spurious substring hits
            if re.search(rf"\b{re.escape(kw.lower())}\b", text_lc):
                score += 1
        scores[mod_id] = score

    if not scores or max(scores.values()) < taxonomy.get("min_classification_score", 2):
        return taxonomy.get("default_module", "misc"), 0, scores

    best = max(scores, key=scores.get)
    return best, scores[best], scores


def parse_flows_index(taxonomy: dict) -> dict:
    """Return {module_id: [recipe_entries]}."""
    if not FLOWS_INDEX_PATH.exists():
        return {}

    idx = json.loads(FLOWS_INDEX_PATH.read_text(encoding="utf-8"))
    by_module: dict = defaultdict(list)

    for r in idx.get("recipes", []):
        # Recipe area maps directly to module (per design §3.2)
        # Treat recipe.area as authoritative for classification
        module = r.get("area", "misc")
        if module not in taxonomy["modules"]:
            module = "misc"

        by_module[module].append({
            "flow_id": r["flow_id"],
            "path": r["path"],
            "status": r.get("status", "active"),
            "verification_count": r.get("verification_count", 0),
            "tags": r.get("tags", []),
            "envs": r.get("envs", []),
            "estimated_replay_tokens": r.get("estimated_replay_tokens"),
        })

    return by_module


def parse_bugs_json(taxonomy: dict) -> tuple[dict, list]:
    """Return ({module_id: {open_count, recent_examples, examples_list}}, unclassified_list)."""
    if not BUGS_JSON_PATH.exists():
        return {}, []

    data = json.loads(BUGS_JSON_PATH.read_text(encoding="utf-8"))
    bugs = data.get("bugs", [])

    by_module: dict = defaultdict(lambda: {"open_count": 0, "all_examples": []})
    unclassified: list = []

    for b in bugs:
        # Build classification text from summary + keywords + tags
        text_parts = [
            b.get("summary", ""),
            " ".join(b.get("keywords", []) or []),
            " ".join(b.get("tags", []) or []) if isinstance(b.get("tags"), list) else (b.get("tags") or ""),
        ]
        text = " ".join(text_parts)

        module, score, all_scores = classify(text, taxonomy)

        is_open = b.get("status", "").lower() in ("open", "submitted", "in progress", "to do", "reopened")

        entry = {
            "id": b.get("id"),
            "title": b.get("summary", "")[:200],
            "status": b.get("status"),
            "priority": b.get("priority"),
            "is_first_cohort": b.get("is_first_cohort", False),
        }

        by_module[module]["all_examples"].append(entry)
        if is_open:
            by_module[module]["open_count"] += 1

        if module == taxonomy.get("default_module", "misc") and score == 0:
            unclassified.append({
                "source": "bugs.json",
                "ref": b.get("id"),
                "title": b.get("summary", "")[:80],
                "scores": {k: v for k, v in all_scores.items() if v > 0} or "none above threshold",
            })

    # Trim to RECENT_BUGS_LIMIT, prefer open
    for mod_id, payload in by_module.items():
        examples = payload.pop("all_examples")
        # Sort: open first, then by title
        examples.sort(key=lambda x: (x.get("status", "").lower() not in ("open", "submitted", "reopened"), x.get("id", "")))
        payload["recent_examples"] = examples[:RECENT_BUGS_LIMIT]
        payload["total_examples"] = len(examples)

    return dict(by_module), unclassified


def build_modules(taxonomy: dict, recipes_by_mod: dict, bugs_by_mod: dict) -> dict:
    """Aggregate per-module nodes."""
    modules: dict = {}

    for mod_id, mod_def in taxonomy["modules"].items():
        node = {
            "name": mod_def.get("name", mod_id),
            "description": mod_def.get("description", ""),
            "ui_areas_taxonomy": mod_def.get("ui_areas", []),
            "db_tables_taxonomy": mod_def.get("db_tables", []),
            "recipes": recipes_by_mod.get(mod_id, []),
            "recent_bugs": bugs_by_mod.get(mod_id, {"open_count": 0, "recent_examples": [], "total_examples": 0}),
            "_phase_a_partial": True,
            "_pending_phase_b_sources": [
                "ui_surfaces (from ui_flows.md)",
                "db_tables (from db_naming_map.md)",
                "business_rules (from business_rules.md)",
                "glossary_terms (from glossary.md)",
                "insights (from insights.md)",
                "allure_coverage (from Allure MCP)",
                "schema_drift_notes (from db_diff__stage_vs_release.md)",
            ],
        }
        modules[mod_id] = node

    return modules


def write_unclassified(unclassified: list) -> None:
    if not unclassified:
        UNCLASSIFIED_PATH.write_text(
            "# Product Map — Unclassified Entries\n\n"
            f"> Auto-generated by `scripts/refresh-product-map.py`\n"
            f"> Last refresh: {datetime.now(timezone.utc).strftime('%Y-%m-%dT%H:%M:%SZ')}\n\n"
            "All entries classified successfully. ✓\n",
            encoding="utf-8",
        )
        return

    lines = [
        "# Product Map — Unclassified Entries",
        "",
        f"> Auto-generated by `scripts/refresh-product-map.py`",
        f"> Last refresh: {datetime.now(timezone.utc).strftime('%Y-%m-%dT%H:%M:%SZ')}",
        "",
        f"**{len(unclassified)} entries fell into `misc` bucket.** Triage:",
        "- Add new keyword to `_module_taxonomy.json` if pattern emerges",
        "- Add explicit `module:` field to source if obvious (Phase D — schema enrichment)",
        "- Accept misc bucket if entry is truly cross-cutting",
        "",
        "## Bugs",
        "",
    ]

    by_source = defaultdict(list)
    for u in unclassified:
        by_source[u["source"]].append(u)

    for source, entries in by_source.items():
        lines.append(f"### {source} ({len(entries)})")
        lines.append("")
        for e in entries[:50]:  # cap output
            lines.append(f"- **{e['ref']}** — {e['title']!r}")
            lines.append(f"  - scores: `{e['scores']}`")
        if len(entries) > 50:
            lines.append(f"- ... ({len(entries) - 50} more)")
        lines.append("")

    UNCLASSIFIED_PATH.write_text("\n".join(lines) + "\n", encoding="utf-8")


def main() -> int:
    check_only = "--check" in sys.argv

    taxonomy = load_taxonomy()
    recipes_by_mod = parse_flows_index(taxonomy)
    bugs_by_mod, unclassified = parse_bugs_json(taxonomy)
    modules = build_modules(taxonomy, recipes_by_mod, bugs_by_mod)

    new_map = {
        "version": "1.0",
        "phase": "A",
        "generated_at": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "source_files_hash": {
            "flows/_index.json": file_sha(FLOWS_INDEX_PATH),
            "knowledge_base/bugs.json": file_sha(BUGS_JSON_PATH),
            "knowledge_base/_module_taxonomy.json": file_sha(TAXONOMY_PATH),
        },
        "module_count": len(modules),
        "modules": modules,
        "_phase_b_sources_pending": [
            "knowledge_base/business_rules.md",
            "knowledge_base/ui_flows.md",
            "knowledge_base/glossary.md",
            "knowledge_base/db_naming_map.md",
            "knowledge_base/insights.md",
            "knowledge_base/db_diff__stage_vs_release.md",
            "Allure MCP cases",
        ],
        "unclassified_count": len(unclassified),
    }

    new_text = json.dumps(new_map, indent=2, ensure_ascii=False) + "\n"

    if check_only:
        if MAP_PATH.exists():
            try:
                existing = json.loads(MAP_PATH.read_text(encoding="utf-8"))
                cmp_existing = {k: v for k, v in existing.items() if k != "generated_at"}
                cmp_new = {k: v for k, v in new_map.items() if k != "generated_at"}
                if cmp_existing == cmp_new:
                    print(f"✓ product_map.json up-to-date ({len(modules)} modules, {len(unclassified)} unclassified)")
                    return 0
            except (json.JSONDecodeError, KeyError):
                pass
        print("✗ product_map.json out of sync — run without --check to fix", file=sys.stderr)
        return 1

    MAP_PATH.write_text(new_text, encoding="utf-8")
    write_unclassified(unclassified)

    # Summary stats
    print(f"✓ Wrote {MAP_PATH.name}")
    print(f"  modules: {len(modules)}")
    print(f"  recipes by module:")
    for mod_id, recipes in sorted(recipes_by_mod.items()):
        print(f"    {mod_id}: {len(recipes)} recipe(s)")
    print(f"  bugs classification:")
    for mod_id in sorted(modules.keys()):
        b = bugs_by_mod.get(mod_id, {})
        if b.get("total_examples", 0) > 0:
            print(f"    {mod_id}: {b.get('open_count', 0)} open / {b.get('total_examples', 0)} total")
    print(f"  unclassified: {len(unclassified)} (audit: {UNCLASSIFIED_PATH.name})")

    return 0


if __name__ == "__main__":
    sys.exit(main())
