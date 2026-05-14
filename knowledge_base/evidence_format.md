# Evidence Comment Format — YouTrack QA reporting

> **Calibrated 2026-05-11** from TRD-13668 + TRD-12728 sessions.
> **Trigger when loaded:** brain writing evidence comment for QA subtask or parent test ticket.
> **Authority:** hand-curated rule per Yaroslav. Brain MUST follow this structure for every evidence comment.

---

## Why this exists

Two failure modes calibrated against:

1. **TRD-13668 (2026-05-11)** — brain wrote evidence as flat "subtype → header" table without AC mapping. Yaroslav required rewrite. **Reason:** evidence без AC-привязки нечитаемо для review и не доказывает покрытие.

2. **TRD-12728 (2026-05-11)** — screenshots без URL в адресной строке. **Reason:** screenshot без env / entity / surface = половина evidence value потеряна.

---

## Two hard requirements

### Requirement 1 — Per-AC structure (one row per sub-AC)

❌ **Wrong:** общая таблица подтипов / surfaces / sections без явной привязки к AC-номерам.

✅ **Right:** каждый sub-AC (AC #1.1.1, AC #1.2, AC #1.4.3 ...) = отдельная строка с:
- **Requirement** — verbatim or short citation from AC text
- **Evidence** — URL + observed value + ✅/❌

### Requirement 2 — Screenshot under each AC group

✅ Каждая группа AC (или каждый sub-AC если визуально разные) получает **inline screenshot** с подписью.

Screenshot rules (combined with `qa_workflow.md` Phase 3):
- **Address bar visible** (URL shows env, entity, surface)
- **macOS `screencapture`** preferred over Playwright page-only screenshot
- One screenshot can cover multiple sub-AC of same group (caption lists all covered)

---

## Structure template

```markdown
Env: <full-url-base> | Account: <role>

**AC #X.Y — <Section name>**

| Sub-AC | Requirement | Evidence |
|---|---|---|
| X.Y.1 | <exact requirement> | `<url>` — observed: **<value>** ✅ |
| X.Y.2 | <exact requirement> | `<url>` — observed: **<value>** ❌ → bug TRD-NNNNN |

![screenshot-filename.png](<youtrack-attachment-url>)
*AC X.Y.1, X.Y.2 — <what this screenshot proves>*

---

**AC #X.Z — <Next section>**

| Sub-AC | Requirement | Evidence |
|---|---|---|
| X.Z.1 | ... | ... |

![screenshot-name.png](<url>)
*<caption>*

---

(repeat per AC group)
```

---

## Screenshot upload technique (YouTrack)

YouTrack attachments via REST API — used because MCP `add_comment` doesn't handle file uploads:

```bash
source .env
curl -sS -X POST \
  -H "Authorization: Bearer $YOUTRACK_TOKEN" \
  -F "file=@<path-to-file>.png;type=image/png" \
  "https://[your-youtrack]/api/issues/<TRD-ID>/attachments?fields=id,name,url"
```

Response:
```json
{ "id": "...", "name": "...", "url": "/api/files/..." }
```

Prepend `https://[your-youtrack]` to the `url` field. Use in markdown as:

```markdown
![filename.png](https://[your-youtrack]/api/files/...)
*caption on next line, italic*
```

---

## Application checklist

Before posting evidence comment to YouTrack:

- [ ] Structure mirrors **AC numbering** (X.Y.Z), not execution order
- [ ] Each sub-AC has its own row in table
- [ ] Each AC group has an inline screenshot
- [ ] Every screenshot has italic caption explaining what it proves
- [ ] Every screenshot has visible address bar (URL)
- [ ] Filename pattern: `trd-<id>-ac<X.Y.Z>-<surface>-<verdict>.png`
- [ ] `---` separator between AC groups
- [ ] Top of comment: `Env: <url> | Account: <role>` line
- [ ] Pass = ✅, Fail = ❌ → bug-link, Skip/N/A = ⚠ (rare, justify in caption)

---

## Anti-patterns

| ❌ Wrong | ✅ Right |
|---|---|
| Flat table «Surface → result» | Per-AC rows with sub-AC numbers |
| Screenshot dump at bottom | Screenshot under each AC group with caption |
| `[screenshot uploaded]` placeholder | Actual `![]()` markdown embed with attachment URL |
| Page-only screenshots (Playwright) | Full-window screenshots showing address bar |
| "Tested all surfaces — see attachments" | Explicit observed value per sub-AC in table cell |
| Caption = filename | Caption = what the screenshot proves (text) |

---

## Source

- TRD-13668 calibration round 2026-05-11 (originated requirement)
- TRD-12728 retest 2026-05-11 (screenshot-with-URL rule)
- Yaroslav feedback memory: `~/.claude/projects/-Users-[test-user]-Documents-[COMPANY]/memory/feedback_evidence_format.md`
