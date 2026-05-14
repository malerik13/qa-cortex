#!/usr/bin/env python3
"""Build human-readable + structured schema docs from a raw schema dump.

Per-DB layout (--db <name>):
  Input:  kb_cache/db/<name>/raw_schema.json
  Output: knowledge_base/db_schema__<name>.md
          knowledge_base/db_schema__<name>.json

Legacy single-DB layout (when called without --db):
  Input:  kb_cache/db/raw_schema.json
  Output: knowledge_base/db_schema.md
          knowledge_base/db_schema.json

Read-only: only consumes the cached dump. To refresh the dump, run
scripts/refresh-db-schema.sh (which calls psql against the chosen DB).
"""
from __future__ import annotations

import argparse
import json
import re
from pathlib import Path
from datetime import datetime

ROOT = Path(__file__).resolve().parent.parent
KB = ROOT / "knowledge_base"


def paths_for(db_name: str | None) -> tuple[Path, Path, Path]:
    if db_name:
        raw = ROOT / "kb_cache" / "db" / db_name / "raw_schema.json"
        out_md = KB / f"db_schema__{db_name}.md"
        out_json = KB / f"db_schema__{db_name}.json"
    else:
        raw = ROOT / "kb_cache" / "db" / "raw_schema.json"
        out_md = KB / "db_schema.md"
        out_json = KB / "db_schema.json"
    return raw, out_md, out_json


def parse_size_to_bytes(size_str: str) -> int:
    """'42 MB' → 44040192. Used for sorting only."""
    if not size_str:
        return 0
    m = re.match(r"([\d.]+)\s*(\w+)", size_str)
    if not m:
        return 0
    val = float(m.group(1))
    unit = m.group(2).lower()
    mult = {"bytes": 1, "kb": 1024, "mb": 1024**2, "gb": 1024**3, "tb": 1024**4}.get(unit, 1)
    return int(val * mult)


def slugify(name: str) -> str:
    return re.sub(r"[^a-z0-9]+", "-", name.lower()).strip("-")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--db", default=None, help="DB name (e.g. stage, release). Omit for legacy single-DB mode.")
    args = parser.parse_args()

    raw_path, out_md, out_json = paths_for(args.db)
    if not raw_path.exists():
        raise SystemExit(f"❌ Raw schema not found: {raw_path}\n   Run: scripts/refresh-db-schema.sh{(' --db ' + args.db) if args.db else ''}")

    raw = json.loads(raw_path.read_text())
    meta = raw.get("meta", {})
    tables = raw.get("tables") or []

    # Sort tables by size (largest first) for the overview
    tables_by_size = sorted(
        tables,
        key=lambda t: parse_size_to_bytes(t.get("total_size", "0 bytes")),
        reverse=True,
    )

    # ────────── Structured JSON ──────────
    structured = {
        "meta": {
            "database": meta.get("database"),
            "pg_version": meta.get("pg_version"),
            "extracted_at": meta.get("extracted_at"),
            "role": meta.get("role"),
            "table_count": len(tables),
            "total_columns": sum(len(t.get("columns") or []) for t in tables),
            "total_indexes": sum(len(t.get("indexes") or []) for t in tables),
            "tables_with_fk": sum(
                1 for t in tables
                if any((c.get("type") == "foreign_key") for c in (t.get("constraints") or []))
            ),
        },
        "tables": {
            f"{t['schema_name']}.{t['table_name']}": {
                "approx_rows": t.get("approx_rows"),
                "total_size": t.get("total_size"),
                "comment": t.get("table_comment"),
                "columns": t.get("columns") or [],
                "indexes": t.get("indexes") or [],
                "constraints": t.get("constraints") or [],
            }
            for t in tables
        },
    }
    out_json.write_text(json.dumps(structured, indent=2, default=str))

    # ────────── Human-readable Markdown ──────────
    lines: list[str] = []
    db_label = meta.get("database") or (args.db or "unknown")
    lines.append(f"# DB `{db_label}` — Schema Reference")
    lines.append("")
    lines.append(f"> Source: `{meta.get('database')}` on PostgreSQL {meta.get('pg_version')}")
    lines.append(f"> Extracted: {meta.get('extracted_at')}")
    lines.append(f"> Role: `{meta.get('role')}` (read-only, member of `readonly_role`)")
    lines.append("")
    lines.append("**👉 Read [`db_naming_map.md`](db_naming_map.md) FIRST — it translates UI terms (Client, Account, Agent) to actual table names. This file is the structural reference; the naming map is the semantic one.**")
    lines.append("")
    lines.append("**Important findings:**")
    lines.append("")
    lines.append(f"- {len(tables)} tables, {structured['meta']['total_columns']} columns, {structured['meta']['total_indexes']} indexes")
    fk_tables = structured["meta"]["tables_with_fk"]
    if fk_tables == 0:
        lines.append("- **No foreign keys at DB level.** All referential integrity lives in application code. Treat join columns as conventional.")
    else:
        lines.append(f"- {fk_tables} tables have foreign keys at DB level.")
    lines.append("- No views (`information_schema.views` = 0).")
    lines.append("")
    lines.append("---")
    lines.append("")

    # ────────── Table of contents (by size) ──────────
    lines.append("## Tables — overview (sorted by size)")
    lines.append("")
    lines.append("| Table | Approx rows | Size | Anchor |")
    lines.append("|---|---:|---:|---|")
    for t in tables_by_size:
        full_name = f"{t['schema_name']}.{t['table_name']}"
        anchor = slugify(full_name)
        rows = t.get("approx_rows") or 0
        size = t.get("total_size") or "—"
        lines.append(f"| `{full_name}` | {rows:,} | {size} | [↓](#{anchor}) |")
    lines.append("")
    lines.append("---")
    lines.append("")

    # ────────── Per-table detail (alphabetical for predictable navigation) ──────────
    lines.append("## Tables — details (alphabetical)")
    lines.append("")
    for t in sorted(tables, key=lambda x: (x["schema_name"], x["table_name"])):
        full_name = f"{t['schema_name']}.{t['table_name']}"
        anchor = slugify(full_name)
        lines.append(f"### `{full_name}` <a id=\"{anchor}\"></a>")
        lines.append("")
        rows = t.get("approx_rows") or 0
        size = t.get("total_size") or "—"
        lines.append(f"_Approx rows: {rows:,} · Size: {size}_")
        if t.get("table_comment"):
            lines.append("")
            lines.append(f"> {t['table_comment']}")
        lines.append("")

        cols = t.get("columns") or []
        if cols:
            lines.append("**Columns:**")
            lines.append("")
            lines.append("| # | Column | Type | Nullable | Default |")
            lines.append("|---:|---|---|---|---|")
            for c in cols:
                default = (c.get("default_value") or "").replace("|", "\\|")
                if len(default) > 60:
                    default = default[:57] + "..."
                nullable = "yes" if c.get("nullable") else "no"
                lines.append(
                    f"| {c['ordinal_position']} | `{c['name']}` | `{c['type']}` | {nullable} | "
                    f"{('`' + default + '`') if default else '—'} |"
                )
            lines.append("")

        cons = t.get("constraints") or []
        if cons:
            lines.append("**Constraints:**")
            lines.append("")
            for c in cons:
                lines.append(f"- `{c['name']}` ({c['type']}): `{c['definition']}`")
            lines.append("")

        idx = t.get("indexes") or []
        if idx:
            lines.append("**Indexes:**")
            lines.append("")
            for i in idx:
                tags = []
                if i.get("is_primary"):
                    tags.append("PK")
                if i.get("is_unique") and not i.get("is_primary"):
                    tags.append("UNIQUE")
                tag_str = f" _[{', '.join(tags)}]_" if tags else ""
                lines.append(f"- `{i['name']}`{tag_str}: `{i['definition']}`")
            lines.append("")

        lines.append("---")
        lines.append("")

    out_md.write_text("\n".join(lines))

    # ────────── Console summary ──────────
    print(f"✓ Wrote {out_json}  ({out_json.stat().st_size:,} bytes)")
    print(f"✓ Wrote {out_md}    ({out_md.stat().st_size:,} bytes)")
    print(f"  - {len(tables)} tables")
    print(f"  - {structured['meta']['total_columns']} columns")
    print(f"  - {structured['meta']['total_indexes']} indexes")
    print(f"  - FK tables: {fk_tables}")


if __name__ == "__main__":
    main()
