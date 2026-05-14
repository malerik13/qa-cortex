# Sub-Task Orchestration Playbook

> **When to read:** orchestrator/engineer decides to decompose a non-trivial task
> into parallel sub-tasks. Sister to `orchestrator_persona.md §13` (model rec).
>
> **Triggers (load this file):**
> - Task touches >3 independent investigations
> - Mixed complexity (some trivial reads + some judgement calls)
> - Multi-round work (R1 findings → R2 deep-dive → R3 synthesize)
> - User uses verbs: «декомпозируй», «распараллель», «разбей на агентов»

Inherits all CLAUDE.md rules — this file specializes the **delegation layer** on top of them.

---

## The 5 rules — non-negotiable

### Rule 1 — Narrow micro-tasks
Each `Task()` call = ONE thing. If subtask description has «and» or numbered list >2 items → split further. A subtask is small enough when its description fits one English sentence and its prompt fits 200 words.

### Rule 2 — Model by complexity (orchestrator self-assigns)

| Subtask shape | Model | Why |
|---|---|---|
| Read file, single grep, list dir, check git status, simple bash | **haiku** | trivial throughput; reading is cheap, scaling matters |
| Standard Read+analyze (TRD intake, AC parsing, scenario draft, code review for style) | **sonnet** | balanced — most work lives here |
| Severity calls, AC ambiguity dispute, calibration, architecture review with judgement, multi-system root-cause | **opus** | reasoning depth dominates throughput |

Orchestrator passes model in `Task()` params: `Task(model="haiku", subagent_type=…, …)`.
Mixed waves are normal: one Opus + three Haikus is cheaper AND smarter than four Sonnets when load divides cleanly.

### Rule 3 — Parallel waves
Independent subtasks → SINGLE message with multiple `Agent` tool_use blocks.
Inherits CLAUDE.md «PARALLEL tool execution» rule, applied recursively to delegation.

Self-check before send: if N subtasks declared independent → count `Agent` blocks in current turn → must be N. If <N → repack into one message.

### Rule 4 — Numbered rounds
Format every decomposition as **R1→R2→R3** (more if needed). Each round reads results of previous round.

- **R1** — parallel discovery (cheap, broad). Output: structured findings.
- **R2** — targeted deep-dive on R1's signals. May be parallel or sequential.
- **R3** — synthesis + final write (intake.md, scenarios.md, bug payload).

State explicitly in chat: «R1 запускаю 4 parallel agents, читаю результаты, потом R2».
This is the audit trail Yaroslav can scan.

### Rule 5 — Existing Anthropic infrastructure (don't reinvent)

| Need | Use | Don't |
|---|---|---|
| Sub-agent delegation | `Task(subagent_type=…, model=…)` | Don't write your own sub-agent runner |
| Background work | `Task(run_in_background=true)` + wait notification | Don't poll manually with sleep |
| Recurring routines | `mcp__scheduled-tasks__create_scheduled_task` | Don't ask user to set crontab |
| Domain workflows | `scalefinal-qa-assistant:*` skills | Don't reimplement skill logic inline |
| Self-pacing loops | `/loop` skill | Don't manual sleep+wake cycle |
| Specialist roles | `subagent_type` (e.g. `code-reviewer-pro`, `debugger`, `qa-expert`, `Explore`) | Don't free-write specialist prompts |
| Task tracking | `TodoWrite` (mark in_progress→completed) | Don't keep state only in prose |
| User prompts | `AskUserQuestion` (chip UI) | Don't ask 4 yes/no in prose |
| Memory across turns | Files (qa-output, journal) | Don't expect chat history alone |

`/agents` slash command lists ALL available subagent_types — orchestrator MUST consult it before free-writing a "general-purpose" prompt for a task that has a specialist.

---

## Templates

### Template A — Discovery wave (R1)

> Use when: scope unclear, need broad recon before decomposition.

```
R1 — parallel discovery (single message, 4 Agent calls):

Task(model="haiku", subagent_type="general-purpose",
     description="Read ticket content",
     prompt="Read TRD-X via youtrack:get_ticket. Extract:
             AC count, type, status, linked count.
             Report under 100 words. Cite exact AC numbers.")

Task(model="haiku", subagent_type="general-purpose",
     description="List linked tickets",
     prompt="Call youtrack:get_linked_tickets(TRD-X).
             Group by link_type (subtask/relates/duplicate).
             Report ids only with one-line summaries.")

Task(model="haiku", subagent_type="Explore",
     description="Search bugs.json for cluster",
     prompt="Use Bash python on knowledge_base/bugs.json —
             find OPEN bugs mentioning area X.
             Top 5 by recency. Report id+title+status only.")

Task(model="sonnet", subagent_type="general-purpose",
     description="Search Slack for area X",
     prompt="Use slack MCP — search #qa for 'X' in last 7d.
             Surface 1-3 relevant threads with permalink + tldr.
             If MCP not loaded, ToolSearch first.")
```

After R1 returns → orchestrator analyzes → decides R2.

### Template B — Targeted deep-dive (R2)

> Use when: R1 surfaced specific items needing closer look.

```
R2 — sequential or parallel based on dependency:

Task(model="sonnet", subagent_type="qa-expert",
     description="Analyze AC#5 ambiguity",
     prompt="AC#5 of TRD-X reads <verbatim quote>.
             R1 found similar case in PROJ-201.
             Compare interpretations a/b.
             Cite §business_rules.md.
             Don't decide — surface trade-offs.")

Task(model="opus", subagent_type="general-purpose",
     description="Severity calibration on candidate bug",
     prompt="Evidence: <full evidence block>.
             Walk severity algorithm (domain × scope × impact).
             Output: recommended severity + 1-line why.
             Don't auto-file — preview only.")
```

### Template C — Synthesis (R3)

> Use when: R1+R2 done, need final artifact.

```
R3 — synthesis (orchestrator-self OR single agent):

Option 1 (orchestrator self): aggregate R1+R2 outputs → write qa-output/intake.md inline.
Option 2 (delegate):
  Task(model="sonnet", subagent_type="general-purpose",
       description="Write intake.md from R1+R2 findings",
       prompt="Inputs: <R1 result block>, <R2 result block>.
               Write qa-output/intake.md per template in
               skills/start-ticket-test/SKILL.md §intake-template.
               EN per language matrix. Cite source IDs.")
```

---

## Decision tree — when to decompose vs go solo

```
Is the task self-contained AND under 3 independent reads?
  → solo (orchestrator does it inline)

Are some subtasks trivial (haiku-grade) AND others judgement-heavy (opus-grade)?
  → decompose (different agents save cost + improve quality)

Is the work bursty (>5 independent ops at once)?
  → decompose (parallel waves are 4-10× faster than serial)

Will work span >2 hours?
  → decompose into checkpoints + run_in_background where possible

Is it a clear single-skill task (one of 5 plugin skills)?
  → invoke skill, don't decompose
```

---

## TodoWrite integration

Orchestrator MUST use `TodoWrite` for any multi-round work:

```
TodoWrite([
  {content: "R1: parallel discovery (4 agents)", status: "in_progress"},
  {content: "R2: deep-dive on AC#5 + severity",  status: "pending"},
  {content: "R3: write qa-output/intake.md",      status: "pending"},
])
```

Mark `in_progress` BEFORE spawning the wave. Mark `completed` immediately after results aggregated. Spawn next round → new in_progress.

This is the audit trail — Yaroslav can scan and see decomposition state at any moment.

---

## Self-management loop (the 4 verbs)

Orchestrator runs this loop on every multi-round decomposition:

1. **Create** — declare round in chat + spawn agents (`TodoWrite` in_progress + `Task` × N)
2. **Verify** — read each Task result; reject if format wrong / required fields missing
3. **Close** — `TodoWrite` mark completed only after results validated
4. **Decide** — analyze cumulative findings → next round OR terminate

If verify-step fails on a Task result (agent returned malformed output / missing fields):
- Don't paper over — report to Yaroslav with «Agent X returned unusable output, re-run with tighter prompt or escalate?»
- Track failures in journal as decomposition friction

---

## Anti-patterns

| ❌ Don't | ✅ Do |
|---|---|
| Spawn one mega-agent «do the whole thing» | Decompose into narrow R1/R2/R3 |
| Sequential when parallel works | Single message, multiple Agent calls |
| Opus for trivial file reads | Haiku for reads, sonnet for analysis, opus for judgement |
| Sonnet for severity calibration | Opus + xhigh effort for judgement-critical |
| Forget TodoWrite tracking | Mark every round in_progress→completed |
| Reinvent specialist prompts | Use `subagent_type` from `/agents` catalog |
| Manual polling for background work | `Task(run_in_background=true)` + wait notification |
| Free-form delegation prose | Templates A/B/C with model+subagent_type+desc |
| Trust agent output blindly | Verify format/fields before closing TodoWrite item |
| Decompose for trivial tasks | Solo when <3 ops |

---

## Cost calibration

Per typical Task() call (~5K tokens roundtrip):
- **Haiku**: ~$0.005 — file reads, grep, list ops
- **Sonnet 4.6**: ~$0.05 — standard reasoning
- **Opus 4.7**: ~$0.25 — judgement + extended reasoning

**Mixed wave example:** 3×haiku + 1×sonnet R1 ≈ $0.07.
**Mega-opus alternative:** single opus does the same work ≈ $0.50.
**Decomposition wins ≥3 subtasks** (cost AND quality, because each agent has narrow context and clear deliverable).

---

## Concrete example — TRD retest decomposition

Task: «retest TRD-13812 на release».

**Solo path** (single agent does everything): one mega-message, mixed reasoning, ~30K tokens, lossy attention.

**Decomposed path:**

```
TodoWrite([
  {content: "R1: parallel pre-load (5 haiku agents)", status: "in_progress"},
  {content: "R2: AC ambiguity check + bug cluster analysis", status: "pending"},
  {content: "R3: write intake.md + Cockpit summary", status: "pending"},
])

R1 (single message, 5 Agent calls):
  haiku — youtrack:get_ticket(TRD-13812)
  haiku — youtrack:get_linked_tickets(TRD-13812)
  haiku — youtrack:get_comments(TRD-13812, max=50)
  haiku — allure:find_test_cases_by_issue(TRD-13812, include_scenario=true)
  haiku — Bash: grep TRD-13812 in journal/2026-*.md

[results aggregated → orchestrator analyzes → marks R1 completed → starts R2]

R2 (parallel — 2 agents, only if R1 surfaced signals):
  sonnet (qa-expert) — AC#3 wording vs Insight 14 (stage↔release drift)
  sonnet — bugs.json cluster: similar Email Builder bugs in last 30d

[R2 done → R3]

R3 (orchestrator-self):
  Write qa-output/intake.md
  Surface Cockpit summary
  STOP — await Phase 2 approval
```

Cost: 5×$0.005 + 2×$0.05 + self ≈ $0.13 vs ~$0.50 mega-opus.
Quality: each agent has narrow context = sharper output.
Audit: TodoWrite trail shows decomposition explicitly.

---

## Failure modes & recovery

| Failure | Symptom | Recovery |
|---|---|---|
| Agent returns wrong format | "Report under 100 words" came back as 500-word essay | Re-spawn with stricter prompt OR run_in_background and wait |
| Agent times out | No result after timeout | Retry with smaller scope OR escalate to user |
| Wave produces conflicting findings | R1 agent A says «exists», agent B says «not found» | R2 narrow probe to disambiguate; don't synthesize on conflict |
| R3 synthesis incomplete | Required fields missing | Don't write artifact; surface gap to Yaroslav |
| Context bloat from too many waves | >3 rounds without convergence | Stop; re-scope; consider new chat |

---

## See also

- `orchestrator_persona.md §13` — model recommendation matrix at task entry
- `CLAUDE.md` — PARALLEL tool execution rule (recursively applies to Task delegation)
- `/agents` — slash command listing all available `subagent_type` values
- Skill: `loop` — for self-pacing recurring work
- Skill: `schedule` — for cron-style routines via `mcp__scheduled-tasks__*`
- `qa_brain_master_plan.md` — strategic context for when decomposition fits the bigger plan
