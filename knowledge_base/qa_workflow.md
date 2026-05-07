> ⚠ **PORTED FROM scalefinal-qa-assistant — Phase 2 audit pending.**
> Some examples may still reference your-product-specific concepts that need generalization.
> Mechanical scrub applied; content audit on backlog.
> See `knowledge_base/design_docs/qa_cortex_v1.md` Phase 2 for refactor scope.

---

# QA Workflow — End-to-end ticket lifecycle

> Caнonical playbook for "QA receives a TRD → QA closes it Verified". Every phase has clear inputs, outputs, tools, and exit criteria.
> Phase 1 (Preparation) is implemented in `test_prep/MECHANISM.md` and stays the source of truth for that phase.

---

## How to start (the one rule)

**Way #1 — paste a YouTrack link or <TICKET>-ID + intent verb:**

| User says | Intent | First phase |
|---|---|---|
| "тестируй <TICKET>-12345" / "хочу тестировать <TICKET>-12345" | full lifecycle | Phase 1 |
| "подготовь к тестированию <TICKET>-12345" / "разверни контекст" | prep only | Phase 1, stop after |
| "статус по <TICKET>-12345" | pulse only | (orchestrator, no workflow) |
| "перепроверь <TICKET>-12345 после фикса" | re-test | Phase 5 |
| "оформи баг про X" | bug only | Phase 4 (existing bug-report skill) |

**Way #2 — orchestrator picks the next ticket:**
After `/plan-day` proposes order, QA confirms one — workflow starts at Phase 1 for that ticket.

The brain ALWAYS confirms intent verb before executing. "<TICKET>-X" alone (no verb) → ask: "тестировать, готовить, или просто статус?"

---

## The six phases

```
   [INTAKE]
      ↓
 ┌─ Phase 1: Preparation       (test_prep/MECHANISM.md)
 │     ↓                        artefact: test_prep/<<TICKET>-ID>/<<TICKET>-ID>.md
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
 │     ↓                        artefact: <TICKET>-XXXXX bug + journal log
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
2. Set journal mission via `scripts/journal.sh mission "<one-sentence>"`. Default: "Test <TICKET>-XXXXX end-to-end".
3. State the plan: "Starting Phase 1 (Preparation). Will stop for your review before Phase 2."

**Exit criteria:** mission set, user knows what's about to happen.

---

## Phase 1 — Preparation

**Source of truth:** [`test_prep/MECHANISM.md`](../test_prep/MECHANISM.md). Don't duplicate the mechanism here; it lives there and is battle-tested. Summary of inputs/outputs only:

**Inputs:** <TICKET>-ID, parallel pulls from YouTrack + Allure + KB.

**⚠ Allure tool usage rule:** when calling `find_test_cases_by_issue`, **always pass `include_scenario: true`** (capped at 20 cases by default). Without the flag, brain only sees `[id, name, status]` — no scenario steps — and Coverage Matrix (§6) becomes guessing. The flag triggers live API call per case to fetch full steps + sub-steps + expected results. Slower but correct. If a TRD has >20 linked cases (rare), pass `max_cases: 50` or fetch specific ones via `get_test_case(id)`.

**Output:** `test_prep/<<TICKET>-ID>/<<TICKET>-ID>.md` with the 11 sections:
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

---

## Phase 1.5 — Create QA subtask in YouTrack (public test plan)

**Why this exists:** Phase 1 produces a *local* artefact (`test_prep/<TRD>/<TRD>.md`) that's rich and personal. Phase 1.5 produces a *public* artefact (a [QA] subtask in YouTrack) that's terse, engineering, and visible to the dev/PO team. Same content, two registers.

**Mandatory for every `/start <TICKET>-X test` flow** — apply once per parent TRD, idempotent.

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
   | [QA] exists but NOT same parent (e.g. linked to sibling CR ticket <TICKET>-13653) | Treat as `CREATE_NEW` for THIS parent (different ticket, different scope). |

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
   - Brain returns the new <TICKET>-ID + URL.

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
| Subtask link | OUTWARD ← parent | via `subtask of <TICKET>-XXXXX` command |

### Hard rules

- **English only** in title and body. Per `qa_persona.md §7` language matrix.
- **Engineering register** — no opinions, no hedging, no «I think». Facts + plan.
- **Brevity** — 15-30 lines body. If exceeds, split scope (multiple QA subtasks for sub-stories).
- **Idempotent** — never create duplicate. Existing one wins.
- **Approval-gated** — even though writes are now possible via MCP, two-step approval applies.

### Exit criteria

- QA subtask exists in YouTrack with proper title and fields.
- Linked to parent as Subtask.
- New <TICKET>-ID journaled.
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
   - Each created case immediately journal-logged: `journal.sh log "Created Allure case <id> for <TICKET>-X"`.
3. **Plan the launch (don't create yet — Allure MCP doesn't expose write for launches in this plugin version):**
   - Compose launch metadata: name (e.g. `<TICKET>-12345 — sprint-2.10 verify`), expected test cases, environment (stage / release / etc).
   - Output the launch plan to Yaroslav for him to create in Allure UI manually.
   - Future enhancement: when Allure MCP supports launch creation, automate this step.
4. **Once launch exists in <test-mgmt>:** Yaroslav provides launch URL/ID → brain stores in `test_prep/<<TICKET>-ID>/<<TICKET>-ID>.md` Phase 2 section.

**Exit criteria:**
- Every test plan scenario has a corresponding Allure case (created or pre-existing).
- Launch exists in Allure with all cases assigned.
- Launch URL/ID recorded in `test_prep/<<TICKET>-ID>/`.
- **Yaroslav approves** to start Phase 3.

**Hard rule:** No `create_test_case` without `approved: true` and explicit `yes` from Yaroslav.

---

## Phase 3 — Execution

**Inputs:** launch with cases ready, environments accessible, test data prepped (per Phase 1 §9).

**Steps per scenario:**

1. **Set up state.**
   - Right environment (per AC). Login as the right role.
   - Fixture data per `knowledge_base/glossary.md` and `project_test_fixtures.md`.
   - DB pre-state via `scripts/db-query.sh --db <name>` if test depends on initial data.

2. **Run the scenario — BRAIN drives, not the user.**

   ⚠ **Hard rule:** brain выполняет browser-действия САМ через Playwright MCP. Never ask Yaroslav to "open browser and navigate to X". Per `qa_persona.md Rule 10` (Tool-first reflex) and CLAUDE.md `🤖 Capability declaration`.

   **Pre-flight (one-time per chat):**
   ```
   ToolSearch(query="select:mcp__playwright__browser_navigate,mcp__playwright__browser_click,mcp__playwright__browser_snapshot,mcp__playwright__browser_fill_form,mcp__playwright__browser_evaluate,mcp__playwright__browser_take_screenshot,mcp__playwright__browser_press_key,mcp__playwright__browser_network_requests,mcp__playwright__browser_console_messages")
   ```
   Loads deferred browser_* tools. Brain has them now.

   **Execution layers:**
   - **UI** through `mcp__playwright__browser_*` — navigate, click, fill, snapshot. Side-channel: `browser_network_requests`, `browser_console_messages`.
   - **API** through Playwright `browser_evaluate` for in-page fetch, OR direct curl/httpie via Bash for headless API tests.
   - **DB** through `scripts/db-query.sh --db stage|release "..."` — verify state matches UI claim.
   - **Automated scripts** if `scripts/playwright/*.py` exists for the flow — call via Bash, get JSON result.

   **Where Yaroslav still inputs (limited cases):**
   - **Telegram 2FA code** (Insight 7) — brain pauses, Yaroslav reads from Telegram bot, types it, brain resumes.
   - **Approval gates** for ticket writes / Slack posts (per persona §6).
   - **Physical actions** outside browser (e.g. checking external email, Telegram desktop app interaction beyond Web).

   For everything else — brain drives.

3. **Mark result:**
   - **Pass:** journal log "Phase 3 — <TICKET>-X case <name> PASS at HH:MM, env=stage". Move on.
   - **Fail:** evidence collected (screenshots, network, console snippet, relevant DB rows). Localise: which step, what was actual vs expected, why it diverges from AC. Hand off to Phase 4.

4. **Update launch as you go.**
   - Mark each case Pass/Fail in Allure (manual; future: API).

**Hard rules:**
- Never claim "works" without doing the step. ISTQB principle 1.
- Never skip evidence collection on Fail — even if it "looks obvious". Future-you needs it.
- Re-run a Fail at least once before filing — flakiness happens.
- DB writes never. Only `db-query.sh` reads.

**Exit criteria:** every case in the launch has Pass/Fail, every Fail has been handed to Phase 4 (or duped to existing bug).

---

## Phase 4 — Defect handling

**Trigger:** any Fail from Phase 3, or any defect noticed outside the formal scenarios.

**Source of truth:** [`skills/bug-report/SKILL.md`](../skills/bug-report/SKILL.md). It already covers:
- Step 1 — Gather facts
- Step 2 — Find parent User Story (delegate to `bug-writer` subagent)
- Step 3 — Human approval gate
- Step 3.5 — Tag classification (`1st cohort` per `insights.md` Insight 13)
- Step 4 — Submission (Yaroslav posts manually in YouTrack)
- Step 5 — Journal log (NON-NEGOTIABLE)

**Workflow-specific additions:**

1. **Link the bug to the launch case in Allure** — once <TICKET>-XXXXX exists, attach to the failing case.
2. **Annotate the Phase 1 artefact** — add a "Defects found" section in `test_prep/<<TICKET>-ID>/<<TICKET>-ID>.md` listing each new TRD with link.
3. **Decide blocking-ness** — if the bug blocks the parent ticket from being verifiable, surface to Yaroslav with `blocker` candidate flag (per Escalation rules — Yaroslav decides).

**Exit criteria:** every Phase 3 Fail has a draft → approval → posted bug → journal entry → Allure link.

---

## Phase 5 — Validation (post-fix re-test)

**Trigger:** dev marks one of the bugs as fixed (status change in YouTrack), or Yaroslav says "перепроверь <TICKET>-X".

**Steps:**

1. **Pull fix details.**
   - `youtrack.get_ticket(<bug_id>)` — what was changed.
   - `youtrack.get_comments(<bug_id>)` — context from dev (what file, what migration, anything for QA to know).
   - If a code repo is accessible: read the diff (when this capability lands).

2. **Re-run THE specific failing scenario first.**
   - Same env, same role, same data setup as the original Fail.
   - Mark Pass/Fail in the launch.
   - Log: `journal.sh log "Re-test <TICKET>-bugID PASS — original Fail no longer reproduces"`.

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
2. `allure.preview_test_case_payload` — draft a regression case named like `[Regression] <TICKET>-<bug-id>: <one-line reproducer>`.
3. Link it to the **parent User Story** (so future tests of that area pick it up), and tag with the bug <TICKET>-ID.
4. Yaroslav approves → `allure.create_test_case(..., approved: true)`.
5. Journal log: `journal.sh log "Regression case for <TICKET>-<bug-id> created in Allure, linked to parent <story-id>"`.

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
4. **Status push** (Yaroslav-gated):
   - Draft the status-change comment for YouTrack (English, clinical, per voice rules).
   - Yaroslav reviews and posts manually.
5. **Save the journal session.**
   - `scripts/journal.sh save "<TICKET>-X verified end-to-end, N bugs filed (M 1st cohort), <key insight>"`.

**Exit criteria:** ticket Verified in YouTrack, KB updated if needed, journal session saved.

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
| Mission set, no `test_prep/<<TICKET>-ID>/` artefact yet | Phase 0/1 |
| `test_prep/<<TICKET>-ID>/<<TICKET>-ID>.md` exists, awaiting review | end of Phase 1 |
| Launch ID recorded in `test_prep/<<TICKET>-ID>/` | Phase 2 done, in Phase 3 |
| `journal.sh log` shows scenario PASS/FAIL entries | mid-Phase 3 |
| `journal.sh bug` entries exist | Phase 4 in progress |
| Re-test logs after a bug TRD ID | Phase 5 |
| `journal.sh save` with "verified end-to-end" | Phase 6 done |

If the user asks "где мы по <TICKET>-X?" — orchestrator (or engineer in mid-flow) checks the markers and answers.

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
