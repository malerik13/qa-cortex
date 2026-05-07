# `flows/` directory — Flow Cache & Recipe Library

This directory holds the **brain's executable memory** of UI/API flows that recur across QA sessions. Cached recipes get replayed at ~3% of the cost of fresh discovery (~800 tokens vs ~30K).

**Read first:** `knowledge_base/design_docs/flow_cache_v1.md` (full architecture).

---

## Quick start (for friend / new instance)

1. **Empty start is fine.** No recipes yet → brain works in pure discovery mode (current default).

2. **Recipes accumulate naturally.** As QA sessions repeat, brain offers to cache flows. Approve → recipe saved here.

3. **Three tiers:**
   - **Tier 1 — Discovery** (no recipe yet): full UI exploration, expensive
   - **Tier 2 — Recipe replay** (this directory): cached path, cheap
   - **Tier 3 — Playwright** (`flows/playwright/`): compiled `.spec.ts`, autonomous

4. **Index is auto-generated.** Run `python3 scripts/refresh-flows-index.py` after manual recipe edits.

---

## Directory layout

```
flows/
├── _index.json          ← lookup index (auto-generated, DO NOT hand-edit)
├── _traps.json          ← known UI/flow gotchas (hand-curated registry)
├── auth/                ← login, 2FA, logout, password-reset
├── client-mgmt/         ← create-client, attach-employee, bulk-actions
├── brand/               ← brand switching, brand-vars management
├── trading/             ← trade-creation, position-mgmt, etc.
├── finance/             ← funds, transactions, swap-profiles
├── kyc/                 ← KYC review, document upload
├── analytics/           ← reports, dashboards
├── comms/               ← email-templates, send-email
├── settings/            ← role-mgmt, system settings
├── misc/                ← anything that doesn't fit
└── playwright/          ← Tier 3 compiled scripts (own package.json)
```

---

## Recipe format

Each recipe is `<flow-id>.recipe.md` with YAML frontmatter + Markdown body.

See `knowledge_base/design_docs/flow_cache_v1.md` §4 for full schema.

Frontmatter required fields:
- `flow_id` (canonical)
- `last_verified` (ISO date or `never`)
- `verification_count` (int)
- `env` (list of envs this works on)
- `role` (which user role)
- `tags` (search facets)

---

## When to add a recipe

- Flow used in 2+ sessions → candidate for caching
- Flow has stable UI (not changing weekly) → safe to cache
- Flow is reusable across tickets → recipe pays back

**Don't recipe:**
- One-off bug-retest exploration that won't recur
- Flows with manual judgement step (visual checks)
- Flows requiring 2FA Telegram code (can't automate auth bypass)

---

## Maintenance

- **Drift handling:** brain detects selector drift on replay → auto-falls-back through strategies → updates recipe with new primary if found
- **Staleness:** `last_verified` > 30 days = demoted in lookup. Run replay to refresh.
- **Promotion:** `verification_count >= 5` + Yaroslav approval → invoke `qa-orchestra:automation-writer` → save `.spec.ts` to `playwright/`
- **Cleanup:** retired flows → mark `status: deprecated` in frontmatter, delete after 1 release cycle

---

## For portability (friend's brain on different stack)

This concept transfers to any stack. For Jira+TestRail+Slack adaptation:

1. Replace `allure_case_id` field with `testrail_case_id` (recipe schema is flexible)
2. Replace ScaleFinal-specific env URLs with friend's env URLs in recipes
3. Trap registry (`_traps.json`) starts empty; populate as friend discovers gotchas
4. Starter recipes for friend: probably login flow + 1 navigation flow specific to their product

Friend creates recipes from their own QA sessions — does not import ScaleFinal recipes (different product = different flows).
