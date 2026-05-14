---
description: One-time analysis of scraped Slack dialogs — fill gaps in project knowledge
---

You are producing a structured digest of Slack history. **Human review is mandatory before any file is written.**

## Prerequisite

User must have run `python scripts/slack-ingest.py` first. Scraped files are in `kb_cache/slack_raw/*.jsonl`.

If that directory is empty or missing, stop and instruct the user to run the ingest script.

## Step 1 — Inventory

```bash
ls kb_cache/slack_raw/
```

Report which channels were scraped and approximate message counts.

Ask the user: "Analyze all channels, or focus on specific ones? (e.g. #qa-chat, #crm-release)"

## Step 2 — Analyze in chunks

For each channel (or user-selected subset), spawn the `slack-analyzer` subagent with the raw JSONL as input. Ask it to extract:

1. **Product decisions** not reflected in YouTrack (e.g. "we agreed to use Telegram as primary 2FA")
2. **Known bugs / workarounds** discussed casually
3. **Team structure**: who owns what module, who is PO for which area
4. **Production incidents** and lessons learned
5. **Terminology/sleng** that is project-specific
6. **Client-specific quirks** (broker X requires Y configuration)

Subagent returns per-channel structured notes — max 300 words per channel.

## Step 3 — Synthesize

Combine all subagent outputs into a proposed update to `knowledge_base/slack_insights.md`:

```markdown
# Slack-sourced insights
> Last synced: <date>, covering: <channels>

## 🏛 Team & ownership
- Module X owner: @username
- ...

## 🧠 Product decisions (not in YouTrack)
- ...

## 🐞 Known issues & workarounds
- ...

## 💼 Client-specific notes
- ...

## 🗣 Project terminology
- **Term**: meaning

## 🔥 Past incidents (lessons)
- ...
```

## Step 4 — Human review gate

**DO NOT write the file yet.** Show the full proposed content to the user. Ask:

> "Review the digest above. Options:
> - `accept` — write to knowledge_base/slack_insights.md as-is
> - `edit <section>` — modify a section, I'll re-show
> - `discard` — throw away and don't touch the file"

Only after `accept`:

```bash
# Write the approved content to knowledge_base/slack_insights.md
```

## Step 5 — Offer KB enrichment

After writing, ask:

> "Found any facts that belong in knowledge_base/product_map.json or knowledge_base/business_rules.md instead? Propose edits with a diff — I'll review."

## Hard rules

- Never invent. If Slack didn't say it, it isn't a fact.
- Never write to knowledge_base/ without explicit `accept`.
- Strip PII: client emails, phone numbers, access tokens that might appear in Slack messages.
- Keep the final `slack_insights.md` under 2000 words — this is a digest, not a dump.
