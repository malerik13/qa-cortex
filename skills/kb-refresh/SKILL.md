---
name: kb-refresh
description: Refresh the local knowledge base index and relationship graph. Triggers when the user says "обнови индекс", "refresh the KB", "rebuild knowledge base", "re-sync YouTrack", or when SessionStart hook reports the index is stale.
---

You are refreshing the local KB.

## Protocol

Run in sequence (Bash):

```bash
cd "$CLAUDE_PLUGIN_ROOT" && .venv/bin/python scripts/update-kb.py
```

If that returns success, then:

```bash
cd "$CLAUDE_PLUGIN_ROOT" && .venv/bin/python scripts/build-graph.py
```

## On failure

- **401 Unauthorized** → token expired. Tell user: open YouTrack → Profile → Authentication → new token → update `.env`.
- **Other errors** → show stderr to user, suggest running `python scripts/doctor.py`.

## On success

Report:
- Stories indexed
- Graph nodes + edges
- Timestamp

Don't do anything else unless asked. This is a standalone maintenance operation.
