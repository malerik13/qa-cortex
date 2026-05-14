# Sub-Agent Delegation Map

> **Load when:** considering delegation to a specialist sub-agent. Or when reasoning about R1/R2/R3 multi-agent waves.
>
> **Lazy-load trigger:** «delegate», «sub-agent», «специалист для X», "let me get a specialist".

---

## Pool

**153 VoltAgent sub-agents** in `~/.claude/agents/`. Direct invocation:

```
Task(subagent_type="<name>", description="<short>", prompt="<self-contained>")
```

No namespace prefix needed. Names taken directly from `.md` filename (e.g. `qa-expert.md` → `subagent_type="qa-expert"`).

---

## Phase-mapped delegation (6-phase QA lifecycle)

| Phase | Default sub-agent | Use case |
|---|---|---|
| Phase 1 (Preparation, ticket-not-yet-implemented) | — | Brain does intake itself; no sub-agent needed |
| Phase 2 (Allure launch / test code generation) | `test-automator` | IF generating test code from scenarios |
| **Phase 3 (Execution)** | `ui-ux-tester` | Drives Playwright through documented flows |
| **Phase 4 (Defects)** | — | Our `bug-report` skill handles drafting + approval gate |
| **Phase 5 (Validation after fix)** | `code-reviewer` + `qa-expert` | Diff analysis + test impact assessment |
| Phase 6 (Close, multi-repo) | `code-reviewer` | Cross-repo diff sanity check |

---

## High-value sub-agents (on-demand, not phase-bound)

| Sub-agent | When |
|---|---|
| `debugger` | Flaky tests, hard-to-repro bugs, mysterious behavior |
| `security-auditor` | Auth/payment ticket review, OWASP-relevant scenarios |
| `mcp-developer` | Extending our youtrack/allure MCPs, building new MCP server |
| `chaos-engineer` | Resilience scenarios, failure mode exploration |
| `accessibility-tester` | WCAG compliance checks, a11y audits |
| `multi-agent-coordinator` | R1/R2/R3 orchestration when task complex (see `orchestration_playbook.md`) |
| `qa-expert` | QA strategy, test framework decisions, coverage analysis |
| `test-automator` | Generating tests from scenarios |
| `database-administrator` | Database performance, replication, HA setup |
| `database-optimizer` | Slow queries, index strategies |
| `error-detective` | Error correlation across services, root cause hunting |
| `slack-expert` | Slack API integration, bot security review |
| `terraform-engineer` | IaC for infrastructure |
| `penetration-tester` | Active vulnerability exploitation testing |

---

## Decision tree — delegate vs solo

```
Is task self-contained AND under 3 independent reads?
  → Solo (brain does it inline)

Are some sub-tasks trivial AND others judgement-heavy?
  → Decompose with model-by-complexity:
      - haiku for trivial reads
      - sonnet for standard analysis
      - opus for judgement calls
      (See orchestration_playbook.md Rule 2)

Is work bursty (>5 independent ops)?
  → Decompose into parallel wave (single message, N Agent calls)
  → R1 → R2 → R3 pattern per orchestration_playbook

Will work span >2 hours?
  → Decompose into checkpoints + run_in_background where possible

Is it a clear single-skill task (one of our 7 skills)?
  → Invoke skill, don't decompose
```

---

## Parallel waves (R1/R2/R3)

For complex decomposition — see `knowledge_base/orchestration_playbook.md` for full pattern.

Quick reference:
- **R1** — parallel discovery (cheap, broad). Single assistant message, N `Agent` blocks. Each agent narrow micro-task.
- **R2** — targeted deep-dive on signals from R1
- **R3** — synthesis + write artifact

Model assignment per sub-task:
- File read, single grep, list dir → `haiku`
- Standard analysis (TRD intake, AC parsing, scenario draft) → `sonnet`
- Judgement (severity, AC ambiguity, calibration) → `opus`

---

## Cost calibration (rough)

Per typical Task() call (~5K tokens roundtrip):
- **Haiku**: ~$0.005 — file reads, grep, list ops
- **Sonnet 4.6/4.7**: ~$0.05 — standard reasoning
- **Opus 4.7**: ~$0.25 — judgement + extended reasoning

Mixed wave example: 3×haiku + 1×sonnet R1 ≈ $0.07.
Mega-opus alternative: single opus does same work ≈ $0.50.
**Decomposition wins ≥3 sub-tasks** (cost AND quality, because each agent has narrow context and clear deliverable).

---

## Source

- v0.7.2 orchestration playbook
- VoltAgent collection 19.4k★ installed 2026-05-09 (153 agents)
