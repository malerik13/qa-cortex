#!/usr/bin/env python3
"""
build-graph.py — Build a relationship graph from the User Stories index.

Reads knowledge_base/user_stories.json (produced by update-kb.py) and produces
kb_cache/relationship_graph.json with nodes + edges.

Nodes carry: id, summary, status, version, assignee, keywords.
Edges carry: {from, to, type}. Types: child_of, relates_to.

The graph lets Claude answer "what connects to TRD-X" in O(1) local lookups
without querying YouTrack. For the live/authoritative view, use the MCP tool
get_linked_tickets.

Usage:
    .venv/bin/python scripts/build-graph.py
"""
from __future__ import annotations

import json
import sys
import time
from pathlib import Path

PLUGIN_ROOT = Path(__file__).resolve().parent.parent
INDEX_FILE  = PLUGIN_ROOT / "knowledge_base" / "user_stories.json"
OUTPUT      = PLUGIN_ROOT / "kb_cache" / "relationship_graph.json"


def main() -> int:
    if not INDEX_FILE.exists():
        print(f"ERROR: {INDEX_FILE} not found. Run scripts/update-kb.py first.", file=sys.stderr)
        return 1

    with open(INDEX_FILE, encoding="utf-8") as f:
        data = json.load(f)

    stories = data.get("stories", [])
    nodes: dict[str, dict] = {}
    edges: list[dict] = []

    for s in stories:
        nodes[s["id"]] = {
            "summary":  s.get("summary", ""),
            "status":   s.get("status", ""),
            "version":  s.get("version", ""),
            "assignee": s.get("assignee", ""),
            "keywords": s.get("keywords", []),
        }
        for child in s.get("children", []):
            edges.append({"from": s["id"], "to": child, "type": "child_of"})
        for rel in s.get("related", []):
            edges.append({"from": s["id"], "to": rel, "type": "relates_to"})

    # Deduplicate edges
    seen: set[tuple] = set()
    deduped: list[dict] = []
    for e in edges:
        key = (e["from"], e["to"], e["type"])
        if key not in seen:
            seen.add(key)
            deduped.append(e)

    OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    with open(OUTPUT, "w", encoding="utf-8") as f:
        json.dump({
            "meta": {
                "generated_at": time.strftime("%Y-%m-%d %H:%M UTC", time.gmtime()),
                "source_index": str(INDEX_FILE.relative_to(PLUGIN_ROOT)),
                "nodes":        len(nodes),
                "edges":        len(deduped),
            },
            "nodes": nodes,
            "edges": deduped,
        }, f, ensure_ascii=False, indent=2)

    print(f"✅ Graph: {len(nodes)} nodes, {len(deduped)} edges → {OUTPUT}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
