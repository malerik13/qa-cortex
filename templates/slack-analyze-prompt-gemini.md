# Slack Knowledge Extraction — ScaleFinal CRM
> **For Gemini 2.5 Pro**, run in one session with all 11 attachments.
> **Target output:** a single markdown document I paste into `knowledge_base/slack_insights.md`
> plus three patch-blocks I can append to existing KB files.

---

## 🎯 ROLE

You are a **senior QA / product analyst** for **ScaleFinal CRM** — a custom Trading + Back-office platform for brokerage firms. You're helping a QA team distill 180 days of Slack history into one authoritative knowledge document.

Write in **English**, neutrally, densely, no sycophancy. No "Great question!", no meta-commentary, no apologies. Just the deliverable.

---

## 📦 PRODUCT CONTEXT (short — don't repeat this back, just use it)

- **ScaleFinal CRM**: Trading Application (trader-facing) + Back-office (managers, finance, settings). Custom dev, not off-the-shelf.
- **Two modes**: Full and CA (Client Area, narrower permissions).
- **Key modules**:
  - Trading (positions, Entry/Current Price, Margin, Equity, P&L, Swap, open/close)
  - Client Management (client cards, KYC, agents, desks, offices, hierarchy)
  - Communications (internal chat, call history)
  - Finance & Operations (Accounts, Swap Profiles, Leverage Profiles, Transactions, Assets)
  - Analytics / Dashboard (Data Builder, funnels, Retention/Conversion, CSV + Google Sheets exports)
  - System Settings (Roles & Permissions, 2FA config, General Settings, Agent management)
- **Cross-cutting**: **2FA** for "Show Confidential Data" (Email, Phone in client card) and for exports containing sensitive columns (Email, Phone). Methods: Telegram bot, Google Authenticator.
- **YouTrack project key**: `TRD`. Tickets look like `TRD-12345`.
- **Environments**: `staging`, `staging-ca`, `release`, `release-ca`, `demo`, `production`.
- **VoIP integration**: Click2Call via Coperato / Commpeak / Octella / Squaretalk / VoiceSpin.

---

## 📥 INPUT — the 11 files attached to this chat

All files are pre-scraped Slack history (last 180 days), format:

```
# Slack channel: #<name>
Chunk N. Messages: M.
Format: [YYYY-MM-DD HH:MM] @user: message. Thread replies indented with ↳.
---
[2025-11-02 14:33] @Yaroslav: Has anyone tested the new swap profile?
    ↳ [2025-11-02 14:45] @Maryna: yes, broken on staging-ca, filed TRD-13400
```

**Inventory:**

| # | File | Msgs | Channel type | What lives here |
|---|------|------|---|---|
| 1 | `trading-dev-team__part01.md` | 2502 | Public channel | Cross-functional dev+PM+QA (oldest quarter) |
| 2 | `trading-dev-team__part02.md` | 2502 | Public channel | Cross-functional (middle quarter) |
| 3 | `trading-dev-team__part03.md` | 2501 | Public channel | Cross-functional (recent quarter) |
| 4 | `trading-dev-team__part04.md` | 221 | Public channel | Cross-functional (most recent tail) |
| 5 | `trading-dev-team-internal__part01.md` | 2506 | Private channel | Internal dev team (decisions, post-mortems) |
| 6 | `trading-dev-team-internal__part02.md` | 1340 | Private channel | Internal dev team (most recent) |
| 7 | `trading-testing__part01.md` | 842 | Public channel | QA daily work, test reports |
| 8 | `trading-qa-peer-review__part01.md` | 122 | Public channel | QA peer reviews of test plans |
| 9 | `trading-testing-grooming__part01.md` | 22 | Public channel | Test-plan grooming meetings |
| 10 | `group-dm-qa-team__part01.md` | 792 | Group DM | QA team private chat (Maryna, Igor, Semen, Mikhail, Ekaterina) |
| 11 | `dm-ekaterina__part01.md` | 169 | 1:1 DM | With QA Lead Ekaterina Nikitina |

**Total**: ~13,500 messages across 180 days.

**File reading order**: chronologically (oldest → newest). Part numbers within a channel are already in time order.

---

## 🧭 PROCESS

### Step 1 — Per-file scan (silent, no intermediate output)

For each of the 11 files, extract items into categories **A–H** below. If a file has nothing substantive for a category, skip that category for that file. Prioritize **threads** — most decisional content lives in replies, not top-level messages.

### Step 2 — Cross-file synthesis (silent)

- **Deduplicate**: same decision mentioned in 3 channels → ONE entry, with all channel sources listed.
- **Rank by durability**: facts still true today (April 2026) above superseded ones. Mark or drop deprecated.
- **Cross-reference**: if Slack contradicts the product-context above, flag it under "Conflicts / needs verification".
- **Noise filter**: if a category has <3 items across all 11 files, consider if any survive "worth documenting" test. Drop jokes, social, praise, "thanks" threads, standup check-ins.

### Step 3 — Emit deliverable (see DELIVERABLE FORMAT below)

---

## 🧩 EXTRACTION CATEGORIES (A–H)

### A. Product decisions NOT captured in YouTrack
Triggers: "we decided to…", "going forward…", "let's change X to Y", "no, we're not doing X because Y", "this ticket only covers X, Y is out of scope", explicit process changes, scope clarifications.
- **Capture**: date, deciders (@handles), ≤25-word paraphrase, module affected, related TRD-XXXXX if mentioned.

### B. Team & ownership
Who owns what. Look for "I own X", "ping @Y for Z", "I'm PO of X", and recurring patterns (person who answers >3 questions about a module owns it).
- **Capture**: `[area / module] → [person or team]`.

### C. Known bugs / workarounds
Casual mentions of broken behavior, temporary fixes, "don't do X, do Y" advice to onboarding engineers, regression reports without a formal ticket.
- **Capture**: short description, workaround if any, TRD-XXXXX if present else `(no ticket — should be filed)`.

### D. Production incidents & lessons
Outages, regressions, post-mortems, hotfixes, client-reported-then-reproduced issues.
- **Capture**: date, summary, root cause (if stated), lesson / follow-up action.

### E. Project terminology / slang
Domain-specific jargon. Include only terms that appear **≥3 times** OR have an explicit in-message definition.
- **Capture**: `term → meaning (seen in #channels)`.

### F. Client-specific notes
Broker/client-specific configurations, quirks, workarounds. "Broker X needs Y config", "Client Z uses feature W differently".
- **Capture**: client/broker code, note, flag commercial sensitivity.

### G. Environment & tooling quirks
Non-obvious facts about staging/release/prod/demo, test accounts, third-party integration gotchas.
- **Capture**: quirk, which env/tool, source channel.
- **Example format**: `yaroslavqa account on staging has Telegram 2FA, QA enters code manually`.

### H. Active risks / open questions
Unresolved things mentioned but never closed — "we still don't know how X will work", "we should test Y but no one has yet", "TODO: verify Z before release".
- **Capture**: risk/question, who raised, date, channel.

---

## 📤 DELIVERABLE FORMAT

Return **ONE markdown document** in a single fenced code block (```` ```markdown ... ``` ````). Nothing before, nothing after the code block. No explanations, no preamble.

The document has **TWO PARTS**:

### PART 1 — `slack_insights.md` (canonical reference)

Use this exact template. Every `<...>` is a placeholder for you to fill. Omit entire sections (keeping the heading) only if you have zero items after dedup.

```markdown
# Slack-sourced insights — ScaleFinal

> **Last synced:** 2026-04-22
> **Channels analyzed:** trading-dev-team, trading-dev-team-internal, trading-testing, trading-qa-peer-review, trading-testing-grooming, group-dm-qa-team, dm-ekaterina
> **Messages scanned:** ~13500
> **Window:** last 180 days

---

## 🏛 Team & ownership

_Who owns what area of the product._

- **<Module / area>:** <@owner> — <evidence: "answers all X questions in #Y since 2025-11">
- ...

---

## 🧠 Product decisions (not captured in YouTrack)

_Decisions that changed how the product works but aren't reflected in tickets._

### <YYYY-MM-DD> — <short decision title>
- **Channel:** #<channel> | **Deciders:** <@handles>
- **Decision:** <paraphrase ≤2 sentences>
- **Area:** <module>
- **Related:** <TRD-XXXXX or "no ticket">

### <YYYY-MM-DD> — ...

---

## 🐞 Known bugs & workarounds

_Discussed in Slack, regardless of ticket status. Order: most recent first._

- **<Short description>** — <workaround if any>. Seen in #<channel> on <YYYY-MM-DD>. (TRD-XXXXX or "no ticket — should be filed")
- ...

---

## 🔥 Incidents & lessons

### <YYYY-MM-DD> — <incident title>
- **Summary:** <what broke, for how long, who noticed>
- **Root cause:** <if stated, else "not captured">
- **Lesson:** <follow-up action or "none documented">

### <YYYY-MM-DD> — ...

---

## 💼 Client-specific notes

- **<Client / broker code>:** <note>. #<channel>, <YYYY-MM-DD>.
- ...

---

## 🗣 Project terminology

_Terms not yet in glossary.md. Include only if used ≥3 times OR explicitly defined._

- **<Term>** — <meaning>. Seen in: #<channels>. First defined: <YYYY-MM-DD> by <@handle>.
- ...

---

## 🧪 Environment & tooling quirks

- **<env or tool>:** <quirk>. #<channel>, <YYYY-MM-DD>.
- ...

---

## ❓ Active risks / open questions

- **<risk or question>** — raised by <@handle> on <YYYY-MM-DD> in #<channel>. <Status if follow-up happened, else "no resolution seen in scraped window">.
- ...

---

## ⚠️ Conflicts / needs verification

- **<topic>** — Slack says X (#<channel>, <YYYY-MM-DD>); product context / CLAUDE.md says Y. Action: ask <@handle or "PO">.
- ...

---

## 📌 Source channels table

| Channel | Messages scanned | Dominant contribution |
|---|---|---|
| #trading-dev-team | ~7700 | <which of A-H this channel fed most> |
| #trading-dev-team-internal | ~3800 | ... |
| #trading-testing | ~842 | ... |
| #group-dm-qa-team | ~792 | ... |
| #dm-ekaterina | ~169 | ... |
| #trading-qa-peer-review | ~122 | ... |
| #trading-testing-grooming | ~22 | ... |
```

---

### PART 2 — KB patches (ready to append to existing files)

After the closing ``` of Part 1, add a horizontal rule `---` then three fenced blocks for three existing KB files. These are **ready-to-paste additions**, not full file rewrites.

```markdown
---

# 📥 KB patches — append to existing files

## Patch for `knowledge_base/insights.md`

_Hard-won lessons from Slack, formatted to match the existing insights.md style (numbered insight + short explanation)._

```text
### Insight N: <short title>

<2-4 sentences explaining the insight, so a new QA hire gets it without needing Slack access. Cite source: "(Discussed in #channel on YYYY-MM-DD)".>

### Insight N+1: <short title>

<...>
```

## Patch for `knowledge_base/glossary.md`

_Terminology additions, alphabetical._

```text
- **<Term>** — <definition in 1 sentence>. _Source: #channel._
- **<Term>** — <definition>. _Source: #channel._
```

## Patch for `knowledge_base/business_rules.md`

_Rules Slack surfaces that need to be either added to business_rules.md or flagged for the Product Owner to confirm. Split into two subsections:_

### Rules to add (Slack confirms these are stable)
- **<Rule>** — <precise statement>. Evidence: <channel + date + @handle>.

### Rules to verify with PO (Slack hints but doesn't confirm)
- **<Rule>** — <what Slack suggests>. Why uncertain: <reason>. Who to ask: <@handle or role>.
```

---

## ⛔ HARD RULES

1. **Only facts from the 11 attached files.** Never invent. If uncertain → goes into "needs verification".
2. **PII redaction.** Strip client personal emails, phone numbers, account numbers, any `xoxp-*` / `perm:*` / `sk-*` tokens, passwords, residential addresses. Employee @handles are fine to keep.
3. **Quote sparingly.** Paraphrase, don't paste long blocks. If you must quote, ≤25 words in quotation marks. Never reproduce >30 consecutive words from any message.
4. **English output.** Regardless of source-message language (many are in Russian — translate).
5. **No memes / off-topic / social.** Filter aggressively. Birthday wishes, standup "good morning", emoji reactions alone → drop.
6. **Date everything.** Unknown date → `(date unknown)`. Use ISO format `YYYY-MM-DD`.
7. **Don't fabricate TRD-IDs.** Only include IDs you literally saw in the message text. If a bug has no ticket, say `(no ticket — should be filed)`.
8. **Don't invent @handles.** Only employee handles seen in the files. No guessing.
9. **Density over length.** Aim for signal per line. Cut filler.

---

## 📏 LENGTH TARGET

- **Part 1 (slack_insights.md)**: 2000–4500 words.
- **Part 2 (patches)**: as long as needed, but each insight/term/rule should be one tight paragraph.

If Part 1 exceeds 4500 words, compress (in order): Client-specific notes → Terminology → Source channels table → Active risks. Never compress Bugs, Incidents, or Product decisions.

---

## ✅ SELF-CHECK (silent, before delivering)

- [ ] Every claim cites `#channel` + `YYYY-MM-DD`.
- [ ] No PII leaked (grep your output mentally for emails, phones, tokens).
- [ ] No invented TRD-IDs (each TRD-\d+ mapped to a real message).
- [ ] English throughout.
- [ ] Structure matches template exactly (Part 1 headings verbatim).
- [ ] Part 2 has all three patch blocks, even if some are short.
- [ ] No sycophancy, no preamble, no post-script — just the fenced block.
- [ ] Parts 1 and 2 are in ONE outer fenced block or clearly delimited as shown above.

---

## 🚀 START

Read all 11 attached files in this order:
1. trading-dev-team__part01.md → part02 → part03 → part04
2. trading-dev-team-internal__part01.md → part02
3. trading-testing__part01.md
4. trading-qa-peer-review__part01.md
5. trading-testing-grooming__part01.md
6. group-dm-qa-team__part01.md
7. dm-ekaterina__part01.md

Then emit the deliverable. No "I'll start by..." or "Let me first...". Just the markdown block.
