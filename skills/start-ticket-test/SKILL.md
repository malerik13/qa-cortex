---
name: start-ticket-test
description: Start QA lifecycle on a TRD ticket. Pre-loads your product context (YouTrack ticket via MCP, <test-mgmt> cases with steps, linked tickets, comments, bugs index), writes intake artefact, runs Phase 1.5 (QA subtask idempotency check + create). Optionally delegates to qa-orchestra agents in Phase 3+ when diff/running app available. Triggers when Yaroslav says "Тестируем <TICKET>-XXXXX", "Тестирование <TICKET>-XXXXX", "продолжай тестирование <TICKET>-XXXXX", "Full re-test <TICKET>-XXXXX staging + release", "валидируй <TICKET>-XXXXX", "протестировать тикет <TICKET>-XXXXX", or pastes a YouTrack ticket URL (https://<ticketing>.scalefinal.io/issue/<TICKET>-XXXXX/...) WITH OR WITHOUT explicit verb — URL alone is sufficient signal, default intent = test.
---

You orchestrate the 6-phase QA lifecycle for a TRD ticket. Pre-load your product context, build intake, run Phase 1.5 idempotency, surface a Cockpit summary for Yaroslav.

**Pre-condition:** `qa_persona.md` already loaded (mandatory by CLAUDE.md trigger).

---

## Step 1 — Recognize intent

Parse user message for:
- **<TICKET>-XXXXX** identifier
- **Intent verb**:
  - `test` (default) — full lifecycle Phase 0→6
  - `prep` / «подготовь» / «разверни контекст» — Phase 1 only, stop
  - `retest` / «перепроверь» / «после фикса» — jump to Phase 5
  - `status` — single-ticket pulse (no testing, returns to chat)

**STOP if <TICKET>-ID missing** — ask: «Какой тикет? Например `Тестируем <TICKET>-12345`».

If user pasted URL — extract <TICKET>-ID via regex.

---

## Step 2 — Set journal mission

```bash
scripts/journal.sh mission "{INTENT} <TICKET>-{ID}"
```

---

## Step 3 — Pre-load context (PARALLEL batch — HARD CHECKPOINT)

**MUST be one assistant message with multiple `tool_use` blocks** — NOT 4 separate messages. Sequential execution is a regression — wastes time on independent reads.

```
SINGLE message, 4 parallel tool_use blocks:
  block 1: mcp__plugin_qa-cortex_<ticketing>__get_ticket(ticket_id="<TICKET>-XXXXX")
  block 2: mcp__plugin_qa-cortex_<ticketing>__get_linked_tickets(ticket_id="<TICKET>-XXXXX")
  block 3: mcp__plugin_qa-cortex_<ticketing>__get_comments(ticket_id="<TICKET>-XXXXX", max_results=50)
  block 4: mcp__plugin_qa-cortex_allure__find_test_cases_by_issue(
             issue_id="<TICKET>-XXXXX",
             include_scenario=true     ← MANDATORY (boolean true, NOT string "true")
           )
```

**Anti-pattern (DO NOT):** call them one-by-one across 4 messages. This is what brain did in <TICKET>-13822 retest — sequential, not parallel. Wastes ~3-4 round trips of latency.

**How to verify in own behavior:** when constructing the response that fires these tools, check that all 4 are emitted in the same `<assistant>` block. Если ловишь себя за «вызвал get_ticket, теперь жду результат, потом get_linked_tickets» — это regression, останови и пакуй в parallel.

**Conditional KB reads** (only if ticket area matches — don't load all):

| Read | When |
|---|---|
| `knowledge_base/insights.md` | Ticket touches email/2FA/KYC/export/swap topics |
| `knowledge_base/business_rules.md` | 2FA / hierarchy / export / role keywords in AC |
| `knowledge_base/db_naming_map.md` | Data layer / DB queries needed |
| `knowledge_base/db_diff__stage_vs_release.md` | Cross-env testing explicit |
| `knowledge_base/ui_flows.md` | UI nav for Role/Desk/Agent areas |

**Bugs index grep** (defect clustering signal):

```bash
python3 -c "
import json
data = json.load(open('knowledge_base/bugs.json'))
keywords = ['<feature-keyword-1>', '<feature-keyword-2>']
matches = [b for b in data['bugs']
           if any(k in b['summary'].lower() or k in b.get('preview','').lower() for k in keywords)]
for b in matches[:15]:
    print(f'{b[\"id\"]:<10} {b[\"status\"]:<20} {b[\"summary\"][:80]}')
"
```

---

## Step 4 — Write intake artefact

Write `qa-output/intake.md`:

```markdown
\`\`\`json qa-orchestra
{
  "agent": "qa-cortex:start-ticket-test",
  "version": "1.1.0",
  "verdict": "ready",
  "ticket_id": "<TICKET>-XXXXX",
  "intent": "test",
  "summary": "<ticket summary>",
  "ac_count": <N>,
  "linked_tickets": ["<TICKET>-X", "<TICKET>-Y"],
  "allure_cases": [<list of {id, name, steps_count}>],
  "past_bugs": [<list of {id, status, summary}>]
}
\`\`\`

# <TICKET>-XXXXX — Pre-flight Intake

## Ticket summary
<...>

## Acceptance Criteria (verbatim — quote, don't paraphrase)
<...>

## Linked tickets (graph)
<...>

## Existing <test-mgmt> coverage (cases + scenarios)
<...>

## Past bugs in area (cluster signal)
<...>

## Open questions to PO
<...>

## Environment + roles to test
<see context/CONTEXT.md for env URLs + credentials>
```

---

## Step 4.5 — Flow recipe lookup (token amortization, opt-in Phase A)

Per design doc `knowledge_base/design_docs/flow_cache_v1.md` (v1.0). **Phase A status — opt-in, ask Yaroslav before using.**

### Lookup logic

```bash
# Read index (small file, cheap)
cat flows/_index.json | python3 -c "
import json, sys
idx = json.load(sys.stdin)
trd = '<TICKET>-XXXXX'
area_keywords = ['<from ticket summary>']  # e.g. ['email','reset','auth']

# Strategy 1: TRD direct match
direct = idx.get('by_trd', {}).get(trd, [])

# Strategy 2: tag/area match
candidates = set(direct)
for tag in area_keywords:
    candidates.update(idx.get('by_tag', {}).get(tag, []))

# Hydrate full records
recipes = [r for r in idx['recipes'] if r['flow_id'] in candidates]
print(json.dumps(recipes, indent=2))
"
```

### Surface format to Yaroslav

If recipes found:

```
🔍 Flow recipe lookup:
   Found N candidate(s) for <TICKET>-XXXXX:
     ✓ <flow_id> (verified <X days ago>, replayed <N>×, status: <skeleton|active>)
        — fits <Phase 3 / login / navigation>
     ⚠ <flow_id> (last_verified: never / stale > 30 days) — refresh suggested

   Estimated savings if used: ~<replay_tokens × N> tokens vs full discovery.

   [yes use them / discover anyway / refresh stale first]
```

If no recipes match:

```
🔍 Flow recipe lookup:
   No recipes match <TICKET>-XXXXX area. Discovery mode for Phase 3.
   (Recipe will be auto-distilled at Phase 3 close — Phase B feature.)
```

### Opt-in protocol (Phase A only)

**Phase A = manual approval gate.** Brain shows lookup result, Yaroslav decides:
- `да use` → load recipe(s) at Phase 3 start, follow verified path
- `discover anyway` → full Tier 1 discovery, ignore recipe (e.g. for verification refresh)
- `refresh stale` → run recipe in verify-mode, update `last_verified` + selectors if drifted
- silence/no answer → default to discover (don't auto-use unverified recipes)

**Anti-pattern:** silently use a recipe without surfacing the lookup result. Audit trail requires explicit Yaroslav decision in Phase A.

### Honest limitations (Phase A)

- All starter recipes are **`status: skeleton`** — selectors are placeholders. First use enters partial-discovery mode (verifies + fills in selectors), saves updated recipe.
- No auto-distillation yet (Phase B feature).
- No Playwright promotion (Phase C feature).
- Recipe library currently small (3 starter recipes). Most TRDs won't have a match — and that's fine, library grows organically.

---

## Step 5 — Phase 1.5: QA subtask idempotency (HARD CHECKPOINT)

This is the most-skipped step. **NO silent reasoning** — call tool OR surface bracket-format-N/A. See CLAUDE.md anti-pattern #9.

### 5a — If ticket type = User Story (most common testing target)

```
STOP — call tool:
  mcp__plugin_qa-cortex_<ticketing>__find_qa_subtasks(parent_id="<TICKET>-XXXXX")
```

```
STOP — surface result in this exact format:

  📋 Phase 1.5 idempotency check:
     Existing QA subtasks: [list <TICKET>-IDs or "none"]
     Recommendation: [USE_EXISTING <TICKET>-YYYY / CREATE_NEW / AMBIGUOUS — N candidates]
     Reasoning: <one line>
```

```
STOP — wait for Yaroslav's decision: "use existing <TICKET>-X" / "create new" / "skip subtask".
```

### 5b — If ticket type = Bug / Task / Epic (NOT User Story)

Phase 1.5 не применима — но surface block ОБЯЗАТЕЛЕН для audit trail:

```
📋 Phase 1.5 idempotency check:
   Status: N/A — ticket type = [Bug | Task | Epic]
   Reasoning: QA subtask mechanism applies only to User Stories
```

Skip the tool call (correct — tool returns empty for non-User-Story parents). Proceed to Step 6.

**Forbidden:** молча написать «Phase 1.5 N/A» в Cockpit'е без surface блока. Format = audit trail.

If decision = `create new`:
```
mcp__plugin_qa-cortex_<ticketing>__create_qa_subtask(
  parent_id="<TICKET>-XXXXX"
  # NO approved param yet → returns preview
)
```

```
STOP — show preview to Yaroslav. Wait for "да create" / "yes create".
```

On approval:
```
mcp__plugin_qa-cortex_<ticketing>__create_qa_subtask(
  parent_id="<TICKET>-XXXXX",
  approved=true
)
```

Then journal:
```bash
scripts/journal.sh log "Created QA subtask <NEW-TRD> for <TICKET>-XXXXX (Phase 1.5)"
```

**Forbidden in this step:** writing «QA subtask exists (<TICKET>-X)» in chat without first calling `find_qa_subtasks`. Tool call is the audit trail.

---

## Step 6 — Cockpit summary + STOP for approval

Output to chat:

```
🎯 Cockpit — <TICKET>-XXXXX

§0 Bridge
  Object:   <feature one-liner>
  Goal:     <test intent>
  Approach: <Phase 1 done / Phase 1.5 → ?>
  Risk:     <key risk: 2FA blocker / cross-env drift / no <test-mgmt> coverage / etc.>
  Status:   Awaiting Phase 2 approval

§1 AC count: N · <test-mgmt> coverage: M cases (K with scenarios)
§2 Linked tickets: [graph]
§3 Past bugs cluster: [N matches]
§4 PO open questions: [list]
§5 Phase 1.5: [USE_EXISTING <TICKET>-X | CREATED <TICKET>-Y | SKIPPED per Yaroslav]
```

**Do NOT auto-proceed to Phase 2.** Yaroslav approves explicitly.

---

## Step 7 — Phase 2-5: optional qa-orchestra delegation (if approved)

qa-orchestra plugin is **dormant ready** — installed but only invoked when justified. Delegate when:

| Phase | Trigger | Agent |
|---|---|---|
| Phase 2 (test code generation) | «сгенери Playwright тест-код для сценариев» | `Task(subagent_type="qa-orchestra:automation-writer")` |
| Phase 3 (browser validation in batch) | «прогони сценарии через Playwright автономно» | `Task(subagent_type="qa-orchestra:browser-validator")` |
| Phase 5 (post-fix retest, diff available) | «после фикса, что переэтап-овать» | `Task(subagent_type="qa-orchestra:smart-test-selector")` |

**Do NOT invoke qa-orchestra in Phase 1** — agents need diff/running app.

If invoking — pass `qa-output/intake.md` as context. Agents write their outputs to `qa-output/*.md`. Read those files, surface findings to Yaroslav.

If NOT invoking (default, current state) — brain executes the phase itself using Playwright MCP + scenarios from intake.

---

## Step 7.5 — Browser token economy (HARD RULES for Playwright work)

Forensic 2026-05-06 (<TICKET>-13822 retest): `browser_snapshot` сожрал 48% всех tool-result токенов сессии (17 calls × ~5K tokens avg = 22K tokens). Re-snapshot после каждого click'а при том что 90% дерева не меняется. Не делай так.

### Pattern hierarchy (по приоритету ROI)

**1. Ref-based interactions > re-snapshot** (биггест win)

После первого `browser_snapshot` страницы — у тебя уже есть `ref_NN` для всех elements. Кликай/заполняй по ref, НЕ re-snapshot после каждого action:

```
✅ correct:
  browser_snapshot(tabId)         # один раз — получили ref'ы
  browser_click(ref="ref_42")     # без re-snapshot
  browser_type(ref="ref_43", text="...")
  browser_click(ref="ref_44")
  # snapshot ТОЛЬКО если: page navigated / modal opened / явно нужен новый state

❌ regression pattern (сделал в <TICKET>-13822):
  browser_snapshot
  browser_click(ref="ref_42")
  browser_snapshot   ← 5K токенов на повтор того же дерева
  browser_click(ref="ref_44")
  browser_snapshot   ← ещё 5K
  ...
```

**2. `browser_evaluate` для targeted reads > snapshot**

Если нужно прочитать одно значение (счётчик, текст label'а, value поля) — НЕ snapshot, а:

```
browser_evaluate(
  tabId,
  text="document.querySelector('.email-counter').textContent"
)
# Returns ~50 bytes vs ~5000 для snapshot
```

Use cases: проверка счётчиков, статусов, значений полей, наличия класса/атрибута, заголовка модалки.

**3. `browser_network_requests` > snapshot для API verification**

Если проверяем «сработал ли submit» / «отправился ли запрос на reset password» / «что вернул API»:

```
browser_network_requests(tabId, urlPattern="/api/...")
# ~200 bytes per request vs full page snapshot
```

Не нужно смотреть на UI чтобы понять что endpoint отстрелил.

**4. Screenshot > snapshot для visual verification**

Если задача «убедиться что toast появился» / «проверить визуально что layout не сломался»:

```
browser_take_screenshot(tabId)
# ~1.5K tokens (image) vs ~5K (snapshot tree)
```

Trade-off: скриншот не даёт ref'ов для interaction. Используй когда interaction уже не нужен, только проверка.

**5. Save snapshot to file → grep**

Если snapshot ОЧЕНЬ большой (CRM grid с сотнями rows) и нужны конкретные данные:

```
# 1. Snapshot once
browser_snapshot(tabId)
# 2. Sub-agent или manual: save full tree to qa-output/snapshots/<page>.txt
# 3. Grep targeted pattern instead of holding full tree in context
```

### Anti-patterns — never do

1. **Re-snapshot after every action.** Используй ref'ы.
2. **Snapshot для чтения одного значения.** Используй `browser_evaluate`.
3. **Snapshot чтобы проверить API call.** Используй `browser_network_requests`.
4. **Snapshot после navigation на page которая в snapshot'е уже была.** Часто можно reuse refs.

### Когда snapshot ОБЯЗАТЕЛЕН

- Первый заход на страницу — нужно получить ref'ы
- Modal / dropdown / tab opened — структура изменилась
- Auto-generated content (новые rows в grid после save) — нужны новые ref'ы
- Phase 2 первичный orientation на новом UI flow

В этих случаях snapshot — оправданная цена.

---

## Step 8 — Phase 6: close (HARD CHECKPOINT — journal log required)

### 8a — Journal log of test outcome (NON-NEGOTIABLE per CLAUDE.md anti-pattern #4)

**Before any status transition or save** — log the verdict:

```bash
# Pick verdict line based on test result:
scripts/journal.sh log "<TICKET>-XXXXX retest <env>: passed (N AC verified, M scenarios green)"
# OR
scripts/journal.sh log "<TICKET>-XXXXX retest <env>: not reproducible (evidence: <link to qa-output/>)"
# OR
scripts/journal.sh log "<TICKET>-XXXXX retest <env>: blocked — <reason>"
# OR
scripts/journal.sh log "<TICKET>-XXXXX retest <env>: regression-found (filed <TICKET>-NEWID)"
# OR
scripts/journal.sh log "<TICKET>-XXXXX retest <env>: by-design (cited AC #N)"
```

Without this — morning standup doesn't see the evidence chain. **Forbidden:** end test session at "verdict surfaced in chat" without journal log.

### 8b — Status transition (if applicable)

```
mcp__plugin_qa-cortex_<ticketing>__update_ticket_status(...)
  # preview without approved → ask → approved=true
```

### 8c — KB enrichment

If new insight surfaced (`Edit knowledge_base/insights.md` with new entry).

### 8d — Save journal

```bash
scripts/journal.sh save
```

---

## Hard rules

1. **Pre-load context BEFORE Phase 1.5** — Step 3 is non-negotiable. qa-orchestra agents (if used later) need intake.md.
2. **`include_scenario=true` MANDATORY** for `find_test_cases_by_issue` — without it brain sees case names, not steps. Boolean `true`, not string `"true"`.
3. **Phase 1.5 = HARD CHECKPOINT** — see Step 5 STOP gates. Tool call > textual reasoning.
4. **Approval gate before Phase 2** — Yaroslav reviews Cockpit first.
5. **No UI invention** — see CLAUDE.md anti-pattern #6 (verify ladder).
6. **Honest gaps.** If `find_test_cases_by_issue` returns empty → «no <test-mgmt> cases linked», don't fabricate.
7. **Bugs index grep-only** — never `Read knowledge_base/bugs.json` (3.6 MB).
8. **Journal every milestone:** intake done / Phase 1.5 done / Phase 3 case results.
9. **1st cohort verbatim ask** — only at bug-filing time (see CLAUDE.md anti-pattern #5), not in this skill.

---

## Failure modes

- **No TRD found (404)** → ask if user meant a different ID.
- **YouTrack MCP unavailable** → degrade: ask Yaroslav to paste AC, continue.
- **<test-mgmt> index stale** (find returns empty BUT comments mention case IDs) → suggest `python3 scripts/update-allure-index.py`.
- **qa-orchestra agents not loaded** → only matters for Phase 3+. If absent there → fall back to brain-driven Playwright execution.
- **AC missing/unclear** → don't invent. Mark intake "incomplete pending PO".
- **Bugs index >50 matches** → keyword too broad, narrow.
- **2FA Telegram on staging** → per Insight 7, pause for Yaroslav to enter code. Or switch to release-ca.
