#!/usr/bin/env python3
"""
query-graph.py — Traverse the relationship graph.

Usage:
    query-graph.py TRD-12065             # 1-hop neighbors
    query-graph.py TRD-12065 --depth 2   # 2-hop (transitively)
    query-graph.py --area 2fa            # find by keyword

Output: JSON to stdout.
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

PLUGIN_ROOT = Path(__file__).resolve().parent.parent
GRAPH_FILE  = PLUGIN_ROOT / "kb_cache" / "relationship_graph.json"


def load_graph() -> dict:
    if not GRAPH_FILE.exists():
        sys.stderr.write(f"ERROR: {GRAPH_FILE} not found. Run scripts/build-graph.py first.\n")
        sys.exit(1)
    with open(GRAPH_FILE, encoding="utf-8") as f:
        return json.load(f)


def neighbors(ticket_id: str, graph: dict, depth: int = 1) -> dict:
    nodes = graph["nodes"]
    edges = graph["edges"]

    frontier = {ticket_id}
    visited: set[str] = set()
    out_edges: list[dict] = []

    for _ in range(depth):
        next_frontier: set[str] = set()
        for node in frontier:
            if node in visited:
                continue
            visited.add(node)
            for e in edges:
                if e["from"] == node and e["to"] not in visited:
                    out_edges.append(e)
                    next_frontier.add(e["to"])
                elif e["to"] == node and e["from"] not in visited:
                    out_edges.append(e)
                    next_frontier.add(e["from"])
        frontier = next_frontier

    touched = visited | {e["to"] for e in out_edges} | {e["from"] for e in out_edges}
    return {
        "root":  ticket_id,
        "depth": depth,
        "nodes": {tid: nodes[tid] for tid in touched if tid in nodes},
        "edges": out_edges,
    }


def search_area(keyword: str, graph: dict) -> list[dict]:
    keyword = keyword.lower()
    hits = []
    for tid, meta in graph["nodes"].items():
        if keyword in meta.get("summary", "").lower() or keyword in meta.get("keywords", []):
            hits.append({"id": tid, **meta})
    return hits[:25]


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("ticket_id", nargs="?", help="TRD-XXXXX to explore")
    ap.add_argument("--depth", type=int, default=1)
    ap.add_argument("--area", help="Search by keyword across summaries/keywords")
    args = ap.parse_args()

    graph = load_graph()
    if args.area:
        print(json.dumps(search_area(args.area, graph), indent=2, ensure_ascii=False))
    elif args.ticket_id:
        print(json.dumps(neighbors(args.ticket_id, graph, args.depth), indent=2, ensure_ascii=False))
    else:
        ap.print_help()
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
