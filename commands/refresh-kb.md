---
description: Refresh the local User Stories index from YouTrack
---

Run the KB refresh. Use Bash to execute:

```
cd ${CLAUDE_PLUGIN_ROOT:-.} && .venv/bin/python scripts/update-kb.py
```

After it finishes:

1. Report how many stories were indexed and the new timestamp.
2. Offer to also rebuild the relationship graph: `.venv/bin/python scripts/build-graph.py`.
3. Remind: if YouTrack API returned 401, check `.env` — the token likely expired.
