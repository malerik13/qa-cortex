---
description: Map the relationship graph around a ticket — what connects, what might break
argument-hint: {TICKET_PREFIX}-XXXXX
---

You are building a regression-scouting view around a ticket.

## Step 1 — Direct links

Call `get_linked_tickets $ARGUMENTS`. Group by link type (parent, child, duplicates, relates to).

## Step 2 — Second-degree context

For each parent story: call `get_ticket` briefly (summary + module from custom fields).
For each child: list status — Done / In Progress / Open / Won't Fix.

Don't fetch more than 10 tickets total — we care about map, not dump.

## Step 3 — Nearby area search

Extract keywords from the ticket's summary (module, feature, UI element). Run one additional search:

`search_tickets` with `#{Bug} <keywords> created: -60d .. Today` — recent bugs in the same area.

## Step 4 — Render the map

```markdown
# Relationship map — $ARGUMENTS

## 🎯 This ticket
<id>: <summary>
Status: <status>, Version: <version>

## ⬆️ Parent (what this implements)
<list>

## ⬇️ Children (sub-tasks)
<list with statuses>

## ↔️ Related (informational)
<list with one-line why-it-matters>

## 🐞 Recent bugs in the area (last 60 days)
<list, or "none found">

## ⚠️ Suggested regression focus
<3–5 bullet areas likely to be affected by changes in this ticket>
```

End with: "Want a full test plan for one of these? Run `/test {TICKET_PREFIX}-XXXXX`."
