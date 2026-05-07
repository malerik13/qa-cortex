# Design Doc — Flow Cache & Recipe Library v1.0

> **Status:** PROPOSAL · awaiting Yaroslav approval before implementation
> **Author:** qa-cortex brain (with Yaroslav)
> **Created:** 2026-05-06
> **Target tag:** v0.6.0 (after Phase A validation)
> **Reading time:** ~15 min

---

## TL;DR

Brain currently re-discovers UI flows from scratch in every session. A typical QA session spends **60% of token budget on UI exploration** (snapshots, evaluates, click→read→click). Most of those flows repeat (login, navigate to client, open template editor, etc).

**Proposal:** introduce a **3-tier amortization ladder** — Discovery → Recipe → Playwright — so each flow's exploration cost is paid once, replayed cheaply forever, and eventually compiled to autonomous Playwright scripts.

**Expected savings:** ~68% of UI-related tokens after 4-6 weeks of warm-up. Concrete model in §10.

**Risk:** medium — UI drift, recipe maintenance debt, concept-creep with Allure. Mitigations in §11.

**Phased rollout:** Phase A (1.5-2h) validates concept on 3 hand-written recipes. Phase B (auto-distill) and Phase C (Playwright promotion) gated on Phase A success.

---

## 1. Problem statement

### 1.1 Observed cost (forensic data, 2026-05-06)

Two test sessions analyzed in detail:

| Session | Tool | Calls | Tokens | % of session |
|---|---|---:|---:|---:|
| <TICKET>-13822 (Forgot Password) | `browser_snapshot` | 17 | ~22K | **48%** |
| <TICKET>-13812 (Brand variables) | `browser_snapshot` | 7 | ~3-5K | ~10% (after token-economy fix) |
| <TICKET>-13812 (Brand variables) | `browser_evaluate` | 50 | ~24K | ~40% |

Browser-related tools dominated tool-result tokens. Even after `browser token economy` patterns reduced raw snapshot count, the **discovery work itself** (figuring out which selectors work, which clicks succeed, what state the modal returns) remains expensive.

### 1.2 Repeating discovery is the actual waste

Login flow alone:
- Navigate to login page → snapshot to find inputs → fill email → fill password → snapshot to verify → click submit → wait → snapshot to confirm dashboard
- ~6-8K tokens per execution
- **Done in every QA session.** Every. Time.

Same for: create-client, attach-employee, open-template-editor, switch-brand, bulk-actions navigation, swap-profile flow, KYC review flow, etc. — well-known recurring patterns.

### 1.3 Why this is the highest-ROI fix

- CLAUDE.md trim cycle: cut 11K tokens, saves ~11K per turn (chat overhead) — high frequency, low per-incident impact
- Skill checkpoints: improve correctness, modest token impact
- Browser token economy patterns: ~70% reduction per browser action — applied once, saves on every action
- **Flow caching: amortizes discovery. One flow re-used 10× saves ~290K tokens.** Per-flow ROI is 1-2 orders of magnitude larger than any other optimization on the table.

---

## 2. Goals & non-goals

### 2.1 Goals

1. **Reduce UI exploration tokens by 60%+** within 6 weeks of warm-up
2. **Self-bootstrapping** — recipes accumulate from regular QA work, no separate "recipe writing" project
3. **Self-healing** — UI drift detection + auto-refresh on selector failure
4. **Promotion path** — high-use recipes graduate to Playwright `.spec.ts` for autonomous regression runs
5. **Allure-friendly** — recipes link to Allure cases, complement not replace
6. **Portable** — concept works on any stack (templates for friend's Jira/TestRail brain)

### 2.2 Non-goals

1. **Replace Allure cases** — Allure remains source of truth for formal QA documentation. Recipes are brain's *executable memory*, separate concern.
2. **Replace Playwright tests** — long-term Playwright suite remains primary regression infrastructure (when written by humans). Recipes are intermediate layer + bootstrap for Playwright.
3. **Capture every detail** — recipes are *replay scripts*, not full UI maps. Don't try to model every page.
4. **Cross-environment magic** — a recipe is per-env initially (stage vs release). Cross-env unification is later concern.
5. **Visual regression** — out of scope. Recipes verify text/state, not pixel-perfect visuals (that's Allure-screenshot territory).

---

## 3. Architecture overview

### 3.1 The 3-tier ladder

```
┌─────────────────────────────────────────────────────────────────────┐
│                         TIER 1: DISCOVERY                           │
│  First time brain encounters a flow                                 │
│  Tools: browser_snapshot, browser_evaluate, browser_click           │
│  Token cost: ~30-50K per flow                                       │
│  Output: working path discovered + saved as recipe                  │
└─────────────────────────────────────────────────────────────────────┘
                            │
                            │ (auto-distill at end of successful flow)
                            ▼
┌─────────────────────────────────────────────────────────────────────┐
│                         TIER 2: RECIPE REPLAY                       │
│  Brain reads cached recipe, executes verified path                  │
│  Tools: Read recipe, browser_navigate, browser_fill (by selector),  │
│         browser_click (by selector), browser_evaluate (verify)      │
│  Token cost: ~500-1K per flow                                       │
│  Output: pass/fail + updated recipe last_verified date              │
└─────────────────────────────────────────────────────────────────────┘
                            │
                            │ (after N successful replays — promotion criteria)
                            ▼
┌─────────────────────────────────────────────────────────────────────┐
│                         TIER 3: PLAYWRIGHT SCRIPT                   │
│  Compiled .spec.ts file, runs via `npx playwright test`             │
│  Tools: Bash to invoke playwright, parse result                     │
│  Token cost: ~200 per flow (orchestration only)                     │
│  Output: pass/fail + Playwright report                              │
└─────────────────────────────────────────────────────────────────────┘
```

### 3.2 Directory structure

```
flows/
├── _index.json                          ← lookup index (auto-generated)
├── auth/
│   ├── login-aaa.recipe.md
│   ├── login-qatestbot.recipe.md
│   └── 2fa-bypass.recipe.md
├── client-mgmt/
│   ├── create-client-individual.recipe.md
│   ├── create-client-corporate.recipe.md
│   ├── attach-employee.recipe.md
│   └── bulk-actions-emails.recipe.md
├── brand/
│   ├── switch-brand.recipe.md
│   └── update-brand-variables.recipe.md
├── trading/
│   └── ...
└── playwright/                          ← Tier 3 compiled scripts
    ├── auth/
    │   └── login-aaa.spec.ts
    ├── client-mgmt/
    │   └── ...
    └── tsconfig.json
```

### 3.3 Skill integration points

- **`start-ticket-test/SKILL.md` Step 3.5 (NEW)**: recipe lookup before discovery
- **`start-ticket-test/SKILL.md` Step 7.7 (NEW)**: auto-distill recipe at end of successful Phase 3
- **CLAUDE.md anti-pattern (NEW)**: «Don't re-discover when recipe exists» — minor reminder
- **`scripts/refresh-flows-index.py` (NEW)**: rebuild `_index.json` from filesystem state (called periodically + on commit hook)

---

## 4. Recipe format specification

### 4.1 File naming

`flows/<area>/<flow-id>.recipe.md`

- `<area>`: kebab-case, matches one of: `auth`, `client-mgmt`, `brand`, `trading`, `finance`, `kyc`, `analytics`, `comms`, `settings`, `misc`
- `<flow-id>`: kebab-case, descriptive: `login-aaa`, `create-client-individual`, `bulk-emails-multi-client`

### 4.2 Frontmatter (YAML, machine-parseable)

```yaml
---
flow_id: auth.login.aaa                    # canonical ID, used in _index.json
last_verified: 2026-05-06                  # ISO date, auto-updated on successful replay
last_verified_env: stage                   # which env was used for last verification
verification_count: 7                      # how many times replayed successfully
discovery_session: 12a2b5ec-...            # session UUID where flow was first discovered

env: [stage, staging-ca, release, release-ca, demo]   # which envs this recipe is tested for
role: aaa                                   # which user role
estimated_replay_tokens: 800                # rough cost when replayed via brain
estimated_discovery_tokens: 12000           # cost when re-discovered (for break-even math)

allure_case_id: 2544                        # crosslink to formal Allure case (optional)
playwright_spec: null                       # path to .spec.ts when promoted (else null)

related_recipes: [auth.2fa-bypass]          # other recipes this depends on / chains with
related_trd: [<TICKET>-12153, <TICKET>-13822]         # tickets this flow appeared in (recency hint)

selectors_strategy: data-test-first         # data-test-first | role-name-first | css-fallback
known_traps: [admin-2fa-lockout, session-30min-expiry]   # IDs of known issues, see §6.4

tags: [smoke, auth, foundational]
---
```

### 4.3 Body structure

```markdown
# <Flow human-readable name>

## When to use
<1-2 sentences — when a session would benefit from this recipe>

## Preconditions
- <list of state requirements, e.g. "user not logged in", "stage env up", "test client <TICKET>-12345 exists">

## Verified path
<Numbered steps — actionable, not narrative>

1. Navigate `<URL>`
2. Fill `<selector-strategy>` with `<value-or-env-var>`
3. Click `<selector-strategy>`
4. Wait for `<condition>` (max <Ns>)
5. Assert: `<verifiable claim>`

## Selectors (DOM-stable, NOT snapshot ref-IDs)

| Element | Primary strategy | Fallback 1 | Fallback 2 |
|---|---|---|---|
| Email input | `[data-test="email-input"]` | `input[name="email"]` | `text="Email"` (label proximity) |
| ... | ... | ... | ... |

## Postconditions
- <state after successful run>
- <cleanup needed? usually none>

## Known traps
- **<trap-id>**: <description + workaround>
- ...

## Token cost analysis
- Discovery (one-time): ~12K tokens (8 snapshots, 4 evaluates, 6 clicks)
- Replay (per-call): ~800 tokens (1 verify-snapshot, 4 fills via selector, 1 click, 1 wait, 1 assert)
- Playwright (when promoted): 0 brain tokens (bash orchestration only, ~200 for parse/report)

## Refresh history
- 2026-05-06 — discovered (<TICKET>-13822 retest)
- 2026-05-08 — replayed, all selectors stable
- 2026-05-12 — refreshed: `[data-test="email-input"]` changed → new attribute `[data-test="login-email"]`
```

### 4.4 Selector strategy hierarchy

When recording or replaying, brain tries selectors in this priority order:

1. **`data-test` / `data-testid` / `data-cy`** — explicitly QA-stable attributes (when qa-cortex instance frontend has them)
2. **Role + accessible name** — `role="button" name="Submit"` — survives most refactors
3. **Stable text content** — `text="Send Email"` — works for buttons/links with stable copy
4. **CSS selector by structural attrs** — `input[name="email"]`, `form#login-form` — fragile but common
5. **Index-based / nth-child** — last resort, brittle

**Recipe stores all viable strategies with priority** so failover is automatic.

---

## 5. Index & lookup mechanism

### 5.1 `flows/_index.json` schema

```json
{
  "version": "1.0",
  "generated_at": "2026-05-06T21:35:00Z",
  "recipes": [
    {
      "flow_id": "auth.login.aaa",
      "path": "flows/auth/login-aaa.recipe.md",
      "area": "auth",
      "tags": ["smoke", "auth", "foundational"],
      "envs": ["stage", "release"],
      "roles": ["aaa"],
      "last_verified": "2026-05-06",
      "verification_count": 7,
      "estimated_replay_tokens": 800,
      "related_trd": ["<TICKET>-12153", "<TICKET>-13822"],
      "playwright_spec": null
    },
    ...
  ],
  "by_trd": {
    "<TICKET>-12153": ["auth.login.aaa", "comms.send-email-from-template"],
    ...
  },
  "by_area": {
    "auth": ["auth.login.aaa", "auth.login-qatestbot", "auth.2fa-bypass"],
    ...
  }
}
```

### 5.2 Lookup algorithm (Step 3.5 in skill)

When `start-ticket-test` skill activates on <TICKET>-X:

```python
# Pseudocode — brain's mental model
def find_recipes_for_ticket(trd_id, ac_text, area_keywords):
    index = read_json("flows/_index.json")

    # Strategy 1: TRD direct match (was this exact TRD touched a recipe before?)
    direct = index["by_trd"].get(trd_id, [])

    # Strategy 2: area + keyword match
    area = infer_area(ac_text, area_keywords)
    by_area = index["by_area"].get(area, [])

    # Strategy 3: tag match
    by_tags = [r for r in index["recipes"] if any(t in r["tags"] for t in area_keywords)]

    candidates = dedupe(direct + by_area + by_tags)

    # Filter: stale (not verified in 30+ days) → demote priority but don't exclude
    fresh, stale = partition(candidates, lambda r: days_since(r["last_verified"]) < 30)

    return fresh + stale  # fresh first
```

### 5.3 Surface format to Yaroslav

After Step 3 pre-load, before Phase 1.5:

```
🔍 Flow recipe lookup:
   Found 3 candidates for <TICKET>-13822 (Forgot Password area = auth):
     ✓ auth.login.aaa (verified 2 days ago, replayed 7×) — fits Phase 3
     ✓ auth.forgot-password-trader (verified 5 days ago, replayed 2×) — direct match
     ⚠ auth.2fa-bypass (verified 35 days ago, stale) — refresh suggested

   Recommendation: use 2 fresh recipes for Phase 3 instead of full discovery.
   Estimated savings: ~22K tokens vs full discovery.

   [yes use them / discover anyway / refresh stale]
```

Yaroslav decides explicitly — recipe usage is opt-in initially. Later (after concept validated) → auto-use unless declined.

---

## 6. Distillation algorithm (auto-creation)

### 6.1 Trigger

End of Phase 3 (test execution) when:
- Test passed (or "not reproducible" verdict — flow itself worked, just bug not present)
- AND brain executed a coherent UI flow (≥3 sequential UI interactions)
- AND no existing recipe was used (i.e. this WAS a discovery run)

### 6.2 What to capture

Brain reviews its own session tool calls in Phase 3 and distills:

1. **Sequence of `browser_navigate` + `browser_click` + `browser_fill_form` + `browser_evaluate` calls** — these are the *path*
2. **For each click/fill** — extract selector from snapshot context (look up the ref in nearest preceding snapshot, get its DOM properties)
3. **For each navigate** — record URL pattern (templated with $env)
4. **For each evaluate** — record query + assertion if it was used as verification
5. **Session metadata** — <TICKET>-IDs touched, role used, env, total tokens

### 6.3 Distillation prompt (internal brain self-prompt template)

```
Self-task: distill flow recipe from this session's Phase 3 actions.

Inputs available:
- qa-output/intake.md (TRD context)
- session tool call log (filterable to Phase 3 actions)
- knowledge_base/glossary.md (for canonical terminology)

Output: flows/<area>/<flow-id>.recipe.md per format §4

Constraints:
- Selectors MUST be DOM-stable (data-test > role+name > text > css). Do NOT use ref_NN.
- Steps MUST be replayable in order without snapshot dependency between them.
- If a step required a snapshot to determine next action, mark as `verify-snapshot` step explicitly.
- env-specific values (URLs, credentials) → templated as $VAR not literal.
- Body length: target 30-60 lines. Brevity > exhaustiveness.
```

### 6.4 Known traps registry

`flows/_traps.json` — central registry of UI/flow gotchas referenced by `known_traps` field:

```json
{
  "admin-2fa-lockout": {
    "description": "AAA role triggers 2FA on staging, no Telegram bot — locks user out",
    "workaround": "Switch to qatestbot role (no 2FA)",
    "source": "Insight 7"
  },
  "session-30min-expiry": {
    "description": "Stage session cookie expires after 30min idle",
    "workaround": "Re-login if test_prep was hours ago",
    "source": "discovered <TICKET>-12153"
  }
}
```

Recipes reference traps by ID. New traps added when discovered, in journal + this registry.

---

## 7. Promotion to Playwright (Tier 3)

### 7.1 Promotion criteria

Recipe is candidate for Playwright promotion when:
- `verification_count >= 5` (proven stable across multiple uses)
- `last_verified` within last 14 days (still current)
- Recipe is "leaf" — doesn't compose other recipes (or all composed deps are also Tier 3)
- Yaroslav explicitly approves (initial phase) OR auto-trigger (later phase)

### 7.2 Generation process

```
Yaroslav: «promote auth.login.aaa to playwright»

Brain:
  1. Read flows/auth/login-aaa.recipe.md
  2. Invoke Task(subagent_type="qa-orchestra:automation-writer",
                prompt="Generate Playwright .spec.ts from recipe attached. Use selector strategies in priority order.")
  3. Save output to flows/playwright/auth/login-aaa.spec.ts
  4. Verify: bash 'cd flows/playwright && npx playwright test auth/login-aaa.spec.ts'
  5. If pass → update recipe frontmatter: playwright_spec: flows/playwright/auth/login-aaa.spec.ts
  6. If fail → rollback, log failure, ask Yaroslav to debug
  7. Subsequent calls to this flow: brain orchestrates `npx playwright test` instead of recipe replay
```

### 7.3 Playwright spec storage + execution

- Initially: standalone `flows/playwright/` directory with own `package.json` + `playwright.config.ts`
- One-time setup: `npm install --prefix flows/playwright`
- Execution: `cd flows/playwright && npx playwright test <area>/<flow>.spec.ts --reporter=json`
- Brain parses JSON result, surfaces pass/fail + duration

### 7.4 When NOT to promote

- Flow has high UI variability (modal contents change daily) — recipe is fine, Playwright would brittle
- Flow has manual judgement step (visual check, "does this look right?") — Playwright can't do that, manual stays
- Flow needs 2FA / Telegram code — Playwright can't bypass without real automation infrastructure (out of scope)

---

## 8. UI drift handling

### 8.1 Detection

When recipe is replayed and a step fails:
- Selector returns 0 elements → **selector drift**
- Wait condition timeouts → **flow drift** (page load took longer / state different)
- Assertion fails → **content drift** (expected text changed)

### 8.2 Auto-recovery flow

```
Recipe replay: step 3 fails ("Click button[type=submit]" → 0 matches)
   ↓
Brain: try fallback strategies in order
   ↓
   role+name fallback: button[role="button"][name="Sign in"]
   → success → continue + log "fallback used: role+name for step 3"
   ↓
   if all fallbacks fail:
   → enter mini-discovery: snapshot, find new selector for "submit button intent"
   → if found → update recipe with new primary + old as fallback
   → if not found → mark recipe as STALE, escalate to Yaroslav
```

### 8.3 Periodic refresh (later phase)

Background job (cron, weekly):
- For each recipe with `last_verified` > 14 days
- Run replay in non-disruptive env (release-ca?)
- Update `last_verified` on success, mark stale on fail

Not in v1.0 scope — manual refresh OK initially.

---

## 9. Conflict resolution

### 9.1 vs Allure cases

| Concern | Recipe | Allure case |
|---|---|---|
| Audience | Brain (executable memory) | Humans (formal QA documentation) |
| Format | YAML+Markdown, brain-parsable | Allure schema, Allure UI |
| Selectors | Yes, DOM-stable | No (steps are prose) |
| Maintenance | Auto-update on discovery/drift | Manual update by QA team |
| Versioning | Git in this repo | Allure server |
| Crosslink | `allure_case_id` field | <TICKET>-ID + manual link to recipe |

**Rule:** every Allure case can have ≥0 recipes implementing it. Every recipe SHOULD link to its Allure case if one exists. Recipes for one-off bug-retest flows may not have Allure case (and that's fine).

**Boundary:** if a flow becomes formal Allure case → keep recipe as runtime artifact. If Allure case retired → mark recipe deprecated, eventually delete.

### 9.2 vs `qa-orchestra:test-scenario-designer`

`test-scenario-designer` generates *test scenarios from AC* — what to test, in 4 categories (Happy/Negative/Boundary/Edge).

Recipes are *executions of one specific scenario*. Many recipes can implement scenarios from one designer output.

**Rule:** scenarios = abstract test ideas. Recipes = concrete executable paths. No conflict.

### 9.3 vs `qa-orchestra:browser-validator`

`browser-validator` is the agent that *runs* scenarios in browser. Currently dormant.

When activated: it would invoke recipes (Tier 2) for the parts of scenarios that have recipes. Discovery (Tier 1) for parts that don't.

**Rule:** browser-validator becomes recipe-aware in Phase B+. Until then it's dormant per current architecture.

### 9.4 vs portability template (friend's brain)

Concept transfers fully. Friend's brain on Jira+TestRail stack would have its own `flows/` with recipes for *its* product, not qa-cortex instance. Templates in `templates/flows/` need:
- Empty `flows/_index.json` skeleton
- Empty `flows/_traps.json` skeleton
- README explaining the concept
- Optional 1-2 example recipes (generic — login pattern, form submit pattern)

Add to `templates/` in Phase A or later.

---

## 10. Token amortization model

### 10.1 Variables

- `C_d` = discovery cost per flow ≈ **30,000** tokens (range 15-50K)
- `C_r` = recipe replay cost per flow ≈ **800** tokens (range 500-1500)
- `C_p` = Playwright orchestration cost per flow ≈ **200** tokens
- `N_d` = discovery sessions per week
- `N_r` = recipe replay sessions per week
- `N_p` = Playwright sessions per week
- Total flows in repo: **F**
- Repeat rate (% of week's flows that have existing recipes): **R**

### 10.2 Cold state (week 1, no recipes)

- All flows are discovery
- 20 sessions × 1.5 flows/session avg = 30 flow-executions/week
- Cost: 30 × 30K = **900K tokens/week** on UI work

### 10.3 Warm state (week 6, R=70%)

- 30 flow-executions/week
- Of those: 21 have recipes (70%), 9 are new discoveries
- Cost: 21 × 800 + 9 × 30K = **287K tokens/week**
- **Savings: ~613K tokens/week (-68%)**

### 10.4 Mature state (week 12, R=70%, P=30% promoted to Playwright)

- 30 flow-executions/week
- 9 new discoveries: 9 × 30K = 270K
- 6 Playwright orchestrations: 6 × 200 = 1.2K
- 15 recipe replays: 15 × 800 = 12K
- Cost: **~283K tokens/week**
- Savings vs cold: ~617K/week (-69%)
- Bonus: Playwright suite enables **autonomous overnight regression** (brain not in the loop)

### 10.5 Break-even

For a single flow:
- Discovery: 30K (one-time)
- Replay: 800 (per-use)
- Break-even after **1 reuse**: cumulative cost 30.8K (recipe path) vs 60K (re-discover twice)
- 5 reuses: 34K vs 150K — **4.4× cheaper**

Even if flow is never reused, recipe creation cost is ~500 tokens (distillation prompt itself) — negligible.

### 10.6 Per-month dollar estimate

At Sonnet 4.7 pricing (~$3/M input, $15/M output, ~70/30 split → blended ~$6.6/M):

- Cold: 900K × 4 weeks = 3.6M tokens/month → **~$24/month** on UI discovery
- Warm: 287K × 4 weeks = 1.15M tokens/month → **~$8/month**
- **Savings: ~$16/month + 4-6× faster session completion**

Plus: faster sessions = more QA throughput same hours.

---

## 11. Risks & mitigations

| Risk | Likelihood | Impact | Mitigation |
|---|---|---|---|
| **UI drift breaks recipes silently** | High | Medium | Multi-strategy selectors (§4.4), auto-recovery on miss (§8.2), periodic refresh job (§8.3) |
| **Recipe maintenance debt** | Medium | High | Self-healing on failure + `last_verified` staleness flagging in lookup |
| **Concept-creep with Allure** | Medium | Medium | Strict boundary in §9.1, periodic cross-audit |
| **Brain over-trusts stale recipe** | Medium | High | Staleness threshold (30d default), warning surface in lookup |
| **Selector strategy fails on dynamic UIs** | Medium | Medium | Fallback chain, escalate to Yaroslav on full failure |
| **Recipes leak qa-cortex instance IP** | Low | Medium | Recipes describe selectors + flows, not customer data. Same privacy posture as KB. |
| **Friend's brain tries to import qa-cortex instance recipes** | Low | Low | Recipes per-stack; templates skeleton clean of instance-specific |
| **Playwright promotion produces broken specs** | Medium | Low | Verify step (§7.2 step 4), rollback if fail |
| **Recipe count explodes (1000+)** | Low (year+) | Medium | Indexer designed for this; lookup is O(N) on tags + O(1) on TRD/area maps |

---

## 12. Phased rollout

### Phase A — Manual proof-of-concept (1.5-2 hours)

**Goal:** validate concept on real session within 1 week.

Tasks:
1. Create `flows/` directory + `_index.json` skeleton + `_traps.json` skeleton
2. Hand-write 3 example recipes for most-used flows:
   - `flows/auth/login-aaa.recipe.md`
   - `flows/auth/login-qatestbot.recipe.md`
   - `flows/client-mgmt/open-client-card.recipe.md` (or another high-frequency one)
3. Write `scripts/refresh-flows-index.py` (parses recipe frontmatter, regenerates `_index.json`)
4. Add **Step 3.5 to `start-ticket-test/SKILL.md`** — recipe lookup with explicit Yaroslav approval gate
5. Surface format implementation (per §5.3)
6. Update `templates/flows/` skeleton (empty index, README pointing to design doc)

Validation criteria (1 week of use):
- ≥2 sessions used a recipe (vs full discovery)
- Recipe replay cost ≤1.5K tokens
- 0 false-positive selector matches (recipe didn't lead brain astray)
- Yaroslav qualitative: «легче / быстрее / понятно как использовать»

**If validated → Phase B. If not → analyze why, iterate or shelve.**

### Phase B — Auto-distill mechanism (2-3 hours, after Phase A)

Tasks:
1. Add **Step 7.7 to `start-ticket-test/SKILL.md`** — distill recipe at end of Phase 3
2. Implement distillation prompt template (§6.3)
3. Auto-update `_index.json` on new recipe creation
4. Add anti-pattern to CLAUDE.md: «If you discovered a UI flow without finding existing recipe → MUST distill at Phase 3 close»
5. Recipe linting script (`scripts/lint-recipes.py`) — checks frontmatter completeness, selector strategy presence

Validation:
- 5+ recipes auto-created in 2 weeks of organic use
- Linter pass rate ≥95%
- Replay-after-distillation succeeds without manual edit

### Phase C — Playwright promotion (3-4 hours, after Phase B mature)

Tasks:
1. Create `flows/playwright/` skeleton with `package.json`, `playwright.config.ts`, basic shared fixtures
2. Add `scripts/promote-to-playwright.sh` (orchestrates qa-orchestra:automation-writer → save → verify)
3. Add Yaroslav-facing command: `«promote <flow_id>»` triggers promotion flow
4. Recipe gets `playwright_spec` field populated post-promotion
5. Lookup logic prefers Tier 3 over Tier 2 when available

Validation:
- 3+ recipes promoted to Tier 3
- Playwright execution faster than recipe replay (wall-clock + tokens)
- Overnight regression run (Yaroslav launches before sleep, gets report in morning)

### Phase D (later, optional) — Periodic refresh

- Cron job that picks 5 oldest recipes, replays them on release-ca env, updates `last_verified`
- Configured in `.claude-plugin` hooks or external cron
- Gated on Phase C maturity

---

## 13. Open questions

1. **Storage of binary artifacts during recipe replay?** When recipe step says "screenshot for visual evidence" — where does the screenshot live? Suggestion: `qa-output/replays/<session>/<step>.png`, ephemeral, not committed.

2. **Recipe versioning when UI changes major version?** qa-cortex instance v3.0 → v4.0 hypothetical: recipes become invalid. Strategy: tag recipe with `compatible_versions: [3.x]`, on v4.0 detection → mark all 3.x recipes as needing refresh.

3. **Recipe inheritance / composition?** A flow «test brand variables» implicitly does login first. Should recipe explicitly chain `login.aaa` as prerequisite (composition), or assume login already happened (precondition)? Proposal: explicit `requires: [auth.login.aaa]` field, recipe runner chains them.

4. **Cross-env templating depth?** A recipe for stage with `https://stage.your-product.com/login` — how to make it work on release-ca? Via env var substitution. But what about role-specific flows that exist only on certain envs? Proposal: `env: [stage, release]` whitelist + skip on unsupported.

5. **Concurrency / locking?** If two parallel sessions try to update same recipe (rare but possible) — last-writer-wins acceptable? Or proper file lock? Proposal: just last-writer-wins; recipes are descriptors not state.

6. **Telemetry — track which recipes get used?** Brain logs `journal.sh log "Used recipe auth.login.aaa (replay 7→8)"` on each use. Provides data for promotion decisions and dead-recipe pruning.

---

## 14. Validation criteria — when do we know it works?

### 14.1 Phase A validation (week 1-2)

- [ ] ≥2 real sessions invoked a recipe via Step 3.5
- [ ] Average replay cost ≤1.5K tokens (measured from session jsonl)
- [ ] 0 incidents where recipe led brain astray (false-positive selectors)
- [ ] Yaroslav qualitative thumbs-up on UX

### 14.2 Phase B validation (week 3-4)

- [ ] ≥5 recipes auto-created from real Phase 3 sessions
- [ ] Auto-created recipes pass linter on first try
- [ ] Replay of auto-created recipe succeeds without manual edit

### 14.3 Phase C validation (week 6-8)

- [ ] ≥3 recipes promoted to Playwright
- [ ] Playwright spec passes initial verify (§7.2 step 4)
- [ ] One overnight regression run produces useful report

### 14.4 Steady-state metrics (week 12+)

- [ ] Repeat rate R ≥ 60% (60% of session flows hit recipe)
- [ ] UI-token cost per session reduced ≥50% vs baseline
- [ ] Recipe count: 15-30 (sweet spot — enough coverage, not bloat)
- [ ] Stale rate (recipes >30 days unverified) ≤20% of total

---

## 15. Migration & rollback

### 15.1 Forward migration

Phase A is purely additive — no existing files modified, only new directory + 1 new step in skill. Zero migration cost.

### 15.2 Rollback strategy

If Phase A fails validation:
- `git revert` the commit that introduced flows/ + Step 3.5
- Recipes themselves: `rm -rf flows/` (no other system depends on them)
- Skill returns to discovery-only behavior

If Phase B fails (auto-distill produces bad recipes):
- Disable auto-distill: revert Step 7.7
- Keep manual recipes from Phase A — they continue working
- Recipes stay opt-in via Step 3.5

If Phase C fails (Playwright promotion broken):
- Recipes remain Tier 2 (replay via brain)
- Delete `flows/playwright/` if generated specs are net-negative
- No impact on Tier 1-2 functionality

Each Phase is independently revertible. Low-risk progression.

---

## 16. Decision points (need Yaroslav input)

Before Phase A implementation:

1. **Approve concept** — Yes / No / Iterate-on-design first
2. **Select 3 starter recipes** — recommend: `auth.login.aaa`, `auth.login-qatestbot`, `client-mgmt.open-client-card`. OR Yaroslav picks 3 most-painful repeating flows.
3. **`flows/` location** — repo root (proposed) OR `knowledge_base/flows/` (puts them under KB umbrella) OR `qa-output/flows/` (treats as session artifact, weird)?
4. **Environment for verification** — initial recipes target `stage` (proposed). Or `release-ca` (no 2FA, easier)?
5. **Allure crosslink mandatory or optional?** — proposed: optional. Forcing it blocks bug-retest one-offs.
6. **Friend's brain receives recipes mechanism in Phase A or later?** — proposed: skeleton-only in templates/, full templating later.

---

## 17. Summary — why approve this

- Highest token-ROI initiative in the project (~68% UI-token reduction)
- Self-bootstrapping (no parallel "write recipes" project)
- Self-healing (drift detection + auto-recovery)
- Bidirectional integration with existing infra (Allure, qa-orchestra:automation-writer)
- Phased + revertible (Phase A is 1.5h with zero risk to existing system)
- Portable to friend's stack (templates path)

**Decision asked:** approve Phase A implementation, OR request design changes, OR shelve.

---

## 18. Glossary

- **Discovery** — Tier 1, brain figures out flow from scratch via exploration
- **Recipe** — Tier 2, cached YAML+Markdown describing verified flow path
- **Promotion** — moving recipe from Tier 2 → Tier 3 (Playwright)
- **Distillation** — auto-process of creating recipe from session's actions
- **Selector strategy** — priority chain of ways to identify a DOM element
- **Trap** — known UI/flow gotcha (e.g. 2FA lockout), tracked in `_traps.json`
- **Stale** — recipe not verified in N+ days, demoted in lookup priority
- **Tier** — level in amortization ladder (1=Discovery, 2=Recipe, 3=Playwright)
