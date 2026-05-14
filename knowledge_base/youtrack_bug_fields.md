# YouTrack — Bug creation field map (TRD project)

> Reference for creating bugs via YouTrack REST API.
> Built from real create attempts on 2026-04-29 (TRD-13752, TRD-13753, TRD-13754).
>
> Use when MCP `youtrack` server's `create_ticket` is not available and direct
> API calls are needed.

---

## Endpoint

```
POST https://youtrack.scalefinal.io/api/issues?fields=id,idReadable,summary
Authorization: Bearer <YOUTRACK_TOKEN from .env>
Content-Type: application/json
```

Project ID for `TRD` (B2B Trading): **`0-9`**.

---

## Required custom fields (workflow rules — bug creation fails without them)

YouTrack returns `Field required` errors one-by-one. The full set of mandatory
fields for a Bug in TRD project:

| Field | API `$type` | Sample value | Notes |
|---|---|---|---|
| `Type` | `SingleEnumIssueCustomField` | `Bug` | always `Bug` for bugs |
| `Priority` | `SingleEnumIssueCustomField` | `Critical`/`Major`/`Normal`/`Minor` | match the impact, not your enthusiasm |
| `To Release Notes` | `SingleEnumIssueCustomField` | `No` | bugs always `No` (only User Stories go into client release notes) |
| `Subsystem` | `MultiEnumIssueCustomField` | `[{"name": "CRM"}]` | usually `CRM` for our scope; multi-select |
| `Product` | `MultiEnumIssueCustomField` | `[{"name": "MCRM"}]` | usually `MCRM`; multi-select |
| `Stack` | `SingleEnumIssueCustomField` | `Backend`/`Frontend`/`Testing`/`Localization`/`Design`/`Multiple` | where the fix likely lives |
| `Affected version` | `MultiVersionIssueCustomField` | `[{"name": "3.0"}]` | take from parent User Story; multi-select |
| `Release Version` | `SingleVersionIssueCustomField` | `{"name": "3.0"}` | **must match parent User Story** Release Version |
| `BSource` | `MultiEnumIssueCustomField` | `[{"name": "feature-test"}]` | values: `feature-test` (during AC validation), `regress-test`, `prod`, `internal`; multi-select |

> ⚠️ Be careful with `MultiEnum` vs `SingleEnum`: same name appearing on different
> tickets may have different actual types. If create returns `Incompatible field
> type: <id>`, flip Single ↔ Multi (Multi wraps in `[…]`).

Sample minimal payload:

```json
{
  "project": {"id": "0-9"},
  "summary": "[TRD-XXXXX] Short title",
  "description": "## Markdown body…",
  "customFields": [
    {"name": "Type", "$type": "SingleEnumIssueCustomField", "value": {"name": "Bug"}},
    {"name": "Priority", "$type": "SingleEnumIssueCustomField", "value": {"name": "Major"}},
    {"name": "To Release Notes", "$type": "SingleEnumIssueCustomField", "value": {"name": "No"}},
    {"name": "Subsystem", "$type": "MultiEnumIssueCustomField", "value": [{"name": "CRM"}]},
    {"name": "Product", "$type": "MultiEnumIssueCustomField", "value": [{"name": "MCRM"}]},
    {"name": "Stack", "$type": "SingleEnumIssueCustomField", "value": {"name": "Backend"}},
    {"name": "Affected version", "$type": "MultiVersionIssueCustomField", "value": [{"name": "3.0"}]},
    {"name": "Release Version", "$type": "SingleVersionIssueCustomField", "value": {"name": "3.0"}},
    {"name": "BSource", "$type": "MultiEnumIssueCustomField", "value": [{"name": "feature-test"}]}
  ]
}
```

Auto-filled by YouTrack:
- `State` → `Submitted`
- `Assignee` → currently routes to **Vladislav Zhelihovsky** (BE lead?). Override only if the bug is clearly outside backend scope.

---

## Tags

- Tags are a **separate entity**, not a custom field. Two access points:
  - `POST /api/issues/{id}/tags` with body `{"id": "<tag-id>"}` — applies an existing tag.
  - `GET /api/issueTags?fields=id,name` — list global tags. Tag `1st cohort` was created on 2026-04-29 with id `8-339`.
- The same tag also appears in `customFields` as `Tags` (`MultiEnumIssueCustomField`). Both representations show the same data; updating via the `/tags` endpoint is sufficient.

### When to apply `1st cohort`

Per `knowledge_base/insights.md` Insight 13 — only when **all three** are true:
1. Contradicts the **most obvious AC** (main feature, not edge case).
2. Reproduces with the very first happy-path attempt.
3. A 60-second smoke from the dev would have caught it pre-PR.

Don't tag for: edge-cases, secondary-AC violations, label-only defects, env-specific quirks.

---

## Subtask link to parent User Story

YouTrack link types (from `/api/issueLinkTypes`):
- `Subtask` (`151-3`): source-to-target = `parent for`, target-to-source = `subtask of`.

To make `TRD-NEW` a subtask of `TRD-PARENT` (so the new bug is **child**):
```bash
# Get internal id of parent first
PARENT_ID=$(curl -sS -H "Authorization: Bearer $YOUTRACK_TOKEN" \
  "https://youtrack.scalefinal.io/api/issues/TRD-PARENT?fields=id" | jq -r '.id')

# Get internal id of new bug
NEW_ID="3-XXXXX"   # from create response

# POST FROM the parent's side with direction "s" (source-to-target = parent for)
curl -sS -X POST -H "Authorization: Bearer $YOUTRACK_TOKEN" \
  -H "Content-Type: application/json" \
  --data "{\"id\":\"$NEW_ID\"}" \
  "https://youtrack.scalefinal.io/api/issues/TRD-PARENT/links/151-3s/issues?fields=idReadable"
```

⚠️ **Common mistake:** posting from the new bug's side with direction `s`
makes the **new bug** the parent — the link will appear inverted. If you see
`Subtask / OUTWARD: [TRD-PARENT]` from the new bug's perspective, it is wrong;
correct is `Subtask / INWARD: [TRD-PARENT]`.

Verify with:
```bash
curl -sS -H "Authorization: Bearer $YOUTRACK_TOKEN" \
  "https://youtrack.scalefinal.io/api/issues/TRD-NEW?fields=links(linkType(name),direction,issues(idReadable))"
```

---

## Attachments (screenshots, videos)

```bash
curl -sS -X POST -H "Authorization: Bearer $YOUTRACK_TOKEN" \
  -F "file=@/path/to/screenshot.png;type=image/png" \
  "https://youtrack.scalefinal.io/api/issues/TRD-NEW/attachments?fields=id,name,url"
```

- Use **descriptive file names**: `bulk-send-modal-button-label.png`, not `Screenshot 2026-04-29 ….png`.
- Reference the attachment in the description (`(see attached \`file.png\`)`) so the dev knows where to look.

---

## Updating description after create

```bash
curl -sS -X POST -H "Authorization: Bearer $YOUTRACK_TOKEN" \
  -H "Content-Type: application/json" \
  --data '{"description": "…"}' \
  "https://youtrack.scalefinal.io/api/issues/TRD-NEW?fields=idReadable"
```

The same endpoint accepts `customFields` for partial updates.

---

## Discovering valid values for Enum/Version fields

```bash
# 1. Get the customField id from any existing ticket:
curl -sS -H "Authorization: Bearer $YOUTRACK_TOKEN" \
  "https://youtrack.scalefinal.io/api/issues/TRD-13526?fields=customFields(name,projectCustomField(id))" | jq

# 2. List values from the bundle:
curl -sS -H "Authorization: Bearer $YOUTRACK_TOKEN" \
  "https://youtrack.scalefinal.io/api/admin/projects/0-9/customFields/<projectCustomFieldId>/bundle/values?fields=name,id&\$top=200"
```

`projectCustomField` IDs observed (TRD project):
- Type → `157-44`
- Priority → `157-45`
- State → `157-42`
- Product → `157-493`
- Subsystem → `157-52`
- Stack → `157-106`
- BSource → `157-530`
- Affected version → `157-524`
- To Release Notes → `157-50`

---

## Quick smoke

After every create, run this and screenshot for sanity:

```bash
curl -sS -H "Authorization: Bearer $YOUTRACK_TOKEN" \
  "https://youtrack.scalefinal.io/api/issues/TRD-NEW?fields=idReadable,summary,tags(name),customFields(name,value(name)),links(linkType(name),direction,issues(idReadable))"
```

Verify: required fields populated, tag applied, subtask link points INWARD on the new bug.
