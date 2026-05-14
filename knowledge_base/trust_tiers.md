# Trust Tiers — autonomy by action category

> **Load when:** brain is about to do something where it's unclear «can I just do this, or do I need approval?». Or when reasoning about Tier 1/2/3 classification.
>
> **Lazy-load trigger:** «tier», «approval gate», «can I auto», «нужно ли спрашивать», «без approval».

---

## The 3 tiers

For 70% routine offload. Goal: autonomous on routine, gated on critical, explicit ask if ambiguous.

### Tier 1 — AUTO (no approval needed, routine read/scaffolding)

- All `Read` operations (KB files, qa-output/, flows/, journal/)
- All MCP **read** ops:
  - `youtrack:get_ticket`, `get_comments`, `get_linked_tickets`, `find_qa_subtasks`, `search_tickets`, `search_knowledge_base`, `get_version_features`
  - `allure:search_test_cases`, `find_test_cases_by_issue`, `get_test_case`, `list_recent_test_cases`, `preview_test_case_payload`
  - `slack:slack_get_channel_history`, `slack_get_thread_replies`, `slack_get_users`, `slack_get_user_profile`, `slack_list_channels`
- All `journal.sh` operations (`log`, `mission`, `status`, `standup`, `save`, `bug`, `blocker`, `dev-log`) — brain's own audit trail
- All read-only `Bash` (`git status`, `git log`, `git diff`, `db-query.sh` with read-only role, `python3 scripts/refresh-*.py` idempotent regenerators)
- All `Grep`, `Glob`, `LS`
- `ToolSearch` (deferred MCP loading)
- Playwright **read-only** (`browser_snapshot`, `browser_evaluate` for read queries, `browser_console_messages`, `browser_network_requests`, `browser_take_screenshot`)
- `AskUserQuestion`
- Write to **session artifacts** (`qa-output/*` — intake.md, scenarios.md, etc.) — brain's working memory

**Behaviour:** brain just does it. No surface text needed unless requested.

---

### Tier 2 — IMPLICIT APPROVAL (in-context, no explicit ask but surface action)

- Playwright **UI actions** (`browser_click`, `browser_type`, `browser_fill_form`, `browser_navigate`, `browser_press_key`, `browser_wait_for`) — affect browser state, not data state
- `Edit` on `flows/*.recipe.md` (recipe distillation/refresh, Phase B feature)
- `Edit` on `journal/dev/<DATE>.md` (meta-build chronicle, brain may format)
- Regenerate auto-generated indexes (`flows/_index.json`, `knowledge_base/product_map.json`, `knowledge_base/bugs.json`, `knowledge_base/release_cadence.json`)

**Behaviour:** brain does it, mentions it briefly («saved intake to qa-output/intake.md»).

---

### Tier 3 — EXPLICIT APPROVAL GATE (preview → ask → write)

#### MCP writes
- `youtrack:create_bug`, `create_qa_subtask`, `add_comment`, `update_ticket_status` — preview without `approved` → ask → `approved=true`
- `allure:create_test_case` — `approved=true` gate
- `slack:slack_post_message`, `slack_reply_to_thread`, `slack_add_reaction` — **default = NO comms.** Brain drafts, Yaroslav posts manually. See `slack_channels.md` hard rule.

#### Hand-curated KB edits
- Personas: `qa_persona.md`, `orchestrator_persona.md`, `setup_persona.md`, `qa_workflow.md`
- `insights.md` — Yaroslav-curated lessons, never auto-add. Brain proposes to `qa-output/insights_proposal.md` instead.
- `business_rules.md`, `ui_flows.md`, `glossary.md`, `db_naming_map.md`
- `_module_taxonomy.json` (config)
- `qa_brain_master_plan.md` (strategic doc)
- `design_docs/*.md` (only on explicit «write design doc»)

#### Brain code
- `CLAUDE.md` (master prompt — every change requires Yaroslav-approved diff)
- `.claude/skills/*/SKILL.md`
- `scripts/*` (executable code — never auto-edit)
- `mcp/*/server.py`
- `.mcp.json`, `.gitignore`

#### Yaroslav's authentic record
- `journal/<DATE>.md` (QA standup history — Yaroslav writes via `journal.sh`, brain doesn't direct-edit)

#### Git
- `git commit`, `git tag`, `git push` (versioning is Yaroslav's signal — but Setup mode owns this lifecycle per `setup_persona §5`)

#### Production / irreversible
- Anything in **prod / live customer data** path
- Anything **irreversible** (`rm -rf`, `git push --force`, schema migration, destructive ops)
- Anything tagged **"blocker"** — Yaroslav decides severity

**Behaviour:** brain shows preview, waits for explicit «yes» / «да» in chat. Never `approved=true` on first call.

---

## Rules of thumb

**When in doubt → ask.** False-positive ask is cheap; false-negative (acting unapproved on Tier 3) erodes trust.

**Rooting principle (Article 2 framing):** journal/* (especially `journal/<DATE>.md`) is Yaroslav's **authentic record** — brain may suggest entries via `journal.sh log` commands but content originates with Yaroslav, not auto-generated bloat. `journal.sh log "<verdict>"` is Yaroslav-initiated even when brain prompts for it.

**Approval preview format (Tier 3):**
```
🛠 Tier 3 change proposed:
   Target: <file or MCP call>
   Diff: <one-line semantic description>
   Rationale: <one sentence>
   Approve? [yes / no / refine]
```

After «yes» — apply. Mention in journal if applicable.

---

## Common ambiguity cases

| Situation | Tier | Why |
|---|---|---|
| Writing to `qa-output/intake.md` mid-Phase-1 | 1 | Session artifact, brain's working memory |
| Editing recipe in `flows/*.recipe.md` | 2 | Brain-curated content, not Yaroslav's record |
| Adding entry to `insights.md` | 3 | Hand-curated, propose only via `qa-output/insights_proposal.md` |
| Running `db-query.sh "SELECT ..."` | 1 | Read-only, even on release DB |
| Running `git diff` | 1 | Read-only |
| Running `git commit` | 3 | Setup mode owns this — see `setup_persona §5` |
| Posting Slack message | 3 (defer) | Brain NEVER posts — draft for Yaroslav |
| Posting YouTrack comment | 3 (preview → approved) | Brain DOES post after approval gate |
| Triggering `mcp__scheduled-tasks__create_scheduled_task` | 3 | Affects autonomous future runs |

---

## Source

- v0.7.1 operationalization (initial 3-tier design)
- TRD-12728 calibration 2026-05-11 (clarified Slack draft-only rule)
