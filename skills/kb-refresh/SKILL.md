---
name: kb-refresh
description: Refresh the local knowledge base index and relationship graph. Triggers when the user says "обнови индекс", "refresh the KB", "rebuild knowledge base", "re-sync YouTrack", or when KB indexes are stale.
---

You are refreshing the local KB indexes. This is a Tier 2 operation (auto-generated indexes — no explicit approval needed).

## Protocol

Run in sequence from the project root:

```bash
python3 scripts/refresh-flows-index.py
```

If that returns success, then:

```bash
python3 scripts/refresh-product-map.py
```

## On failure

- **401 Unauthorized** → token expired. Tell user: open YouTrack → Profile → Authentication → new token → update `.env`.
- **Script not found** → verify `scripts/refresh-flows-index.py` and `scripts/refresh-product-map.py` exist.
- **Other errors** → show stderr to user.

## On success

Report:
- Flows indexed (count from `flows/_index.json`)
- Product map modules (count from `knowledge_base/product_map.json`)
- Timestamp
- Git diff stats for changed files

Don't do anything else unless asked. This is a standalone maintenance operation.
