# Rules Index — atomic rule lookup

> **Purpose:** Find the right rule fast WITHOUT loading the full source file. One line per rule + path to detail.
>
> **Load when:** «какое правило про X», «is there a rule for Y», «найди правило про Z».
>
> **Use pattern:** read this file (~5K tokens, light), find target row, then `Read <file>` only if more detail needed. Often the one-liner is enough.

---

## Behavioural rules (always apply)

| Rule | Detail in |
|---|---|
| Two-step approval gate (`approved: bool = False` default for MCP writes) | `trust_tiers.md` §Tier 3 |
| PARALLEL tool execution — independent calls in ONE message | `parallel_execution.md` |
| Every substantive reply ends with recommendation block + AskUserQuestion | `recommendation_format.md` |
| Language matrix: chat RU / artefacts EN (YouTrack, Allure, qa-output) | `CLAUDE.md` §Language |
| Brain NEVER posts to Slack directly — drafts for Yaroslav | `slack_channels.md` §Hard rules |
| Brain writes to journal/dev/ only via `journal.sh dev-log` (never direct edit) | `qa_persona.md` Daily Rule 4 |
| Brain reads ALL of `db_schema__*.md` — forbidden, grep/offset only | `CLAUDE.md` §Top 7 don'ts |
| Tier 3 changes: preview → ask → `approved=true` (never first-call approved) | `trust_tiers.md` |
| Self-check before send: if N independent tools → emit N tool_use blocks in ONE message | `parallel_execution.md` §Self-check |

---

## Default conventions

| Rule | Detail in |
|---|---|
| **Default test envs = BOTH `stage` AND `[staging-alt]`** — initial session covers оба, diff results | `business_rules.md` §Default test environment |
| **[staging-alt] = clone of stage** для business demos (same code/data, demo-purpose) | `business_rules.md` §Default test environment |
| **2FA DISABLED on stage + [staging-alt]** — не запрашивай код, логинься напрямую. 2FA active on release/release-ca | `business_rules.md` §Default test environment §2FA on staging |
| `[test-user]` works на ВСЕХ 4 envs — same credentials, no switching | `business_rules.md` §Default test user |
| Default test user = `[test-user]` (Super Admin, Telegram 2FA) | `business_rules.md` §Default test user |
| Bugs always have `To Release Notes: No` (only User Stories go to client notes) | `youtrack_bug_fields.md` §32 |
| Default model: Sonnet 4.5 standard. Escalate to Opus 4.7 xhigh for judgement | `orchestrator_persona.md` §13.2 |

---

## Phase 1 / Intake rules

| Rule | Detail in |
|---|---|
| First action on TRD-trigger: load `qa_persona.md` before any tool call | `CLAUDE.md` §Persona |
| Pre-load context in PARALLEL (4 MCP calls in one message) | `qa_workflow.md` Phase 0 |
| Build Cockpit summary § 0 Bridge format (Object / Goal / Approach / Risk / Status) | `start-ticket-test/SKILL.md` |
| Phase 1.5 idempotency check — surface `find_qa_subtasks` result in bracket format | `qa_workflow.md` Phase 1.5 |
| Phase 1.5 assignee check — surface reassignment as decision point | `qa_workflow.md` Phase 1.5 §2.5 |

---

## Phase 3 / Execution rules

| Rule | Detail in |
|---|---|
| Brain drives browser via chrome-devtools-mcp (PRIMARY, direct CDP) — never ask user to open URL; Playwright = fallback | `qa_workflow.md` Phase 3 |
| Start CDP Chrome via `scripts/launch-chrome-cdp.sh` (port 9222, persistent profile `~/.chrome-cdp-profile`) | `capabilities.md` §Browser PRIMARY |
| 2FA Telegram code — pause, ask Yaroslav to type manually (Insight 7) | `insights.md` |
| Screenshots MUST show address bar (URL visible) | `qa_workflow.md` Phase 3 §Hard rules |
| ag-grid columns virtualize — scroll loop + dispatchEvent technique | `ui_flows.md` §11 |
| ag-grid empty state: scrollWidth=0 ambiguous, check rowCount + scrollWidth | `ui_flows.md` §11 |
| Filename: `trd-<id>-ac<N>-<surface>-<verdict>.png` | `qa_workflow.md` Phase 3 |

---

## Phase 4 / Defect handling rules

| Rule | Detail in |
|---|---|
| **Continuous testing** — don't stop at first Fail. Queue bug template in `qa-output/bugs_queue.md`, continue Phase 3. Phase 4 batches at end. | `qa_workflow.md` Phase 3 §Continuous testing |
| **Bonus findings** (out-of-AC issues) — capture в bugs_queue в отдельной секции. Yaroslav decides per finding: separate bug / mention в main / skip | `qa_workflow.md` Phase 3 §Bonus findings |
| `db-query.sh --list` — показывает все DBs из .env. Smart-fail на unknown alias предлагает список | `scripts/db-query.sh` |
| **Triple status transition on bug filed:** new bug → `To Do`, parent task → `Reopen`, [QA] subtask → `Reopen` | `qa_workflow.md` Phase 4 §4 |
| Bugs always on review — `approved=True` only after explicit yes | `CLAUDE.md` anti-pattern #3.5 |
| 1st cohort verbatim ask — never silent reasoning, surface 3 criteria | `CLAUDE.md` §Anti-patterns |
| Bug routing by NATURE (i18n → i18n epic, not test ticket) | `qa_workflow.md` Phase 4 #4 |
| One symptom = one bug (Daily Rule 6 — never combine) | `qa_persona.md` Daily Rules |
| 4-artefact communication chain after bug filed: QA subtask evidence + status transition + parent comment + Slack draft | `qa_workflow.md` Phase 4 add-on |
| Evidence comment format: per-AC rows + screenshot per AC group + URL visible | `evidence_format.md` |
| Screenshot upload to YouTrack: `curl POST /api/issues/{id}/attachments` (MCP doesn't handle files) | `evidence_format.md` |

---

## Phase 5 / Validation rules

| Rule | Detail in |
|---|---|
| Re-run EXACT failing scenario first (no substitutes) | `qa_workflow.md` Phase 5 |
| Adjacent regression sample (2-3 scenarios near fix area, ISTQB cluster) | `qa_workflow.md` Phase 5 |
| Cross-env verification gate — stage pass ≠ release pass (Insight 14) | `db_diff__stage_vs_release.md` |

---

## Phase 6 / Close rules

| Rule | Detail in |
|---|---|
| **All AC pass** → parent → `Pre-ready to Deploy` + [QA] subtask → `Done` (evidence comment FIRST) | `qa_workflow.md` Phase 6 §4 |
| **Missing [QA] subtask blocks close** — must create it via `create_qa_subtask` before transitioning parent | `qa_workflow.md` Phase 6 §4 |
| Self-scheduled retest via `mcp__scheduled-tasks` if Reopen state | `qa_workflow.md` Phase 6 §6 |
| KB enrichment: new gotcha → propose to `qa-output/insights_proposal.md` (NOT direct to insights.md) | `setup_persona.md` §10 #1 |
| Save journal session with `journal.sh save` after close | `qa_workflow.md` Phase 6 |

---

## Communication rules

| Rule | Detail in |
|---|---|
| YouTrack comments (bug body, task, story, comments to dev) → EN | `CLAUDE.md` §Language |
| Allure test cases → EN | `CLAUDE.md` §Language |
| Slack any channel → RU | `CLAUDE.md` §Language |
| Slack channel `#trading-dev-team-internal` = ID `C0813EQUEEA` | `slack_channels.md` |
| `@trading-frontend` / `@trading-backend` = channel group handles, no API resolution | `slack_channels.md` |
| Brain drafts Slack messages, Yaroslav posts manually | `slack_channels.md` §Hard rules |
| 4-artefact chain after bug: see Phase 4 entry above | `qa_workflow.md` Phase 4 add-on |

---

## UI / browser rules

| Rule | Detail in |
|---|---|
| Don't invent UI navigation paths — verify or honest «не знаю» | `CLAUDE.md` §Anti-patterns |
| Verification order: ui_flows.md → Allure case scenarios → Playwright live | `CLAUDE.md` §Anti-patterns |
| Login default = [test-user] (Super Admin) | `business_rules.md` + `ui_flows.md` §10 |
| ag-grid scroll-loop technique | `ui_flows.md` §11 |

---

## Setup mode rules

| Rule | Detail in |
|---|---|
| Setup triggers: «добавь правило», «улучши skill», «создай агента», meta-build verbs | `setup_persona.md` §3 |
| Setup owns git commit/push lifecycle | `setup_persona.md` §5 |
| Setup never auto-adds to insights.md (Yaroslav-curated only) | `setup_persona.md` §10 #1 |
| Setup uses `journal.sh dev-log`, never direct journal edits | `setup_persona.md` §10 #2 |
| Setup never blends with product testing in one session | `setup_persona.md` §10 #3 |
| New architecture changes require design doc BEFORE implementation | `setup_persona.md` §10 #4 |
| CLAUDE.md changes always require diff preview + Yaroslav approval | `setup_persona.md` §10 #5 |

---

## Hard «never» list (top of mind)

| Don't | Why |
|---|---|
| Invent AC / business_rules / UI paths | Trust is the asset — Insight 17 |
| Write to YouTrack/Slack/Allure without 2-step approval | Approval gate erosion = trust loss |
| Use curl/REST for writes when MCP-tool exists | Bypass approval + idempotency |
| Set 2FA on `aaa` (Super Admin) | Instant lockout — Insight 7 |
| Commit `.env`, `qa_credentials.md`, `*_token*`, `*.ovpn` | Secrets leak (also blocked by hook) |
| Read `db_schema__*.md` fully | 40K tokens each — use grep/offset/db-query.sh |
| Pollute QA journal with meta-build noise | Use `dev-log` instead |

---

## Insights (accumulated lessons)

See `insights.md` for full list. Key recent:

| Insight | Topic | Calibrated |
|---|---|---|
| Insight 7 | Don't put 2FA on `aaa` (instant lockout) | early |
| Insight 13 | YouTrack `1st cohort` tag definition | early |
| Insight 14 | Stage ≠ Release schemas (71-table drift) | early |
| Insight 16 | CLAUDE.md hygiene — «удали строку, что-то сломается?» | 2026-04 |
| Insight 17 | UI navigation hallucination — verify, don't invent | 2026-04 |
| Insight 18 | Audience-first artefact design | 2026-04 |
| Insight 19 | AC «non-applicable surface» = PASS, not ⚠ N/A | 2026-05-11 (TRD-12728) |
| Insight 20 | Default test env = staging | 2026-05-11 |

---

## How to use this index

1. User asks «есть правило про X»? → Read this file, find row, give one-liner answer + path
2. If user wants more detail → `Read <path>` only the specific section
3. If you're about to do something and unsure → check «Behavioural rules» first
4. If you're starting a new phase → check phase section above
5. Update this index when adding new rules to KB (Setup work)

**Index is the source of truth for «what rules exist».** If a rule exists in KB but not here → fix this file.
