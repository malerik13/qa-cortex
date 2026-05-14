---
description: Guide the QA through writing a bug report in the [COMPANY] EN template
argument-hint: <short description of what's wrong>
---

You are helping the QA write a bug report. **Output must be in English**, regardless of how the user phrases the issue.

## Step 1 — Gather facts

Ask the user these questions **one by one** (wait for answers), unless they already provided them in `$ARGUMENTS`:

1. **What ticket/feature does this touch?** (we'll search YouTrack for the User Story)
2. **Environment?** (staging / staging-ca / release / [release-alt] / demo / prod)
3. **Steps to reproduce** (exact clicks/actions)
4. **Expected result** per AC
5. **Actual result** observed
6. **Client/Account/Entity IDs** involved (if any)
7. **Screenshots / video / console logs** available?

## Step 2 — Find the parent User Story

When the user names the area (e.g. "2FA modal", "Google Sheets export"):
- Call `search_tickets` with a YouTrack query like `#{User Story} <keywords>`
- If nothing relevant, check `search_knowledge_base` for older context
- Offer the top 3 matches to the user and ask them to pick the right one

## Step 3 — Check it's not a known bug

Search YouTrack for recent bugs in the same area:
- `#{Bug} <keywords> created: -30d .. Today`
- Show the user any matches. If there's a duplicate, stop and suggest linking to existing bug instead.

## Step 4 — Fill the template

Use the [COMPANY] bug-report template verbatim (headings with emojis, required sections):

```markdown
## 📌 Prerequisites

<what must be configured to reproduce>

## 🔍 Entity / Client Identifier

* **Client ID:**
* **Account ID / Document ID / Order ID / other:**
* **Role / Agent ID (if applicable):**

## 📝 Steps to Reproduce

1. ...
2. ...
3. ...

## ✅ Expected Result

<what should happen per AC of {TICKET_PREFIX}-XXXXX>

## ❌ Actual Result

<what actually happens>

## 💻 Environment

* OS/Browser:
* Environment:
  * [ ] `staging`  [ ] `staging-ca`  [ ] `release`  [ ] `[release-alt]`  [ ] `demo`  [ ] `production`

## 📖 User Story / Requirement

* [{TICKET_PREFIX}-XXXXX — story title]

## 📂 Related Test Cases

## 📎 Additional Information

<screenshots, video, console, network>
```

## Step 5 — Preview, don't submit

Call `preview_ticket_payload` with the assembled content. Show the payload to the user.

**Then ask:** "Create this bug in YouTrack? [yes / edit / cancel]"

Do NOT call any write tool until user replies "yes". If they say "edit", revise the relevant section and show again.

## Formatting rules

- Pure Markdown, CommonMark. Blank line before every list and after every heading.
- Checkboxes: `[ ]` unchecked, `[x]` checked.
- No Russian anywhere — the team is international, EN is standard.
- Never invent AC. If you can't find the parent story, flag it and ask user.
