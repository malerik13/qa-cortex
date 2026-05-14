---
description: Produce a grouped changelog for a CRM version
argument-hint: <version, e.g. 2.9 or 3.0>
---

Summarize what changed in the version `$ARGUMENTS`, grouped by status and module.

## Step 1 — Gather

- Call `get_version_features $ARGUMENTS` (local KB) if the version is in range v1.4..v2.9.
- Also call `search_tickets` with `Release Version: $ARGUMENTS` to get live YouTrack data.
- Merge: local KB provides context/historicalContext; YouTrack provides current status + assignees.

## Step 2 — Group and render

```markdown
# What's in v$ARGUMENTS

## ✅ Done
### <Module A>
- TRD-XXXX: <summary> — <one-line impact>

### <Module B>
- ...

## 🔄 In Progress
...

## 📋 Open
...

## ❌ Won't Fix / Cancelled
...
```

Module list to use: Trading Application, Client Management, Communications, Finance & Operations, Analytics / Dashboard, System Settings, Security/2FA, Other.

## Step 3 — Offer drilldown

End with: "Want full test plan for any of these? `/test {TICKET_PREFIX}-XXXXX`"
