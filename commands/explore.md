---
description: Deep-dive on a feature area — history, AC, known bugs, insights
argument-hint: <feature or area name, e.g. "2FA" or "swap profile">
---

You are producing an expert brief on a product area.

## Step 1 — Local context first

- `search_knowledge_base $ARGUMENTS` — historical snapshots
- Check `knowledge_base/business_rules.md` and `knowledge_base/insights.md` for documented behavior
- Check `knowledge_base/product_map.json` for module mapping

## Step 2 — Live tickets

- `search_tickets` with `#{User Story} $ARGUMENTS` — canonical stories
- `search_tickets` with `#{Bug} $ARGUMENTS created: -90d .. Today` — recent bugs
- Top 5 of each, no more

## Step 3 — Brief

```markdown
# Area brief — $ARGUMENTS

## 🏛 What it is (from local KB)
<2–4 sentences: business purpose, module>

## 📜 How it evolved (historical)
<bulleted timeline across versions, if present in KB>

## 📖 Key User Stories
<top 3, with id + summary + status>

## 🐞 Known bugs (recent)
<top 5 with id + one-line note>

## ⚠️ Known gotchas (from insights.md)
<any documented QA insights in this area>

## 🧪 What to test if changes happen here
<5–8 bullets: critical scenarios, edge cases, integrations>
```

End with: "Want to drill into any ticket? Use `/test {TICKET_PREFIX}-XXXXX` or `/related {TICKET_PREFIX}-XXXXX`."
