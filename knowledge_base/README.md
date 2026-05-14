# `knowledge_base/` — what's in here

Two kinds of content live in this folder:

## 📝 Static, hand-curated (committed to git, rarely changes)

| File | Purpose |
|---|---|
| `product_map.json` | Modules → features → anchor tickets. Navigation index. |
| `business_rules.md` | Critical rules (2FA, hierarchy, export flow). Source of truth. |
| `insights.md` | Accumulated QA gotchas. Add when you learn something non-obvious. |
| `glossary.md` | Domain terms. |
| `slack_insights.md` | Distilled from Slack scrape (see `scripts/slack-ingest.py`). |
| `v1.4.json … v2.9.json` | Legacy version snapshots with features per release. |

**Edit these directly when rules change. Claude reads them for grounding.**

## 🔄 Generated, refreshed from YouTrack (gitignored)

| File | Source |
|---|---|
| `user_stories.json` | `scripts/update-kb.py` — every User Story from project TRD |

Don't edit by hand — it'll be overwritten. Refresh weekly or before a sprint with:

```bash
.venv/bin/python scripts/update-kb.py
```

## Folder rules

- Static files above are the **authoritative product knowledge**. If a rule is wrong, fix the MD/JSON, don't work around it in code.
- Legacy `v*.json` snapshots are kept for historical context — useful when a ticket asks "how did this work in 2.5".
- Generated files rebuild from YouTrack; treat them as cache.
