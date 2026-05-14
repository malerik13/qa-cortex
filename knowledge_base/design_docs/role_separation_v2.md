# Role Separation v2 — Hybrid Architecture

> **Status:** DRAFT — awaits Yaroslav approval
> **Date:** 2026-05-09
> **Context:** Continuation from `test_prep/handoff_2026-05-07_architecture_redesign.md`
> **Supersedes:** Current 2-mode lazy-loaded persona system (v0.7.x)

---

## TL;DR

Current 2-mode setup (Engineer + Orchestrator) has **fundamental overlap** in actual usage. Setup work is **genuinely different** from both. Recommendation:

- **Setup → dedicated subagent** (different context, tools, model defaults)
- **Engineer + Orchestrator → remain modes** (heavy interaction, shared infra, overlap is real)
- **Mode triggers → verb-anchored** (no more keyword ambiguity)
- **Proactive Orchestrator → scheduled-tasks MCP** (morning brief, pipeline drift checks)

This is **Hybrid Option D'** from chat discussion 2026-05-09.

---

## Problem statement — actual pain points

From real usage over 4+ months (validated against Yaroslav's lived experience):

### Pain 1 — Orchestrator reactive only
Sits silent until user says «доброе утро». Situational awareness is event-driven by user, not by reality. Pipeline drift (ticket stuck >3 days, dev pushed fix overnight, PO posted in Slack) goes unnoticed until user thinks to ask.

### Pain 2 — Mode confusion at trigger boundaries
Current triggers are keyword-based:
- «{TICKET_PREFIX}-XXXXX» alone could be Engineer (test it) OR Orchestrator (status check)
- «расскажи про TRD-X» is Orchestrator (analysis) but reads like Engineer pre-step
- Brain occasionally drifts mid-conversation

### Pain 3 — Setup pollution of QA context
Although `journal/dev/` separation exists, brain working on a TRD that requires brain meta-edits (e.g., "AC #5 is wrong, update business_rules.md") ends up doing BOTH at once. Context bloat, mixed concerns, sometimes wrong file edited.

### Pain 4 — Context size at session start
Engineer mode loads `qa_persona.md` (7K) + sometimes pulls in `orchestrator_persona.md` (7K) "in case". Single-ticket testing doesn't need orchestrator's day-management rules.

---

## Actual usage patterns (Yaroslav's description, 2026-05-09)

| Role | Real usage | Scope | Output |
|---|---|---|---|
| **Orchestrator** | "универсальный рабочий" — Slack analysis, board analysis, regression suites, pattern recognition, "тикет analysis" | **Wide × shallow** | Dashboards, briefings, regression verdicts |
| **Engineer** | Testing tasks, regression, writing bugs, writing comments, "анализ ситуации" on specific ticket | **Narrow × deep** | Bug reports, test plans, status changes, comments |
| **Setup** | Correcting/improving structure files, adding rules, skills, agents | **Brain meta** | CLAUDE.md edits, new skills, persona changes |

**Critical observation:** Engineer and Orchestrator BOTH do regression. BOTH do ticket analysis. The difference is **scope/depth**, not capability. They share tools (youtrack/allure/slack/journal) but use them differently.

Setup is **fundamentally different work** — operates on brain, not product.

---

## Architecture options (4 considered, honest trade-offs)

### Option A — 3 separate Claude Code projects
Setup project (`~/Documents/[company]-brain-setup`), Orchestrator project (`~/Documents/[company]-orchestrator`), Engineer project (`~/Documents/[company]-qa`).

| Pros | Cons |
|---|---|
| Total isolation | Tripled infrastructure (3 CLAUDE.md, 3 settings.json) |
| Different models per role naturally | State duplication (3 journals?) |
| | Complex handoff (Slack mention while testing → switch project?) |
| | High maintenance overhead |

**Verdict:** ❌ Overkill. Coordination cost exceeds isolation benefit.

### Option B — 3 subagents via Task tool
One project, three `subagent_type` definitions. Brain delegates based on trigger.

| Pros | Cons |
|---|---|
| Clean separation | Subagents don't see chat history — context handoff is explicit |
| Parallelism possible (orchestrator monitors while engineer tests) | Coordination overhead for mode transitions |
| Different system prompts per role | Loss of conversational continuity |
| | Engineer ↔ Orchestrator overlap means frequent transitions = high friction |

**Verdict:** ❌ Wrong for Engineer/Orchestrator (overlap too high). Right for Setup (rare cross-talk).

### Option C — Current modes + proactive orchestrator
Keep Engineer + Orchestrator as lazy-loaded modes. Add `scheduled-tasks` for proactive behavior.

| Pros | Cons |
|---|---|
| Minimal change | Doesn't address Pain 3 (Setup pollution) |
| Solves Pain 1 (reactive Orchestrator) | Doesn't address Pain 2 (mode confusion at triggers) |
| Cheap to implement | Doesn't address Pain 4 (context bloat) |

**Verdict:** 🟡 Solves 1/4 pain points. Incomplete.

### Option D' — Hybrid (recommended)
1. Setup → dedicated subagent (Option B for this role only)
2. Engineer + Orchestrator → remain modes (Option C for these)
3. Verb-anchored triggers (resolves Pain 2)
4. Scheduled-tasks for proactive Orchestrator (resolves Pain 1)
5. Stricter lazy-load discipline (resolves Pain 4)

| Pros | Cons |
|---|---|
| Solves Pain 1, 2, 3, 4 | More moving parts than C |
| Setup gets clean isolation where it matters | Verb-anchored triggers require CLAUDE.md rewrite |
| Engineer ↔ Orchestrator stays smooth (modes) | Setup subagent system prompt is new artifact to maintain |
| Proactive Orchestrator delivers visible win | |

**Verdict:** ✅ Recommended.

---

## Detailed design — Option D'

### Component 1 — Setup subagent

**Subagent type:** `setup-agent` (registered as [COMPANY]-specific in plugin)

**Triggers (verb-anchored):**
- «добавь правило», «add rule»
- «улучши skill», «refactor skill», «дополни skill»
- «создай агента», «create subagent»
- «обнови персону», «update persona»
- «дополни KB», «add to KB», «document insight»
- «design doc», «архитектурное решение»

**System prompt source:** New file `knowledge_base/setup_persona.md` (~5K tokens)
Combines:
- Brain master plan reference (architecture, version history)
- Design docs index (what exists, what's WIP)
- KB hygiene rules (Insight 16 — trim discipline)
- Approval gates for Tier 3 edits (CLAUDE.md, personas, hand-curated KB)
- Voice: meta-engineer, not product engineer

**Tools (different from Engineer/Orchestrator):**
- ✅ Read access to ALL `knowledge_base/`, `skills/`, `mcp/`, `CLAUDE.md`
- ✅ Write access to `skills/`, `knowledge_base/design_docs/`, `knowledge_base/insights.md` (with approval)
- ✅ Bash for scripts/ work, git operations
- ❌ NO access to youtrack/allure WRITE tools (Setup doesn't file bugs)
- ❌ NO access to journal/* QA log (uses `journal.sh dev-log` only)

**Journal lane:** `journal/dev/<DATE>.md` only — never QA standup journal.

**Model defaults:** Opus 4.7 for design/architecture, Sonnet 4.7 for implementation.

### Component 2 — Verb-anchored triggers

Current keyword-based system has ambiguity. New system:

| Pattern | Mode | Example |
|---|---|---|
| `<verb> + TRD-XXXXX` where verb ∈ {протестируй, перепроверь, оформи, валидируй} | Engineer | «Протестируй {TICKET_PREFIX}-XXXXX» |
| `<verb>` where verb ∈ {проанализируй, покажи, расскажи про, что в, пульс, утром, дайджест} | Orchestrator | «Покажи что в pipeline» |
| `<verb>` where verb ∈ {добавь правило, улучши skill, создай агента, обнови персону, дополни KB} | Setup (subagent) | «Добавь anti-pattern в qa_persona» |
| Bare `TRD-XXXXX` (no verb) | **Ambiguous → ask** | Brain asks «Тестировать или статус узнать?» |

**Rationale:** Verb signals INTENT, keyword signals TOPIC. Mode should follow intent.

CLAUDE.md change required: rewrite "Persona — 2 modes" section to use verb-anchored triggers with explicit fallback for ambiguous cases.

### Component 3 — Proactive Orchestrator

**Mechanism:** `mcp__scheduled-tasks__create_scheduled_task`

**Scheduled tasks** (cadence anchored to actual release schedule from `TRD-A-41287691`):

[COMPANY] release cycle (~5 weeks per version):
- Tuesday → Feature freeze (last commit for next version)
- Thursday → Internal Demo
- Friday (next week) → Business Demo
- Monday → UAT
- Saturday → Production release

**Timezone awareness (critical):**
- Yaroslav: Vietnam (ICT, UTC+7)
- Team: Poland (CEST/CET, UTC+2 in summer, UTC+1 in winter)
- Δ = 5h summer / 6h winter (Vietnam ahead)
- Yaroslav work hours: ~13:00–21:00 Vietnam = ~08:00–16:00 Poland (overlap with team)
- Daily standup: 14:00 Vietnam = 09:00 Poland

All scheduled tasks fire in **Vietnam local time** (system clock). All briefing artefacts annotate Poland time in parens for cross-reference.

| Vietnam time | Poland time | Task | Output / Purpose |
|---|---|---|---|
| **12:30** Mon-Fri | 07:30 | **Release schedule refresh** — fetch TRD-A-41287691, parse table, update cache | `knowledge_base/release_cadence_cache.md` + `release_cadence.json` |
| **12:45** Mon-Fri | 07:45 | **Morning brief** — pulse check (YouTrack assignee:me, journal/yesterday, Slack #qa overnight), uses fresh release_cadence_cache | `## Morning brief (auto)` block in `journal/<today>.md` |
| **13:50** Mon-Fri | 08:50 | **Pre-standup brief** — focused on "what to say at 14:00 standup": yesterday verdicts, today plan, blockers | `qa-output/standup_<DATE>.md` (RU, ready to read aloud) |
| **16:00, 18:00, 20:00** Mon-Fri | 11:00, 13:00, 15:00 | **Pipeline drift check** — tickets stuck >3 days, overnight dev fixes, status transitions, mentions in #qa | If signal → `journal/_drift_signals.md`, surface next session |
| **Tuesday 18:00** | 13:00 | **Feature freeze reminder** — what's still In Progress / not QA-ready before tomorrow's cutoff | `qa-output/feature_freeze_status.md`; mid-day Poland — still time to push devs |
| **Wednesday 12:45** | 07:45 | **Pre-Internal-Demo readiness** — red/yellow/green per ticket in next version scope | `qa-output/demo_readiness_<version>.md`; full day to react before Thursday demo |
| **Daily 21:00** | 16:00 | **KB freshness lightweight** — check stale recipes, missing flows, Cockpit drift | Flag in next morning brief if stale |
| **Sunday 18:00** Vietnam | 13:00 Poland Sun | **Post-Release retrospective** (after Saturday Production release) — aggregate release-cycle journals, defect clusters, propose 1-3 calibration insights | `qa-output/release_retrospective_<version>.md` |

### Release schedule cache mechanism

`scripts/refresh-release-schedule.sh`:
1. Calls `youtrack:get_ticket("TRD-A-41287691")` (Tier 1 — read-only, no approval)
2. Parses markdown table → extracts: current version, next 3 versions, Internal Demo / Business Demo / UAT / Production dates each, feature freeze deadline
3. Writes `knowledge_base/release_cadence_cache.md` (human-readable, dates annotated with Vietnam/Poland)
4. Writes `knowledge_base/release_cadence.json` (machine-readable, schema below)
5. Logs to `journal/dev/<DATE>.md` if cache changed since last refresh

JSON schema:
```json
{
  "fetched_at": "2026-05-09T12:30:00+07:00",
  "source": "TRD-A-41287691",
  "current_version": "3.0",
  "next_version": "3.1",
  "upcoming": [
    {
      "version": "3.1",
      "feature_freeze": "2026-05-19",
      "internal_demo": "2026-05-21",
      "business_demo": "2026-05-29",
      "uat_start": "2026-06-01",
      "production": "2026-06-06",
      "phase_now": "QA"
    }
  ]
}
```

Why cache + daily refresh (not real-time):
- Schedule changes rarely (1-2 times per quarter)
- 30 min staleness acceptable for QA planning purposes
- One YouTrack API call/day vs 50+ during a session
- Cache file lives in git — version history of schedule changes is automatic

**Hard rules:**
- Scheduled tasks **never write to YouTrack/Slack** (read-only intelligence gathering)
- Scheduled tasks **never modify hand-curated KB** (only propose to qa-output/)
- User can cancel any scheduled task at any time
- All scheduled tasks have explicit notification: brain mentions them at next user session start

**Opt-in:** Each scheduled task created only after Yaroslav explicit approval (during this design implementation).

### Component 4 — Stricter lazy-load discipline

Current CLAUDE.md table specifies "when to read what." Some conditional reads are over-eager (e.g., orchestrator_persona pulled in for engineer tasks).

**Changes:**
- Engineer mode: load `qa_persona.md` + conditional KB only. NEVER orchestrator_persona unless explicitly switching mode.
- Orchestrator mode: load `orchestrator_persona.md` + conditional KB only. NEVER qa_persona unless explicitly switching.
- Setup subagent: loads `setup_persona.md` + design_docs only.

Brain self-check: at any point in session, if Engineer mode is active AND `orchestrator_persona.md` content appears in context → that's a regression, restart fresh chat.

---

## Implementation phases

### Phase 1 — Foundation (week 1)
1. Write `knowledge_base/setup_persona.md` (~5K tokens) — draft → Yaroslav review → finalize
2. Register `setup-agent` subagent type in plugin
3. Update CLAUDE.md "Persona — 2 modes" section → "Persona — 2 modes + Setup subagent"
4. Document verb-anchored trigger table

### Phase 2 — Proactive Orchestrator (week 1-2)
5. Implement 4 scheduled tasks via `mcp__scheduled-tasks__create_scheduled_task`
6. Build morning brief script (read-only intelligence aggregation)
7. Test for one week — does morning brief surface anything Yaroslav didn't already know?
8. Iterate on signal-to-noise ratio

### Phase 3 — Trigger migration (week 2)
9. Rewrite CLAUDE.md persona section with verb-anchored triggers
10. Add ambiguity fallback («бare TRD-XXXXX → ask»)
11. Test with 5-10 real triggers — does brain correctly route?

### Phase 4 — Validation (week 3)
12. Real ticket walkthrough: Engineer mode test, Orchestrator pulse mid-day, Setup task for KB edit
13. Did roles stay clean? Did mode transitions feel right?
14. Measure: did Pain 1-4 actually go down?

### Phase 5 — Lock in (week 3-4)
15. Tag v0.8.0
16. Journal entry — what calibration insights surfaced
17. Update `qa_brain_master_plan.md` with new architecture

---

## Success metrics

After Phase 4 (3 weeks post-implementation):

| Metric | Baseline (current) | Target |
|---|---|---|
| **Mode confusion incidents** (user has to correct brain on which mode) | ~2-3/week (observed) | 0/week |
| **Proactive notifications useful** (user finds value in scheduled output) | 0 (no proactive) | ≥3/week |
| **Setup work pollution of QA journal** | ~1/week observed | 0/week |
| **Context bloat at Engineer session start** (tokens loaded) | ~14K average | <8K average |
| **Yaroslav explicit «работает!» moment** | — | At least one in Phase 4 |

---

## Rollback plan

If after Phase 4 the new architecture doesn't deliver:

1. **Revert Setup subagent** — meta-work goes back to "build chat" pattern in main brain
2. **Keep proactive Orchestrator** if metric 2 hit ≥3/week (independent value)
3. **Keep verb-anchored triggers** if metric 1 dropped (independent value)
4. **Partial adoption is fine** — not all-or-nothing

Rollback artifacts preserved in `knowledge_base/design_docs/rollback_v2_to_v0.7.md` if it happens.

---

## Open questions — RESOLVED 2026-05-09

- [x] **Setup subagent git access?** → **Defer to main brain.** Setup drafts changes, main brain commits/pushes after Yaroslav approval. Preserves single-source-of-truth for git operations.
- [x] **Proactive Orchestrator Slack DM on critical?** → **NO — journal-only.** All proactive output goes to `journal/*.md` or `qa-output/*.md`. Brain surfaces at next session start. Avoids Slack spam, keeps Yaroslav as sole gate for outbound comms.
- [x] **Sprint cadence?** → **Tied to release schedule** (TRD-A-41287691). NOT Sun-Sun weekly. Inflection points: Tue (feature freeze), Thu (Internal Demo), Fri (Business Demo), Mon (UAT), Sat (Production). ~5-week cycle per version.
- [x] **Verb list per mode?** → **Adopt initial draft, iterate based on real usage.** First 2 weeks of operation = calibration window. Mismatches logged to `journal/dev/` for Phase 4 review.

---

## Decision log

| Date | Decision | Rationale |
|---|---|---|
| 2026-05-07 | Original 3-agent split proposed in handoff | Initial vision based on conceptual clarity |
| 2026-05-09 | Refined to Hybrid Option D' | After analyzing actual usage patterns — Engineer/Orchestrator overlap is real, Setup is genuinely different |

---

## Next steps after approval

1. Yaroslav reviews this doc, marks open questions
2. If approved → kickoff Phase 1 in next session
3. Schedule check-in after Phase 2 (proactive Orchestrator live) — 1 week from kickoff
