---
description: Build a full test plan from a YouTrack ticket's Acceptance Criteria
argument-hint: {TICKET_PREFIX}-XXXXX
---

You are producing a test plan for the ticket the user named. Follow these steps precisely.

## Step 1 — Load the ticket

Call the YouTrack MCP tool `get_ticket` with `$ARGUMENTS`. Then call `get_comments` on the same ticket to capture any clarifications from the team (devs or PO often refine AC in comments).

If the ticket is not found, stop and ask the user to double-check the ID.

## Step 2 — Extract AC

From description + comments, extract the **explicit Acceptance Criteria**. If AC are not explicit, say so — don't invent them. Ask the user whether to proceed with your inferred expectations or to escalate to PO first.

## Step 3 — Load related context

Call `get_linked_tickets $ARGUMENTS`. Note parent story, child tasks, and related tickets. These inform the **Regression** section.

## Step 4 — Build the plan

Output a test plan with these exact sections in English:

```markdown
# Test Plan — $ARGUMENTS: <summary>

## 🎯 Acceptance Criteria (from ticket)
<bulleted list — verbatim or paraphrased, no invention>

## 🔗 Related tickets (regression scope)
<list from get_linked_tickets, each with one-line relevance note>

## ✅ Happy Path
<numbered steps: main scenario per AC>

## 🧪 Edge Cases
<numbered list: boundary values, empty/large inputs, 0/negative, off-by-one>

## ❌ Negative Cases
<numbered list: what MUST NOT work; permission denials; invalid inputs>

## 🔁 Regression
<from related tickets: areas that may break nearby>

## 💻 Environment
<suggest: staging / staging-ca / release / [release-alt] — based on ticket version/area>

## ⚠️ Open questions
<anything ambiguous in AC that needs PO/Dev clarification>
```

## Step 5 — Offer next action

End with: "Ready to run this plan manually, or want me to execute the Happy Path in the browser (Claude in Chrome)?"

Never auto-execute. Always wait for user to say yes.
