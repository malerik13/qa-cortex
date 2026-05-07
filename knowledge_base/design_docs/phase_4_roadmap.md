# Phase 4 — Real-Instance Validation Roadmap

> **Status:** PLAN · current phase after v0.2.0-alpha (Phase 3 COMPLETE)
> **Created:** 2026-05-07
> **Scope:** End-to-end validation on real backends by two independent installers
> **Effort estimate:** 4-8h spread across 1-2 weeks (calendar, not continuous)
> **Parent:** `qa_cortex_v1.md` §12 Phase 4
> **Reading time:** ~10 min

---

## What Phase 4 proves

Phase 3 ended with 78 passing unit tests, integration scaffolds, full documentation, and a setup wizard. But none of that proves the system works on a real Jira+TestRail instance from a cold start.

Phase 4 closes that gap. Success criterion: **two independent humans install qa-cortex from scratch, following only the published docs, and reach a working brain on their own stacks.**

If both succeed → tag `v1.0.0-rc1`. If they hit blockers → fix, iterate, retry.

**Why two validators:** Yaroslav knows the codebase. His install catches broken mechanics. A second validator (friend/colleague) has no context — catches anything that requires implicit knowledge to succeed.

---

## Phase 4 participants

| Role | Validator | Stack | Docs path |
|---|---|---|---|
| P1 — Internal | Yaroslav (2nd computer) | Fresh macOS, Jira + TestRail + Confluence + Slack | `examples/jira-testrail.md` + `INSTALL.md` |
| P2 — External | Friend / colleague | Their own Jira+TestRail (or Atlassian free trial) | `README.md → Quick start` + `examples/jira-testrail.md` |

P2 should attempt install **without any real-time help from Yaroslav**. Async questions OK — but Yaroslav shouldn't be hovering. Friction they hit = docs gap.

---

## P1 install procedure (Yaroslav, 2nd computer)

### Pre-conditions

- Fresh macOS (or Linux) that has NOT had qa-cortex before
- Python 3.10+ installed
- Claude Code installed (`claude` command works)
- Access to: Jira Cloud, TestRail, Confluence (same Atlassian as Jira), Slack workspace
- 30-60 min for credential setup + wizard

### Validation checklist

Follow `examples/jira-testrail.md` exactly, in order. Check each box when done:

**Setup:**
- [ ] 1. Cloned repo successfully
- [ ] 2. `pip install -e ".[dev]"` completed without errors
- [ ] 3. `pip install atlassian-python-api testrail-api slack-sdk` completed
- [ ] 4. Setup wizard ran: `python scripts/setup.py`
- [ ] 5. Wizard accepted all inputs without errors
- [ ] 6. `qa-cortex.config.toml` exists in repo root
- [ ] 7. `.env` exists in repo root, mode 0600

**Verification:**
- [ ] 8. `python scripts/setup.py --check` returns "config valid"
- [ ] 9. `pytest tests/` returns "78 passed" (or expected pass count)

**Brain smoke test:**
- [ ] 10. `claude` opens Claude Code without errors
- [ ] 11. Try `Тестируем <your-ticket-key>` — brain loads persona
- [ ] 12. Brain fetches ticket from your Jira (real call, not mock)
- [ ] 13. Brain finds linked TestRail cases
- [ ] 14. Brain builds Cockpit summary
- [ ] 15. Brain STOPS before Phase 2, waits for approval (Tier 3 gate working)
- [ ] 16. `qa-output/intake.md` exists and has structured content
- [ ] 17. `journal/<DATE>.md` has `mission` entry

**Bug filing smoke test (optional but recommended):**
- [ ] 18. Try `Оформи баг: [some test issue]`
- [ ] 19. Brain asks 1st cohort classification verbatim (doesn't skip)
- [ ] 20. Brain shows preview with `approved=False`
- [ ] 21. Brain STOPS, waits for "yes" before submitting
- [ ] 22. On "yes" → ticket created in Jira

### What counts as success for P1

**All 17 core checkboxes (1-17) pass.** Bug test (18-22) is bonus — if it exposes friction, document it.

---

## P2 install procedure (external validator)

### Docs path

P2 follows strictly:
1. `README.md` → Quick start section (first touchpoint)
2. `examples/jira-testrail.md` (full walkthrough)
3. `INSTALL.md` if Quick start is missing something

P2 does NOT read `docs/architecture.md` or `docs/adding-providers.md` — those are for after install.

### P2 pre-conditions

- Atlassian Cloud account (free trial OK) with Jira project + Confluence
- TestRail account (free trial OK)
- Slack workspace (any) + ability to create a Slack app
- Python 3.10+, Claude Code installed
- NO guidance from Yaroslav except async questions after hitting a blocker

### P2 validation scope

Same 17-box checklist as P1. P2 additionally notes:

- Where docs were unclear or missing (exact sentence they got stuck on)
- Any install steps that required guessing
- Time taken for each major step (credential setup / wizard / first chat)

### P2 reporting

After completing (or blocking), P2 sends Yaroslav:

1. Checklist status (which boxes passed/failed)
2. List of friction points: `"Got stuck at X because doc said Y but actual error was Z"`
3. Total time from `git clone` to working brain

---

## Friction reporting protocol

Both validators log friction as they go. Don't wait until the end — log immediately when something doesn't work as expected.

### Friction log format

```
FRICTION-001
Step: examples/jira-testrail.md §5 "Run setup wizard"
Expected: wizard prompts for TestRail project_id
Actual: wizard accepted input but wrote wrong key to config ("project" vs "project_id")
Impact: setup.py --check fails with ConfigError
Fix idea: rename key or update wizard prompt
```

One file per validator: `phase4/p1-friction-log.md`, `phase4/p2-friction-log.md` (gitignored).

### Severity classification

| Level | Description | Action |
|---|---|---|
| **BLOCKER** | Cannot proceed, no workaround | Fix before continuing, retest that step |
| **FRICTION** | Workaround exists but took >5 min to find | Fix before v1.0.0-rc1, document workaround meanwhile |
| **MINOR** | Confusing but solvable in <2 min | Fix before public release (Phase 5), not blocking rc1 |

---

## Iteration cycle

```
Validator hits BLOCKER
    ↓
Log friction entry
    ↓
Yaroslav reads, identifies fix
    ↓
Fix (code / docs / wizard) in qa-cortex repo
    ↓
Validator re-tries that step from the point of failure
    ↓
Continue checklist
```

Expectation: 2-4 iteration cycles before P1 clears all boxes. P2 may need more if they hit different issues.

**Target: zero BLOCKERs by end of Phase 4.** All FRICTIONs documented in CHANGELOG and fixed. MINORs captured in GitHub issues (future work).

---

## Phase 4 steps

### Step 1 — Setup test instance resources (1-2h)

Before validating, create the backend instances the validator will connect to.

Jira + Confluence:
- Create free Atlassian Cloud account (if not already): https://www.atlassian.com/try
- Create Jira project: key `QACT`, type "Scrum"
- Create at least 3 tickets with different types (Story, Bug, Task)
- Add issuelinks on at least one ticket (Jira "Relates to" another ticket)
- Generate Jira API token: https://id.atlassian.com/manage-profile/security/api-tokens

TestRail:
- Create free TestRail trial: https://www.gurock.com/testrail/trial.html
- Create project "qa-cortex Test"
- Add custom field `custom_jira_id` (String type, see `examples/jira-testrail.md §2`)
- Create 2-3 test cases with `custom_jira_id = QACT-1`

Slack:
- Create Slack app in test workspace: https://api.slack.com/apps
- Add required scopes (see `examples/jira-testrail.md §3`)
- Invite bot to test channel

Done when: all four backends available, API tokens in hand.

### Step 2 — P1 cold install (2-3h, Yaroslav)

Follow P1 validation checklist above on a second machine (or fresh macOS user account if 2nd machine not available).

**Critical rule:** do NOT use any knowledge from building the product. If a step fails, treat it as a real user would — follow the docs, don't patch it from memory.

Log all friction as you go.

Done when: all 17 boxes checked or all blockers documented.

### Step 3 — Fix P1 blockers (0.5-2h, per blocker)

For each BLOCKER from P1's log:
1. Identify root cause (code bug, docs gap, or wizard logic error)
2. Fix in qa-cortex repo
3. Commit with reference to friction entry
4. P1 retests that step

Iterate until P1 clears all 17 boxes.

### Step 4 — P2 cold install (async, 1-3h for P2)

Send P2 the repo URL and one sentence: "Install this, follow the README, let me know where you get stuck."

No additional context. P2 follows the published docs only.

Done when: P2 reports final checklist status.

### Step 5 — Fix P2 blockers (0.5-2h, per blocker)

Same fix cycle as Step 3. P2 may hit different issues than P1 (especially docs clarity issues).

### Step 6 — Final validation pass

After all blockers from P1 + P2 are fixed:

1. P1 runs through checklist one final time (fresh clone, clean state)
2. `pytest tests/` still passes (no regressions from friction fixes)
3. `python scripts/setup.py --check` passes on known-good config

If both pass → Phase 4 complete.

---

## Promotion criteria to v1.0.0-rc1

All of the following must be true:

| Criterion | Check |
|---|---|
| P1 checklist: all 17 core boxes pass | |
| P2 checklist: all 17 core boxes pass (or known-blocked with documented workaround) | |
| Zero BLOCKER friction items remaining | |
| `pytest tests/` passing count matches expected (78+) | |
| `python scripts/setup.py --check` clean on valid config | |
| Friction fixes have test coverage (new test for each code fix) | |
| CHANGELOG updated with all fixes | |
| README "Status" badge updated to "rc1" | |

When all boxes checked → tag `v1.0.0-rc1`, update README status badge.

---

## Phase 5 decision framework (public release)

Phase 5 = public release. Not required immediately after rc1 — decision depends on:

### Signals for "ready to release"

1. **Stability:** rc1 has been used for 1-2 real QA sessions without code changes needed
2. **Docs completeness:** `docs/adding-providers.md` tested by actually adding a 2nd provider (e.g. Linear or GitHub)
3. **Contribution readiness:** CONTRIBUTING.md written, issue templates created
4. **Visibility:** where to announce (Reddit r/QualityAssurance, HN, testing community) — identified
5. **License checked:** MIT license in `LICENSE` file, no code from incompatible licenses pulled in

### Signals for "not ready yet"

- rc1 has a known BLOCKER that requires workaround knowledge
- No one except Yaroslav has successfully installed it end-to-end
- `docs/adding-providers.md` untested (can't tell contributors to add providers if the guide itself is wrong)

### Minimum bar for public release

- v1.0.0-rc1 tag exists
- P2 successfully installed without Yaroslav's help
- `docs/adding-providers.md` tested (at least conceptually, better if actually used)
- No known BLOCKERs
- README accurately reflects what works and what doesn't (no false advertising)

When signals align → cut `v1.0.0` tag, make repo public, announce.

---

## Risk register (Phase 4 specific)

| Risk | Likelihood | Impact | Mitigation |
|---|---|---|---|
| Atlassian free trial expires mid-validation | Medium | Medium | Create trial account fresh before starting; 14-day window usually enough |
| P2 doesn't have time / drops out | Medium | Medium | Have fallback P2; or do two separate P1 installs on different stacks |
| TestRail free trial too restrictive | Low | Medium | TestRail trial supports custom fields; verify before handing docs to P2 |
| MCP server fails to start in real Claude Code | Medium | High | Test `plugin.json` MCP startup explicitly as first P1 step |
| Adapter library version conflicts | Low | High | Pin versions in requirements.txt, test `pip install` on clean venv |
| `approved=True` gate misfires in real session | Low | Critical | Covered by unit tests; if happens → BLOCKER, fix before rc1 |

---

## Out of Phase 4 scope

- Adding new providers (Linear, GitHub, Notion) — Phase 5+
- PyPI publication — Phase 5+
- CI/CD pipelines — Phase 5+
- Multi-user / team installs — Phase 5+
- Performance benchmarking — Phase 5+

---

## Docs produced by Phase 4

After Phase 4, these new files exist:

```
CHANGELOG.md                         ← created, listing Phase 4 fixes
phase4/p1-friction-log.md           ← gitignored, internal reference
phase4/p2-friction-log.md           ← gitignored, internal reference
```

README.md `## Status` section updated:
```
**🚧 Release Candidate 1 — v1.0.0-rc1**

Validated by two independent installers on Jira + TestRail default stack.
Zero known blockers. Pending Phase 5 public release decision.
```

---

## Estimated timeline

| Step | Effort | Calendar |
|---|---|---|
| Step 1 — Create test instances | 1-2h | Day 1 |
| Step 2 — P1 cold install | 2-3h | Day 2-3 |
| Step 3 — Fix P1 blockers | 1-3h | Day 3-4 |
| Step 4 — P2 install (async) | 1-3h for P2 | Day 4-7 |
| Step 5 — Fix P2 blockers | 1-2h | Day 7-9 |
| Step 6 — Final pass | 1h | Day 10 |
| **Total** | **7-14h, ~1.5-2 weeks calendar** | |

Dominant factor: P2 availability. If P2 is fast → 1 week. If async → 2 weeks.

---

## What's the right next step from here

From current state (v0.2.0-alpha, Phase 3 done):

**Option A — Start Phase 4 immediately:**
Create test backends (Step 1), do P1 install on 2nd machine now. This is the highest-value next action — everything else is polish until Phase 4 validates that the product works at all.

**Option B — Phase 4 prep polish first:**
Before P2 engagement, review all docs once more as a fresh reader. Fix any obvious gaps spotted during Phase 3 that weren't tracked as issues. Then hand to P2.

**Recommendation: Option A.** Don't polish indefinitely. Real validation exposes real gaps — docs review without install is just theory.

This roadmap doc is reference. Future sessions pick up from any step by reading its section.
