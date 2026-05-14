# QA Workflow — End-to-end ticket lifecycle

> Caнonical playbook for "QA receives a TRD → QA closes it Verified". Every phase has clear inputs, outputs, tools, and exit criteria.
> Phase 1 (Preparation) is implemented in `test_prep/MECHANISM.md` and stays the source of truth for that phase.

---

## How to start (the one rule)

**Way #1 — paste a YouTrack link or TRD-ID + intent verb:**

| User says | Intent | First phase |
|---|---|---|
| "тестируй TRD-12345" / "хочу тестировать TRD-12345" | full lifecycle | Phase 1 |
| "подготовь к тестированию TRD-12345" / "разверни контекст" | prep only | Phase 1, stop after |
| "статус по TRD-12345" | pulse only | (orchestrator, no workflow) |
| "перепроверь TRD-12345 после фикса" | re-test | Phase 5 |
| "оформи баг про X" | bug only | Phase 4 (existing bug-report skill) |

**Way #2 — orchestrator picks the next ticket:**
After `/plan-day` proposes order, QA confirms one — workflow starts at Phase 1 for that ticket.

The brain ALWAYS confirms intent verb before executing. "TRD-X" alone (no verb) → ask: "тестировать, готовить, или просто статус?"

---

## The six phases

```
   [INTAKE]
      ↓
 ┌─ Phase 1: Preparation       (test_prep/MECHANISM.md)
 │     ↓                        artefact: test_prep/<TRD-ID>/<TRD-ID>.md
 │  ◊ Yaroslav reviews
 │     ↓
 ├─ Phase 2: Allure launch      (set up the run)
 │     ↓                        artefact: launch ID + cases linked to TRD
 │  ◊ Yaroslav approves
 │     ↓
 ├─ Phase 3: Execution          (run the cases)
 │     ↓                        artefact: each case Pass/Fail with evidence
 │     ↓
 ├─ Phase 4: Defect handling    (per failure — existing bug-report skill)
 │     ↓                        artefact: TRD-XXXXX bug + journal log
 │     ↓
 ├─ Phase 5: Validation         (after dev fixes, re-test)
 │     ↓                        artefact: re-test results, status update
 │     ↓
 └─ Phase 6: Close              (final verified status + KB update)
                                artefact: launch closed, KB enriched, journal saved
```

---

## Phase 0 — Intake

**Triggered by:** TRD link/ID arrives in chat.

**Steps:**
1. Confirm intent verb if ambiguous.
2. Set journal mission via `scripts/journal.sh mission "<one-sentence>"`. Default: "Test TRD-XXXXX end-to-end".
3. State the plan: "Starting Phase 1 (Preparation). Will stop for your review before Phase 2."

**Exit criteria:** mission set, user knows what's about to happen.

---

## Phase 1 — Preparation

**Source of truth:** [`test_prep/MECHANISM.md`](../test_prep/MECHANISM.md). Don't duplicate the mechanism here; it lives there and is battle-tested. Summary of inputs/outputs only:

**Inputs:** TRD-ID, parallel pulls from YouTrack + Allure + KB.

**⚠ Allure tool usage rule:** when calling `find_test_cases_by_issue`, **always pass `include_scenario: true`** (capped at 20 cases by default). Without the flag, brain only sees `[id, name, status]` — no scenario steps — and Coverage Matrix (§6) becomes guessing. The flag triggers live API call per case to fetch full steps + sub-steps + expected results. Slower but correct. If a TRD has >20 linked cases (rare), pass `max_cases: 50` or fetch specific ones via `get_test_case(id)`.

**Output:** `test_prep/<TRD-ID>/<TRD-ID>.md` with the 11 sections:
0. Bridge (situational awareness — 5 blocks)
1. Header
2. Summary AC
3. TL;DR
4. Open questions to PO/PM
5. Order of execution
6. AC ↔ Allure Coverage Matrix
7. Test Plan (Happy / Edge / Negative / gap-fill / Cross / Regression)
8. Regression Risks
9. Data Setup
10. Pre-release checklist

**Exit criteria:** artefact written, 15-line chat summary delivered, **Yaroslav reviews and confirms** before Phase 2 starts.

**Hard rule:** Phase 1 is read-only. No Allure cases created, no YouTrack writes, no actual testing.

### Phase 1 — Non-text attachments in comments (calibrated 2026-05-13 TRD-12743)

When `get_comments` returns content like `[file.pdf]`, `QA Gate: ...pdf`, `.docx`, `.xlsx`, images — brain can't read them with default tools. Don't pretend.

Surface explicitly in Cockpit §3 or §4:

```
📎 Attachments in comments brain can't auto-read:
   • <name.pdf> by <author> — likely contains <inference from name>
   Options:
     (a) Load mcp__pdf-viewer__* via ToolSearch and try
     (b) Yaroslav summarizes 2-3 lines what's in it
     (c) Skip if not blocking
```

For PDFs specifically: `mcp__pdf-viewer__display_pdf` exists (deferred tool). Load if attachment looks load-bearing (QA Gate from PO, specs).

**Calibration TRD-12743 (2026-05-13):** QA Gate PDFs from PO often = **just an Allure cases export**. If `find_test_cases_by_issue` already returned scenarios → PDF likely redundant. Quick check: number of cases in Allure ≈ number of test scenarios mentioned in PDF filename → skip PDF, save load time. Only fetch PDF if Allure coverage looks insufficient OR PDF name suggests non-test content (architecture, design doc, custom spec).

---

## Phase 1.5 — Create QA subtask in YouTrack (public test plan)

**Why this exists:** Phase 1 produces a *local* artefact (`test_prep/<TRD>/<TRD>.md`) that's rich and personal. Phase 1.5 produces a *public* artefact (a [QA] subtask in YouTrack) that's terse, engineering, and visible to the dev/PO team. Same content, two registers.

**Mandatory for every `/start TRD-X test` flow** — apply once per parent TRD, idempotent.

### Steps

1. **Full link-graph review (mandatory before any decision).** Call `create_qa_subtask` WITHOUT `approved` — even just to get the graph. The MCP tool returns a structured preview with:
   - All outward subtasks categorized: `[CR #N]`, `[BE]`, `[FE]`, `[QA]`, `[BA]`, other
   - All inward subtasks (this ticket's parents)
   - Related tickets
   - Per existing [QA] subtask: state, release version, sprint, summary
   - **Brain's recommendation**: `USE_EXISTING` / `CREATE_NEW` / `ASK_QA` with reasoning

   Surface the full graph to Yaroslav. Never decide silently.

2. **Decision tree (based on graph):**

   | Situation | Action |
   |---|---|
   | No [QA] subtask exists | Propose creation (`CREATE_NEW`). Ask Yaroslav to confirm. |
   | Single [QA] exists, same Release Version, not Done/Verified | `USE_EXISTING` — link to it, log to journal. **Don't create new.** |
   | Single [QA] exists, different Release Version (e.g. existing v3.0, new CR is v3.1) | Propose `CREATE_NEW` for current iteration. Brain explains "different release" reasoning. |
   | Single [QA] exists, state Done/Verified | `ASK_QA` — re-open old or create new for current testing? Yaroslav decides. |
   | Multiple [QA] subtasks exist | `ASK_QA` — show all, ask which (if any) covers current scope. |
   | [QA] exists but NOT same parent (e.g. linked to sibling CR ticket TRD-13653) | Treat as `CREATE_NEW` for THIS parent (different ticket, different scope). |

2.5. **Assignee check on `USE_EXISTING`** — added 2026-05-11 (TRD-12728 calibration):

   When `USE_EXISTING TRD-X` recommendation fires, **also check assignee**. Surface:

   ```
   📋 Phase 1.5 — USE_EXISTING TRD-X
      Current assignee: <name>
      [If assignee != Yaroslav]: «Переназначить на тебя?» (yes / no — keep as-is / ask the current assignee first)
   ```

   Don't silently reassign — surface the ownership transfer as a decision point. Existing assignee might be actively working it.

3. **Extract the module name from the parent.**
   - Parent summary often starts with `[Email builder] ...` or `Email builder: ...` or `[KYC] ...`.
   - Module = the bracketed prefix or the colon-prefix word(s).
   - If parent has no clear module prefix → ask Yaroslav: «модуль не очевиден из summary parent'а — какой ставим?».

4. **Construct the title.**
   ```
   [QA] [<module>] <parent-summary-without-prefix>
   ```
   Example: parent `[Email builder] Improve Dashboard / Drilldown for sent emails statistics` → QA subtask `[QA] [Email builder] Improve Dashboard / Drilldown for sent emails statistics`.

5. **Compose the body** — strict English, dry, engineering. Template in `knowledge_base/youtrack_qa_subtask_template.md`. Five sections, 15-30 lines total:
   - **Scope** — what's tested, what's out of scope (1-2 lines)
   - **Approach** — layers (UI / API / DB) + tools used (2-4 lines)
   - **Risks** — top 2-3 with refs to bugs.json duplicates if found (2-4 lines)
   - **AC coverage** — gaps if any, conflicts if any (2-4 lines)
   - **Environment + roles** — which envs (stage / release / both), which roles (Agent / Admin / Super Admin) (1-2 lines)

6. **Approval gate (per `qa_persona.md §6` two-step)**:
   - Show graph + recommendation + proposed payload.
   - Yaroslav says `да create` / `yes create` → re-call `create_qa_subtask` with `approved: true`.
   - If [QA] already exists and Yaroslav still wants new → add `force: true` (e.g. for separate sub-flow scope).
   - Brain returns the new TRD-ID + URL.

7. **Journal log:**
   ```bash
   scripts/journal.sh log "Created QA subtask <NEW-TRD> for <PARENT-TRD> (Phase 1.5)"
   ```
   or, if used existing:
   ```bash
   scripts/journal.sh log "Phase 1.5 — using existing QA subtask <EXISTING-TRD> for <PARENT-TRD>"
   ```

### Custom fields applied (via `apply_commands` in MCP)

| Field | Value | Source |
|---|---|---|
| Type | Task | hardcoded |
| Stack | Testing | hardcoded — marker of QA subtask |
| Subsystem | CRM | hardcoded (override if testing TA-only) |
| Priority | Major (default) / mirrors parent | parent or QA judgement |
| Release Version | mirrors parent | from parent ticket |
| Sprint | current sprint | from current sprint context |
| SP QA | estimate (optional) | QA judgement |
| Assignee | self (Yaroslav) | implicit via token's user |
| Subtask link | OUTWARD ← parent | via `subtask of TRD-XXXXX` command |

### Hard rules

- **English only** in title and body. Per `qa_persona.md §7` language matrix.
- **Engineering register** — no opinions, no hedging, no «I think». Facts + plan.
- **Brevity** — 15-30 lines body. If exceeds, split scope (multiple QA subtasks for sub-stories).
- **Idempotent** — never create duplicate. Existing one wins.
- **Approval-gated** — even though writes are now possible via MCP, two-step approval applies.

### Exit criteria

- QA subtask exists in YouTrack with proper title and fields.
- Linked to parent as Subtask.
- New TRD-ID journaled.
- Yaroslav can navigate parent → see [QA] subtask in linked tickets.

### When to skip Phase 1.5

Only if explicitly told by Yaroslav («без subtask», `/start ... no-subtask`). Default: always do.

---

## Phase 2 — Allure launch setup

**Inputs:** confirmed test plan from Phase 1, list of mapped Allure cases (existing or to-create).

**Steps:**

1. **Identify cases:**
   - For every test plan scenario → either map to existing Allure case (from `find_test_cases_by_issue`) or mark as "to-create".
2. **Create missing cases (each one is approval-gated):**
   - `allure.preview_test_case_payload(...)` → show JSON to Yaroslav.
   - On `yes` → `allure.create_test_case(..., approved: true)`.
   - On `no/edit/cancel` → respect.
   - Each created case immediately journal-logged: `journal.sh log "Created Allure case <id> for TRD-X"`.
3. **Plan the launch (don't create yet — Allure MCP doesn't expose write for launches in this plugin version):**
   - Compose launch metadata: name (e.g. `TRD-12345 — sprint-2.10 verify`), expected test cases, environment (stage / release / etc).
   - Output the launch plan to Yaroslav for him to create in Allure UI manually.
   - Future enhancement: when Allure MCP supports launch creation, automate this step.
4. **Once launch exists in Allure:** Yaroslav provides launch URL/ID → brain stores in `test_prep/<TRD-ID>/<TRD-ID>.md` Phase 2 section.

**Exit criteria:**
- Every test plan scenario has a corresponding Allure case (created or pre-existing).
- Launch exists in Allure with all cases assigned.
- Launch URL/ID recorded in `test_prep/<TRD-ID>/`.
- **Yaroslav approves** to start Phase 3.

**Hard rule:** No `create_test_case` without `approved: true` and explicit `yes` from Yaroslav.

---

## Phase 3 — Execution

**Inputs:** launch with cases ready, environments accessible, test data prepped (per Phase 1 §9).

**Steps per scenario:**

1. **Set up state.**
   - **Default: test on configured test environments** (per business_rules.md §Default test environment).
   - Login as the right role (default: your configured test user — see business_rules.md).
   - Fixture data per `knowledge_base/glossary.md` and `project_test_fixtures.md`.
   - DB pre-state via `scripts/db-query.sh --db <name>` if test depends on initial data.

2. **Run the scenario — BRAIN drives, not the user.**

   ⚠ **Hard rule:** brain выполняет browser-действия САМ. Never ask Yaroslav to "open browser and navigate to X". Per `qa_persona.md Rule 10` (Tool-first reflex) and CLAUDE.md `🤖 Capability declaration`.

   **Browser tool — chrome-devtools-mcp PRIMARY** (calibrated 2026-05-14). Direct CDP over WebSocket — no Playwright runtime, no Chrome extension. Attaches to a persistent Chrome profile (`~/.chrome-cdp-profile`) started via `scripts/launch-chrome-cdp.sh` on port 9222. Login/session/VPN survive across launches. Playwright = fallback only.

   **Setup (once per machine):**
   ```bash
   ./scripts/launch-chrome-cdp.sh             # start (no-op if already up)
   ./scripts/launch-chrome-cdp.sh --status    # verify :9222 alive
   ```

   **Pre-flight (one-time per chat):**
   ```
   ToolSearch(query="select:mcp__chrome-devtools__navigate_page,mcp__chrome-devtools__list_pages,mcp__chrome-devtools__new_page,mcp__chrome-devtools__select_page,mcp__chrome-devtools__click,mcp__chrome-devtools__fill,mcp__chrome-devtools__fill_form,mcp__chrome-devtools__hover,mcp__chrome-devtools__press_key,mcp__chrome-devtools__type_text,mcp__chrome-devtools__wait_for,mcp__chrome-devtools__evaluate_script,mcp__chrome-devtools__take_screenshot,mcp__chrome-devtools__take_snapshot,mcp__chrome-devtools__list_console_messages,mcp__chrome-devtools__list_network_requests,mcp__chrome-devtools__handle_dialog,mcp__chrome-devtools__upload_file,mcp__chrome-devtools__resize_page")
   ```

   **Then:**
   - `list_pages` → confirm CDP attached, get pageIds
   - `select_page(pageId)` OR `new_page(url)` → focus correct tab
   - `navigate_page(url)` → CRM page (session likely active from persistent profile)

   **Execution layers (chrome-devtools-mcp):**
   - **UI** through `mcp__chrome-devtools__*` — `navigate_page`, `take_snapshot` (refs), `click(ref)`, `fill(ref, value)`, `fill_form`, `press_key`. Side-channel: `list_network_requests`, `list_console_messages`.
   - **API** through `evaluate_script` for in-page `fetch`, OR direct curl/httpie via Bash for headless API tests.
   - **DB** through `scripts/db-query.sh --db <env-name> "..."` — verify state matches UI claim. Use `--list` to discover available DBs.
   - **Screenshots** — `take_screenshot` (full-page or per-element). For evidence with address bar visible (mandatory per rule below): use macOS `screencapture` instead, since CDP screenshots don't include browser chrome.
   - **Session recording** — `screencast_start` / `screencast_stop` for bug evidence.
   - **Performance** — `performance_start_trace` / `performance_analyze_insight` / `lighthouse_audit` built-in (no extra setup).

   **Fallback Playwright** (only if chrome-devtools-mcp unavailable):
   ```
   ToolSearch(query="select:mcp__playwright__browser_navigate,mcp__playwright__browser_click,mcp__playwright__browser_snapshot,mcp__playwright__browser_fill_form,mcp__playwright__browser_evaluate,mcp__playwright__browser_take_screenshot,mcp__playwright__browser_press_key,mcp__playwright__browser_network_requests,mcp__playwright__browser_console_messages")
   ```

   **Where Yaroslav still inputs (limited cases):**
   - **Telegram 2FA code** (Insight 7) — brain pauses, Yaroslav reads from Telegram bot, types it, brain resumes.
   - **Approval gates** for ticket writes / Slack posts (per persona §6).
   - **Physical actions** outside browser (e.g. checking external email, Telegram desktop app interaction beyond Web).

   For everything else — brain drives.

3. **Mark result:**
   - **Pass:** journal log "Phase 3 — TRD-X case <name> PASS at HH:MM, env=stage". Move on.
   - **Fail:** evidence collected (screenshots, network, console snippet, relevant DB rows). Localise: which step, what was actual vs expected, why it diverges from AC. **Queue bug to `qa-output/bugs_queue.md`** — DO NOT stop testing to file immediately. Continue to next AC.

### Continuous testing flow (HARD RULE — added 2026-05-13)

**Не останавливай Phase 3 при первом Fail.** Session идёт от начала до конца. Bug filing batched в Phase 4 после **всех** AC пройдены.

При каждом Fail:
1. Capture evidence (screenshot with URL bar, console, network, DB rows)
2. **Append bug template** в `qa-output/bugs_queue.md`:
   ```markdown
   ## Bug #N — <one-line title>

   - **AC affected:** AC #X
   - **Severity (proposed):** <Critical | Major | Normal | Minor>
   - **1st cohort candidate?:** <yes | no | needs-yaroslav-call>
   - **Parent (proposed):** TRD-XXXX (current ticket OR другой epic if bug routing by nature)
   - **Steps:** ...
   - **Expected:** <verbatim AC>
   - **Actual:** ...
   - **Evidence:** [screenshot.png](path)
   ```
3. journal.sh log: «TRD-X AC#N FAIL — queued in bugs_queue»
4. **Continue Phase 3** — следующий AC, не Phase 4

**Why batch:** test session = unified narrative. Прерывание на каждый bug разрывает фокус, теряет context (что собирался ещё проверить), и approval gate ×N багов = N остановок vs ОДНА в конце.

### Bonus findings (calibrated 2026-05-13 TRD-12743)

Test session часто surfaces проблемы **вне scope** оригинальных AC:
- UX issues (required fields без asterisk markers — see TRD-12743 Leverage/Swap profile)
- Performance hiccups during navigation
- Inconsistent toast messages
- Accessibility gaps
- Console errors не критичные но showing

**Rule:** capture эти findings в `qa-output/bugs_queue.md` в отдельную секцию `## Bonus findings (out of AC scope)`:

```markdown
## Bonus findings (out of AC scope)

### Finding #1 — <title>
- **Where observed:** <during AC #N testing>
- **Type:** UX | Accessibility | Performance | Other
- **Severity (proposed):** typically Minor unless critical
- **Suggestion:** file separately OR mention in main bug OR skip
- **Evidence:** <screenshot/link>
```

В Phase 4 surface bonus findings отдельной строкой:

```
💡 Bonus findings (N): out-of-AC issues observed during test
   • <title> — <type, severity>
   • ...
Decision needed:
  - File each as separate bug (different parent if domain-specific)
  - Mention in main bug body as «while testing also noticed: ...»
  - Skip (acknowledge but not blocking)
```

Yaroslav decides per finding. **Не файлить bonus baga without explicit yes** — иначе bug count раздувается на non-AC scope.

4. **Update launch as you go.**
   - Mark each case Pass/Fail in Allure (manual; future: API).

**Hard rules:**
- Never claim "works" without doing the step. ISTQB principle 1.
- Never skip evidence collection on Fail — even if it "looks obvious". Future-you needs it.
- Re-run a Fail at least once before filing — flakiness happens.
- DB writes never. Only `db-query.sh` reads.
- **Screenshots MUST include the address bar (URL visible).** Added 2026-05-11. Per Yaroslav explicit rule — screenshots without URL lose half their evidence value. A future reader (dev, PO, retest) can't verify which env / which entity / which page state.

### Screenshot capture technique — address bar inclusion

Both `mcp__chrome-devtools__take_screenshot` AND `mcp__playwright__browser_take_screenshot` capture **page content only** (no browser chrome / address bar). Two options:

| Option | When | How |
|---|---|---|
| **A. macOS system screenshot** (preferred) | Default for all evidence | `screencapture -o <path>.png` (full screen) OR `screencapture -W <path>.png` (interactive window pick — works in any context) |
| **B. CDP/Playwright page screenshot + URL annotation** | Fast iteration, draft evidence | `take_screenshot(filename=...)` + include URL in the filename or attached caption when uploading to YouTrack |

**For final bug evidence:** always option A. The address bar shows env (staging URL vs release URL), the entity ID in the path, and the surface. All three are critical reproduction context.

**Filename convention:** `trd-<id>-ac<N>-<surface>-<verdict>.png` — env can also be added: `...-staging.png` / `...-release.png` if ambiguous.

**Exit criteria:** every case in the launch has Pass/Fail, every Fail has been handed to Phase 4 (or duped to existing bug). All Fail evidence screenshots have visible address bar.

---

## Phase 4 — Defect handling (BATCH at end of Phase 3)

**Trigger:** Phase 3 завершена — все AC отработаны (Pass/Fail). Все Fails уже queued в `qa-output/bugs_queue.md` per continuous testing rule. Phase 4 НЕ запускается mid-Phase-3.

### Phase 4 workflow (added 2026-05-13)

1. **Surface Test Report + queued bugs together** (см. Phase 6 для report format):
   ```
   📊 Test Report — TRD-XXXXX
   <verdict table>

   🐛 Bugs on review (N): см. qa-output/bugs_queue.md
     • Bug #1: <title> — Severity X, AC #N
     • Bug #2: ...

   ❓ Open questions: <if any AC ambiguity surfaced>
   💡 Suggestions: <bonus findings, UX issues, etc.>
   ```

2. **Yaroslav reviews queue** — для каждого bug:
   - approve as drafted → submit
   - refine (severity/title/parent route) → re-show
   - reject (was misunderstanding) → discard
   - file as bonus separate ticket

3. **For each approved bug — file via MCP with approval gate:**
   - `youtrack:create_bug(approved=False)` → preview
   - User confirms «да» → `create_bug(approved=True)`
   - Upload screenshot via curl POST `/attachments`
   - journal.sh bug TRD-NEW «...»

4. **Status transitions** (HARD RULE — added 2026-05-13):

   **При создании каждого bug:**

   | Ticket | New state |
   |---|---|
   | **New bug** (freshly created) | `To Do` |
   | **Parent task** (the User Story being tested, e.g. TRD-12743) | `Reopen` |
   | **[QA] subtask** (e.g. TRD-13677 from Phase 1.5) | `Reopen` |

   Все три transition через `youtrack:update_ticket_status` с approval gate (preview → approved=true).

   **Why all three:** new bug в To Do = ready for dev pickup. Parent в Reopen = signal что не deployable. QA subtask в Reopen = signal что retest required after fix.

**Source of truth:** [`skills/bug-report/SKILL.md`](../skills/bug-report/SKILL.md). It already covers:
- Step 1 — Gather facts
- Step 2 — Find parent User Story (delegate to `bug-writer` subagent)
- Step 3 — Human approval gate
- Step 3.5 — Tag classification (`1st cohort` per `insights.md` Insight 13)
- Step 4 — Submission (Yaroslav posts manually in YouTrack)
- Step 5 — Journal log (NON-NEGOTIABLE)

**Workflow-specific additions:**

1. **Link the bug to the launch case in Allure** — once TRD-XXXXX exists, attach to the failing case.
2. **Annotate the Phase 1 artefact** — add a "Defects found" section in `test_prep/<TRD-ID>/<TRD-ID>.md` listing each new TRD with link.
3. **Decide blocking-ness** — if the bug blocks the parent ticket from being verifiable, surface to Yaroslav with `blocker` candidate flag (per Escalation rules — Yaroslav decides).
4. **Bug routing by nature, not by ticket where found** — added 2026-05-11 (TRD-12728 calibration).

   A defect's `parent_trd` should be the ticket that **conceptually owns the defect's domain**, not always the ticket you happened to find it in. Example from TRD-12728:

   | Defect | Parent should be | Why |
   |---|---|---|
   | Column header "Balance USD" not renamed (Data builder) | TRD-12728 (the rename feature) | Direct AC violation of the test ticket |
   | Raw i18n keys `AFFILIATES.LAST_DEPOSIT_DATE_HEADER` visible | TRD-13331 (Localization epic) | i18n is a different epic; this defect is in localization scope |

   **Rule:** before filing, ask «What story / epic owns this defect's *domain*?» Search YouTrack for the matching epic. If the natural parent isn't the test ticket — file under the natural parent, then add a comment on the test ticket referencing the new bug.

**Exit criteria:** every Phase 3 Fail has a draft → approval → posted bug → journal entry → Allure link.

### Phase 4 add-on — Communication chain (after bug filed)

Added 2026-05-11 (TRD-12728 calibration). After EACH bug submitted, brain MUST prepare **two artefacts** for Yaroslav (ready to copy-paste):

| # | Artefact | Where | Language | Author |
|---|---|---|---|---|
| 1 | **Evidence comment** with AC verdict table (✅ passed / ❌ failed → bug-link). **Format = `knowledge_base/evidence_format.md`** (per-AC rows + screenshot per group + address bar in URL) | YouTrack **QA subtask** (e.g. TRD-13684, the [QA] subtask from Phase 1.5) | EN, dry engineering | Brain posts via MCP `add_comment` (Tier 3 — preview → approved); screenshots uploaded via `curl POST /api/issues/{id}/attachments` (MCP doesn't handle files) |
| 2 | **Status transition** for QA subtask | YouTrack QA subtask | — | If any ❌ → `Reopen`. If all ✅ → `Verified`. Via `update_ticket_status` (Tier 3 gate). |
| 3 | **Summary comment** referencing the new bug(s) | YouTrack **parent test ticket** (e.g. TRD-12728) | EN, short | Brain posts via MCP `add_comment` |
| 4 | **Slack draft** for `#trading-dev-team-internal` (channel `C0813EQUEEA`) | Slack | RU, short (3-5 lines) | **Brain DRAFTS only — Yaroslav posts manually** (Slack write scope intentionally not granted, per 2026-05-11) |

**Slack draft template (RU, short):**
```
Тестировал TRD-XXXXX
Посмотрел все AC.
Pass: <N> · Fail: <M> → TRD-YYYYY (1st cohort if applicable)
@trading-frontend / @trading-backend (по ситуации — channel group tag)
```

**Hard rules:**
- Brain NEVER posts to Slack directly. Always: draft → show Yaroslav → he posts.
- Brain DOES post to YouTrack (with Tier 3 approval gate).
- All four artefacts (#1-4) prepared before brain considers Phase 4 "exit" satisfied.
- If any artefact's content is uncertain (e.g., severity, env), surface to Yaroslav before draft.

**Exit criteria (updated):** every Phase 3 Fail has a draft → approval → posted bug → journal entry → Allure link → **4-artefact communication chain prepared**.

---

## Phase 5 — Validation (post-fix re-test)

**Trigger:** dev marks one of the bugs as fixed (status change in YouTrack), or Yaroslav says "перепроверь TRD-X".

**Steps:**

1. **Pull fix details.**
   - `youtrack.get_ticket(<bug_id>)` — what was changed.
   - `youtrack.get_comments(<bug_id>)` — context from dev (what file, what migration, anything for QA to know).
   - If a code repo is accessible: read the diff (when this capability lands).

2. **Re-run THE specific failing scenario first.**
   - Same env, same role, same data setup as the original Fail.
   - Mark Pass/Fail in the launch.
   - Log: `journal.sh log "Re-test TRD-bugID PASS — original Fail no longer reproduces"`.

3. **Adjacent regression sample.**
   - Pick 2-3 scenarios near the fix area (defect clustering — ISTQB principle 4).
   - Run them. Log results.

4. **Re-evaluate the parent ticket.**
   - Are all original AC still passing?
   - Are there NEW Fails introduced by the fix?

5. **Decide on bug status:**
   - Fix confirmed → bug ready to close (Yaroslav posts status change).
   - Fix incomplete / regression → reopen + new evidence + journal entry.

**Hard rules:**
- Never trust dev "fixed" without re-running. ISTQB principle 7 (absence-of-errors fallacy).
- Always test the EXACT failing scenario first — don't substitute "similar".
- If the fix introduces new Fails — DO NOT silently file a new bug. Pause, talk to Yaroslav, decide reopen-vs-new.

**Exit criteria:** all Phase 4 bugs confirmed fixed (or re-opened with evidence). Parent ticket fully unblocked.

### Phase 5 add-on — Post-fix hardening (regression-test creation)

For every bug that was non-trivial (root cause was a real defect, not a misconfiguration), create a **regression test case in Allure** and link it to the parent User Story. This is how the brain remembers the lesson.

**Steps:**
1. Identify the smallest reproducer of the original failure (the sequence that demonstrates the defect).
2. `allure.preview_test_case_payload` — draft a regression case named like `[Regression] TRD-<bug-id>: <one-line reproducer>`.
3. Link it to the **parent User Story** (so future tests of that area pick it up), and tag with the bug TRD-ID.
4. Yaroslav approves → `allure.create_test_case(..., approved: true)`.
5. Journal log: `journal.sh log "Regression case for TRD-<bug-id> created in Allure, linked to parent <story-id>"`.

**Hard rule:** if a bug was filed without a regression case being created, the bug is "closed but not hardened". Mark this gap explicitly in the journal so it's visible at retrospective.

---

## Phase 6 — Close

**Trigger:** Phase 5 cleared all blockers AND all original AC pass.

**Steps:**

1. **Final coverage check.**
   - Re-read AC. Mentally walk it. Any unverified item? If yes → back to Phase 3 for that item.
2. **Update Allure launch.**
   - All cases marked. Final summary recorded.
3. **KB enrichment** (if applicable):
   - New gotcha discovered → add to `knowledge_base/insights.md`.
   - Schema/fact uncovered → add to `db_naming_map.md` or relevant KB file.
   - New Allure cases worth keeping in the index → next `update-allure-index.py` run will pick them up.
4. **Status transitions (all AC pass path)** — added 2026-05-11 per Yaroslav rule.

   When **ALL AC pass AND no open bugs blocking the parent**, the transition is **fixed**:

   | Ticket | New state | Pre-requisite |
   |---|---|---|
   | **Parent test ticket** (e.g. TRD-12728) | `Pre-ready to Deploy` | All AC pass, all linked bugs Fixed/Closed |
   | **[QA] subtask** (e.g. TRD-13684) | `Done` | Evidence comment + screenshots posted FIRST per `evidence_format.md` |

   **Order matters:**
   1. Post evidence comment on [QA] subtask (per `evidence_format.md` — per-AC table + screenshots with address bar)
   2. Transition [QA] subtask → `Done` via `youtrack:update_ticket_status` (Tier 3 gate: preview → approved=true)
   3. Transition parent → `Pre-ready to Deploy` via `youtrack:update_ticket_status` (Tier 3 gate)

   **If [QA] subtask doesn't exist yet** (Phase 1.5 was skipped or missed):
   - Brain MUST create it now via `youtrack:create_qa_subtask` (Tier 3 gate)
   - Then post evidence comment on the new subtask
   - Then transition subtask → `Done`
   - Then parent → `Pre-ready to Deploy`

   **Refuse to transition parent to `Pre-ready to Deploy` if [QA] subtask is missing.** Audit trail requires the [QA] subtask record.

5. **Produce Test Report** (added 2026-05-13 calibration).

   Write `qa-output/<TRD-ID>-report.md`:

   ```markdown
   # Test Report — TRD-XXXXX

   **Date:** YYYY-MM-DD HH:MM
   **Env:** <staging | release>
   **User:** <test user>
   **Verdict:** ✅ PASS | ❌ FAIL | 🟡 PARTIAL

   ## Summary
   <1-2 sentence narrative — что протестировали и каков итог>

   ## AC Results
   | AC | Requirement | Verdict | Evidence |
   |----|-------------|---------|----------|
   | #1 | <verbatim> | ✅ PASS / ❌ FAIL → TRD-NNNN | screenshot link / DB query |
   | #2 | ... | ... | ... |

   ## Bugs filed
   - TRD-NNNN: <title> — Severity Major | 1st cohort
   - TRD-MMMM: <title> — Severity Minor (bonus finding)

   ## Status transitions performed
   - [QA] TRD-13677 → Reopen (bugs filed) | Done (all pass)
   - Parent TRD-12743 → still In QA | Pre-ready to Deploy

   ## Evidence
   - qa-output/screenshots/<file1>.png — what it shows
   - qa-output/screenshots/<file2>.png — what it shows

   ## Open questions / follow-ups
   - <if any AC ambiguity surfaced>
   - <if bonus findings need separate tickets>

   ## Time spent
   - Phase 1: ~N min · Phase 3: ~N min · Phase 4: ~N min · Total: ~N min
   ```

   **Surface report в чат — формат RU narrative + structured table.** Не просто dump artefact'а.

6. **Save the journal session.**
   - `scripts/journal.sh save "TRD-X verified end-to-end, N bugs filed (M 1st cohort), <key insight>"`.

7. **Self-scheduled retest (if Reopen, not Verified)** — added 2026-05-11 (TRD-12728 calibration).

   If ticket exits Phase 6 in `Reopen` state (bugs filed, awaiting dev fix):
   - Brain proposes a scheduled task: «Через 3 часа проверю не сменил ли dev статус TRD-X на Ready for QA — если да, начну Phase 5 retest».
   - On approval → `mcp__scheduled-tasks__create_scheduled_task` with `fireAt` = now + 3h (or appropriate delta).
   - The task prompt: `Check status of TRD-X via youtrack:get_ticket. If state == "Ready for QA" → log to journal "TRD-X moved to Ready for QA, retest scheduled" and notify user. If still in dev → reschedule another check in 3h (manual).`
   - This automates the "hot reread" pattern — brain notices fix readiness without Yaroslav manually checking.

**Exit criteria:** ticket Verified in YouTrack, KB updated if needed, journal session saved. If `Reopen` — retest scheduled.

---

## Mental model — Phases 4-5-6 ≡ TDD red/green/refactor

Useful analogy для понимания собственной работы как инженерного craft (не просто «тестировщик руками тыкает»):

```
Developer's TDD                         QA Engineer's lifecycle
─────────────────────                   ────────────────────────
RED — write failing test           ≡    Phase 4 — file the bug
        (lock the broken state)              (lock the broken state in YouTrack)
            ↓                                       ↓
GREEN — write code to pass         ≡    Phase 5 — re-test specific scenario
        (minimum to make test pass)            (confirm fix works)
            ↓                                       ↓
REFACTOR — clean up while green    ≡    Phase 5.5 — regression case in Allure
        (preserve test, improve code)         (lock-in protection from repeat)
```

**Why this matters:**
- Phase 4 (filing bug) is not "complaining to dev" — it's **encoding a failing test against the system** that drives the fix.
- Phase 5 (re-test) is the GREEN gate — without it, the fix is unverified, just like un-run tests prove nothing.
- Phase 5.5 (regression case) is the REFACTOR step — the lasting artefact that prevents repeat. Skipping it = losing the lesson.

The QA's defect lifecycle is not a side process to development — it's a **mirror TDD loop** at the system level. Sourced from Habr article «Claude Code на автопилоте» (Кир Мойша) which discusses split TDD phases as separate sessions.

---

## State machine — at any moment, "where am I?"

The brain should be able to answer this question instantly. The phases map to journal markers:

| Journal evidence | Current phase |
|---|---|
| Mission set, no `test_prep/<TRD-ID>/` artefact yet | Phase 0/1 |
| `test_prep/<TRD-ID>/<TRD-ID>.md` exists, awaiting review | end of Phase 1 |
| Launch ID recorded in `test_prep/<TRD-ID>/` | Phase 2 done, in Phase 3 |
| `journal.sh log` shows scenario PASS/FAIL entries | mid-Phase 3 |
| `journal.sh bug` entries exist | Phase 4 in progress |
| Re-test logs after a bug TRD ID | Phase 5 |
| `journal.sh save` with "verified end-to-end" | Phase 6 done |

If the user asks "где мы по TRD-X?" — orchestrator (or engineer in mid-flow) checks the markers and answers.

---

## Hard rules across all phases

1. **All write operations are approval-gated.** YouTrack creates, Slack posts, Allure case creation, ticket status changes. The QA approves each.
2. **Read-only is the default.** DB reads, YouTrack reads, Allure reads, Slack reads — go ahead. Writes — never without explicit `yes`.
3. **Journal everything significant.** Every PASS/FAIL, every bug, every blocker, every status change.
4. **Never invent state.** If MCP fails, say so. If Allure has no cases, say so. If AC is silent on a scenario, say so.
5. **Mission per chat.** One ticket per active session preferred. Multi-ticket → split into sequential sessions, save between.

---

## How this wires into the brain

- **CLAUDE.md** routes user intent to the right entry phase (this file is read on session start).
- **`qa_persona.md`** — engineer-mode judgement layer (active during Phases 1-6).
- **`orchestrator_persona.md`** — day-manager mode (active when no specific ticket is in flow, or for /pulse/morning).
- **`test_prep/MECHANISM.md`** — Phase 1 detailed mechanics.
- **`skills/bug-report/SKILL.md`** — Phase 4 detailed mechanics.
- **`skills/test-planning/SKILL.md`** — feeds into Phase 1.
- **`scripts/journal.sh`** — state recorder across all phases.

---

## Open questions / TBD

- [ ] When Allure MCP gains launch CRUD — automate Phase 2 step 3 (launch creation).
- [ ] Code-repo access (GitHub read-only clone) — feeds Phase 5 step 1.
- [ ] Slack-watcher (per orchestrator persona) — when it exists, integrate into Phase 5 (dev pings from #releases).
- [ ] API-coverage layer — when API knowledge lands (OpenAPI / Postman), formalise as Phase 3 sub-layer.
- [ ] Auto-handoff between phases — currently manual checkpoints with Yaroslav. Could be partially automated for Pass-only paths.
