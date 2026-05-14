---
description: Decide if observed behavior is a bug or by-design, grounded in AC
argument-hint: <what you observed>
---

You are giving a grounded verdict: bug or by-design. **The verdict must be backed by Acceptance Criteria from YouTrack — never by opinion.**

## Step 1 — Clarify the observation

Reflect back what you understood the user saw: "You observed: <X>. On screen: <Y>. Correct?"

If the user's description is vague, ask for:
- Exact element / screen
- Exact action that triggered it
- What they expected to happen

## Step 2 — Find the governing User Story

- Call `search_tickets` with a YouTrack query `#{User Story} <keywords>`
- If ambiguous, show top 3 candidates and ask user which area applies.
- Also check `insights.md` in `knowledge_base/` — some cases are documented there.

## Step 3 — Read AC carefully

Call `get_ticket` on the chosen User Story. Extract only the **explicit** AC — don't paraphrase in a way that changes meaning.

## Step 4 — Compare

Output your reasoning in this format:

```markdown
## 🔎 Observation
<what the user reported>

## 📖 Governing story
{TICKET_PREFIX}-XXXXX — <title>

## 📜 Relevant AC
> <quote the relevant line(s) from AC>

## ⚖️ Verdict

- [ ] **BUG** — observed behavior contradicts AC
- [ ] **BY DESIGN** — observed behavior matches AC
- [ ] **UNCLEAR** — AC is silent or ambiguous on this point

## 💡 Reasoning
<2–4 sentences: exactly how AC does or doesn't cover the observation>

## Next step
<if BUG: offer /bug — write bug report>
<if BY DESIGN: offer short explanation of the design rationale>
<if UNCLEAR: suggest which stakeholder to ask (PO? Dev? Both?)>
```

## Hard rules

- **Never** return "BY DESIGN" without a quote from AC.
- **Never** return "BUG" without first showing how AC is violated.
- If AC are missing or ambiguous, the answer is **UNCLEAR** — say so and propose who to ask. Do not guess.
