# Design Doc — Product Map & KB Knowledge Graph v1.0

> **Status:** PROPOSAL · awaiting Yaroslav approval before implementation
> **Author:** qa-cortex brain (with Yaroslav)
> **Created:** 2026-05-06
> **Target tag:** v0.7.0 (after Phase A validation)
> **Related:** `flow_cache_v1.md` (recipes are one data source for this map)
> **Reading time:** ~18 min

---

## TL;DR

KB artifacts (`ui_flows.md`, `business_rules.md`, `glossary.md`, `db_naming_map.md`, `insights.md`, `bugs.json`, `flows/`, Allure index) currently live as **isolated files**. Brain reads them ad-hoc per task.

**Proposal:** introduce `knowledge_base/product_map.json` — auto-generated **module-organized index** that aggregates references to all KB sources, organized by product module (auth, client-mgmt, brand, trading, finance, kyc, etc.).

When brain encounters a TRD touching module X, it loads **one map node** instead of guessing which 3 KB files to read. The node lists: relevant UI flows, DB tables, recipes, business rules, glossary terms, recent bugs cluster, Allure coverage, insights — all with file paths + section refs.

**Recipes from `flow_cache_v1` become primary nodes in this map** (one of the data sources, alongside others). Path A (recipe kb_refs frontmatter) is subsumed by Path B (this design) — recipes auto-classify to modules, map auto-resolves cross-references.

**Expected savings:** ~10-25K tokens per session start (less than flow cache, but stacks). Plus qualitative: brain sees the **product landscape**, not isolated facts.

**Risk:** medium — module taxonomy drift, crawler complexity, classification accuracy.

**Phased rollout:** Phase A (write crawler for 2 simple sources + define schema) → B (extend to all KB sources) → C (skill integration) → D (recipe cross-link).

---

## 1. Problem statement

### 1.1 Current KB topology — isolated files

```
knowledge_base/
├── qa_persona.md              ← persona / behavior rules
├── orchestrator_persona.md    ← persona / day mgmt
├── qa_workflow.md             ← process
├── insights.md                ← 18+ accumulated lessons (TOPIC-mixed)
├── business_rules.md          ← domain rules (2FA, hierarchy, exports — TOPIC-mixed)
├── glossary.md                ← terminology (FLAT list)
├── db_naming_map.md           ← UI ↔ DB tables (TABLE-organized but no module grouping)
├── db_diff__stage_vs_release.md
├── db_schema__stage.md        ← huge, grep-only
├── db_schema__release.md      ← huge, grep-only
├── ui_flows.md                ← verified UI nav (Role/Desk/Agent only — partial coverage)
├── youtrack_bug_fields.md
├── youtrack_qa_subtask_template.md
├── qa_brain_master_plan.md    ← strategic
├── design_docs/
│   ├── flow_cache_v1.md
│   └── product_map_v1.md      ← THIS FILE
├── bugs.json                  ← 3.6MB index (JSON)
└── (others)
```

**Current brain pattern (per CLAUDE.md):**
> Conditional read rules (not all-at-once):
> - `insights.md` only if ticket area matches accumulated topics (email/2FA/KYC/etc keyword)
> - `business_rules.md` only if 2FA/export/hierarchy/role keywords
> - `db_naming_map.md` only if data layer relevant
> - ...

This is **brittle keyword matching**. Brain has to *guess* which file matches AC, often misses or over-loads.

### 1.2 What's missing

A query like «what does brain know about Brand management module?» requires:
- grep `ui_flows.md` for "brand"
- grep `business_rules.md` for "brand"
- grep `glossary.md` for "brand"
- grep `db_naming_map.md` for "brand"
- grep `insights.md` for "brand"
- python `bugs.json` for tag/keyword "brand"
- check `flows/` for `brand/*.recipe.md`
- query Allure MCP for cases tagged Brand

= **8 separate searches**. Each returns scattered hits. No coherent landscape.

### 1.3 Why this is the next strategic move

- **Flow cache (v0.6 path)** addressed *executable memory* (cached UI paths)
- **Product Map (this v0.7 path)** addresses *semantic memory* (product landscape)
- Both are forms of brain memory amortization — flows cache execution, map caches the **knowing-what-exists**

The two together: when <TICKET>-X touches "client-mgmt module":
1. Map says: «here's everything I know about client-mgmt — UI flows in §3, business rule «client visibility per role», DB table `users`, glossary terms «Client/Account/Entity», 5 recipes, 12 recent bugs»
2. Recipe lookup: «of those 5 recipes, 2 fit AC — open-client-card + attach-employee»
3. Brain has full context with **2 reads** instead of **8+ greps**

---

## 2. Goals & non-goals

### 2.1 Goals

1. **One module = one place to find everything** — brain queries `product_map.json` for module X, gets unified reference list
2. **Auto-generated** — no hand-maintained mega-index. Crawler regenerates from sources.
3. **Cheap to load** — single JSON file, ~5-15KB per module slice, much smaller than full KB read
4. **Self-healing** — when KB files change, regenerate detects drift
5. **Recipe integration** — recipes auto-link to module via `area` field (already exists)
6. **Portable** — friend's brain on different stack gets same crawler infrastructure, populates from his KB

### 2.2 Non-goals

1. **Replace KB files** — files remain source of truth. Map is index pointing to them, not content.
2. **Full graph DB / RDF / SPARQL** — overkill. JSON tree suffices for current scale.
3. **Embedding-based search / RAG** — out of scope. Lexical / structural matching is enough.
4. **Wiki / Confluence integration** — KB stays in repo. No external doc system.
5. **Real-time / live updates** — regeneration is on-demand (manual trigger or git hook).
6. **Cross-module reasoning automation** — map provides facts; brain reasons over them.

---

## 3. Architecture overview

### 3.1 Three layers

```
┌─────────────────────────────────────────────────────────────────────┐
│                    LAYER 1: SOURCE FILES (truth)                    │
│  knowledge_base/*.md, flows/*.recipe.md, bugs.json, Allure MCP      │
│  Hand-curated or auto-generated by domain-specific scripts          │
└─────────────────────────────────────────────────────────────────────┘
                            │
                            │ (crawler script reads + classifies)
                            ▼
┌─────────────────────────────────────────────────────────────────────┐
│                  LAYER 2: PRODUCT MAP (index)                       │
│  knowledge_base/product_map.json                                    │
│  Auto-regenerated. Module → references-to-source-files+sections     │
│  Brain queries this for landscape view                              │
└─────────────────────────────────────────────────────────────────────┘
                            │
                            │ (brain reads module slice, then targeted source files)
                            ▼
┌─────────────────────────────────────────────────────────────────────┐
│                  LAYER 3: BRAIN CONSUMPTION                         │
│  Step 3 of start-ticket-test: load product_map node for ticket area │
│  Surface to Yaroslav: "module X has 5 recipes, 3 business rules..." │
│  Targeted KB reads only for sections explicitly listed in node      │
└─────────────────────────────────────────────────────────────────────┘
```

### 3.2 Module taxonomy

Initial fixed list, can evolve:

| Module | Description | Primary UI area |
|---|---|---|
| `auth` | Login, 2FA, password reset, session | Login page, profile menu |
| `client-mgmt` | Client cards, accounts, entities, attach-employee | Operations → Clients |
| `brand` | Brand switching, brand variables, multi-brand config | System Settings → Brands |
| `trading` | Trade creation, position mgmt, order book, instruments | Trading desk |
| `finance` | Funds, transactions, swap-profiles, deposits/withdrawals | Finance desk |
| `kyc` | KYC review, document upload, compliance flags | KYC desk |
| `analytics` | Reports, dashboards, exports | Reports / Analytics |
| `comms` | Email templates, send-email, notifications, Slack | Communications |
| `roles-perms` | Role mgmt, Desk/Agent, attach-employee, permissions | System Settings → Roles |
| `settings` | System settings, configuration, integrations | System Settings |
| `infra` | Infrastructure-level (sessions, performance, DB) | N/A |
| `misc` | Anything that doesn't fit (catch-all) | — |

**Source of taxonomy:**
- your product real module structure (per CONTEXT.md modules list)
- Aligned with `flows/<area>/` directory names (so recipes auto-classify)
- Hand-edit `knowledge_base/_module_taxonomy.json` to evolve

### 3.3 Source-to-classification mapping

Each KB source has a parsing strategy that yields classified entries:

| Source | Parse strategy | Classification method |
|---|---|---|
| `flows/_index.json` | Already structured | `recipe.area` = module direct |
| `flows/<area>/*.recipe.md` | Frontmatter parse | `area` field |
| `bugs.json` | JSON walk | Tag-based: `subsystem` / Allure tag → module map |
| `business_rules.md` | Heading parse + section content | Explicit `module:` markers (need to add) OR keyword heuristic |
| `ui_flows.md` | Heading parse (## Role, ## Desk) | Section title → module map (e.g. "Client navigation" → client-mgmt) |
| `glossary.md` | Table parse | Each term → module via tags (need to add `module:` column to glossary table) |
| `db_naming_map.md` | Table parse | Term → module via mapping (need taxonomy: `users` table → client-mgmt + auth) |
| `insights.md` | Numbered insight extraction | Each insight → module via tags or content keywords |
| `db_diff__stage_vs_release.md` | Heading parse | Each diff entry → module via table-name → module map |
| Allure cases | MCP query (`find_test_cases_by_issue`) | Allure tags → module |

**Non-classified entries** → bucket `misc` + audit log for manual triage.

---

## 4. Product Map JSON schema

### 4.1 Top-level structure

```json
{
  "version": "1.0",
  "generated_at": "2026-05-06T22:30:00Z",
  "source_files_hash": {
    "knowledge_base/business_rules.md": "sha256:abc...",
    "knowledge_base/ui_flows.md": "sha256:def...",
    "flows/_index.json": "sha256:ghi...",
    "...": "..."
  },
  "module_count": 12,
  "modules": {
    "client-mgmt": {
      "name": "Client Management",
      "description": "Client cards, accounts, entities, attach-employee, bulk actions",
      "ui_surfaces": [...],
      "db_tables": [...],
      "recipes": [...],
      "business_rules": [...],
      "glossary_terms": [...],
      "insights": [...],
      "recent_bugs": [...],
      "allure_coverage": {...},
      "ui_flows_sections": [...],
      "schema_drift_notes": [...]
    },
    "auth": { ... },
    "brand": { ... },
    ...
  },
  "unclassified": [
    {"source": "knowledge_base/insights.md", "ref": "Insight 5", "reason": "no module tag, keywords ambiguous"}
  ]
}
```

### 4.2 Per-module structure (full)

```json
{
  "name": "Client Management",
  "description": "Client cards, accounts, entities, attach-employee, bulk actions, customer search",

  "ui_surfaces": [
    {
      "label": "Operations → Clients",
      "url_pattern": "/app/clients",
      "source": "knowledge_base/ui_flows.md#§3",
      "verified_at": "2026-05-06"
    },
    {
      "label": "Client Card",
      "url_pattern": "/app/clients/<ID>",
      "source": "flows/client-mgmt/open-client-card.recipe.md"
    }
  ],

  "db_tables": [
    {
      "table": "users",
      "ui_term": "Client / Customer",
      "source": "knowledge_base/db_naming_map.md",
      "notes": "soft-deleted via deleted_at; tenancy via tenant_id"
    },
    {
      "table": "client_accounts",
      "ui_term": "Account",
      "source": "knowledge_base/db_naming_map.md"
    }
  ],

  "recipes": [
    {
      "flow_id": "client-mgmt.open-client-card",
      "path": "flows/client-mgmt/open-client-card.recipe.md",
      "status": "skeleton",
      "verification_count": 0,
      "tags": ["smoke", "navigation", "foundational"]
    }
  ],

  "business_rules": [
    {
      "title": "Client visibility per role",
      "source": "knowledge_base/business_rules.md#§3",
      "summary": "Agent role only sees clients assigned via attach-employee. AAA sees all."
    }
  ],

  "glossary_terms": [
    {"term": "Client", "definition": "Customer entity in CRM (UI label)", "db_term": "users", "source": "knowledge_base/glossary.md"},
    {"term": "Account", "definition": "Trading account belonging to client", "db_term": "client_accounts", "source": "knowledge_base/glossary.md"},
    {"term": "Entity", "definition": "Synonym for Client in some legacy contexts", "source": "knowledge_base/glossary.md"}
  ],

  "insights": [
    {"id": 12, "title": "Email Builder counter (recipient count display)", "source": "knowledge_base/insights.md#Insight-12"},
    {"id": 8, "title": "Bulk action selection across pages", "source": "knowledge_base/insights.md#Insight-8"}
  ],

  "recent_bugs": {
    "open_count": 5,
    "recent_examples": [
      {"id": "<TICKET>-13812", "title": "Brand variables not updating in template", "status": "Open"},
      {"id": "<TICKET>-12153", "title": "Bulk emails not sending to multi-brand selection", "status": "Done"}
    ],
    "source": "bugs.json query by tag 'client-mgmt'"
  },

  "allure_coverage": {
    "case_count": 47,
    "launch_id_recent": 31288,
    "pass_rate_recent": "92%",
    "source": "Allure MCP query"
  },

  "ui_flows_sections": [
    {"section": "§3 Client navigation", "source": "knowledge_base/ui_flows.md", "covers": "List → Search → Open card"},
    {"section": "§5 Bulk actions", "source": "knowledge_base/ui_flows.md", "covers": "Multi-select → Apply action"}
  ],

  "schema_drift_notes": [
    {"note": "stage adds users.preferred_locale, release doesn't yet (rollout <TICKET>-XXXXX)", "source": "knowledge_base/db_diff__stage_vs_release.md"}
  ]
}
```

### 4.3 Brain consumption pattern

Instead of:

```
# Old: brain guesses what to read
Read knowledge_base/insights.md   # 5K tokens — much irrelevant
Read knowledge_base/business_rules.md  # 1K tokens — partial relevance
grep bugs.json for 'client'  # noisy hits
Read knowledge_base/db_naming_map.md  # 2K tokens — mostly irrelevant
```

Brain does:

```
# New: load module slice, then targeted reads
Read knowledge_base/product_map.json with jq filter on .modules['client-mgmt']
  → 1-2K tokens, high signal
Then targeted: Read insights.md only Insight 12 + 8 (with offset/limit) → 0.5K
Then targeted: Read business_rules.md only §3 → 0.5K
Total: ~3K tokens vs ~10K, plus better signal
```

---

## 5. Crawler / refresh script

### 5.1 Architecture

`scripts/refresh-product-map.py` — single Python script, parses all sources, writes `knowledge_base/product_map.json`.

```
┌──────────────────────────────────────────────────┐
│ Per source (async-capable):                      │
│   parse_flows_index() → {area: [recipes]}        │
│   parse_bugs_json() → {tag: [bugs]}              │
│   parse_business_rules() → {section: text}       │
│   parse_ui_flows() → {section: text}             │
│   parse_glossary() → [{term, defn, ...}]         │
│   parse_db_naming() → [{table, ui_term, ...}]    │
│   parse_insights() → [{id, title, tags}]         │
│   parse_db_diff() → [{drift_note, table}]        │
│   query_allure() → {tags: stats}                 │
└──────────────────────────────────────────────────┘
                       │
                       ▼
┌──────────────────────────────────────────────────┐
│ classify_to_module(entry) → module_id            │
│   Strategy 1: explicit `module:` field           │
│   Strategy 2: tag → module map                   │
│   Strategy 3: keyword heuristic                  │
│   Strategy 4: fallback to 'misc' + audit log     │
└──────────────────────────────────────────────────┘
                       │
                       ▼
┌──────────────────────────────────────────────────┐
│ Aggregate per-module structure                   │
│ Compute source file hashes for invalidation      │
│ Write knowledge_base/product_map.json            │
│ Write knowledge_base/product_map_unclassified.md │
│   (audit log — humans triage)                    │
└──────────────────────────────────────────────────┘
```

### 5.2 Module classification taxonomy

`knowledge_base/_module_taxonomy.json` — hand-curated mapping config:

```json
{
  "version": "1.0",
  "modules": {
    "auth": {
      "keywords": ["login", "logout", "2fa", "password", "reset", "session", "token", "auth"],
      "ui_areas": ["Login page", "Profile menu"],
      "db_tables": ["users", "sessions", "auth_tokens"],
      "synonyms": ["authentication", "sign-in", "signin"]
    },
    "client-mgmt": {
      "keywords": ["client", "customer", "account", "entity", "attach-employee", "bulk-action"],
      "ui_areas": ["Operations → Clients", "Operations → Accounts"],
      "db_tables": ["users", "client_accounts", "client_entities"],
      "synonyms": ["clients", "customers"]
    },
    "brand": {
      "keywords": ["brand", "brand-vars", "brand_id", "white-label", "tenancy"],
      "ui_areas": ["System Settings → Brands"],
      "db_tables": ["brands", "brand_settings"],
      "synonyms": ["branding"]
    },
    ...
  },
  "default_module": "misc",
  "ambiguity_rules": [
    {"description": "users table referenced in auth context → auth, in client context → client-mgmt", "decision": "use surrounding context"}
  ]
}
```

### 5.3 Classification algorithm

For each KB entry (insight, rule, glossary term, bug, etc.):

```python
def classify(entry, taxonomy):
    text = f"{entry.title} {entry.tags} {entry.body[:500]}".lower()

    # Strategy 1: explicit module: field in source (highest priority)
    if entry.has_explicit_module():
        return entry.explicit_module

    # Strategy 2: scored keyword match across all modules
    scores = {}
    for module_id, module_def in taxonomy["modules"].items():
        score = 0
        for kw in module_def["keywords"] + module_def.get("synonyms", []):
            if kw in text:
                score += 1
        scores[module_id] = score

    best = max(scores, key=scores.get)
    if scores[best] >= 2:  # threshold for confidence
        return best

    # Strategy 3: log ambiguity, default to misc
    log_unclassified(entry, scores)
    return "misc"
```

### 5.4 Source file hash invalidation

Each crawler run computes SHA256 of source files. If hash matches previous map → skip regeneration (fast path). If any hash changes → full rebuild.

Stored in `product_map.json.source_files_hash`. Cheap incremental check.

### 5.5 Unclassified audit log

`knowledge_base/product_map_unclassified.md` — auto-generated, lists entries that classifier couldn't confidently assign:

```markdown
# Product Map — Unclassified Entries

> Auto-generated by scripts/refresh-product-map.py
> Last refresh: 2026-05-06T22:30:00Z

These entries fell into `misc` bucket. Triage:
- Add explicit `module:` field to source if obvious
- Add new keyword to taxonomy if pattern emerges
- Accept misc bucket if entry is truly cross-cutting

## Insights
- **Insight 17** "UI navigation anti-hallucination" — bucketed misc. Suggested module: cross-cutting (applies to all UI work). Recommendation: leave misc, or new module `meta`.

## Business rules
- (none)

## Bugs
- <TICKET>-12998 (no clear module tag) — keywords matched none. Triage manually.

## ...
```

---

## 6. Skill integration

### 6.1 Step 3.6 — Product Map module load (NEW, after pre-load batch)

```markdown
## Step 3.6 — Product Map module load (light read)

After pre-load (Step 3) — once we have ticket summary + AC text — infer module:

```python
# Pseudocode
ticket_text = f"{ticket.summary} {' '.join(ticket.ac)}"
inferred_module = classify(ticket_text, _module_taxonomy)
# OR: if ticket has a Subsystem field — use that directly

# Load module slice
map = read_json("knowledge_base/product_map.json")
node = map["modules"].get(inferred_module)
```

Surface to Yaroslav:

```
🗺  Product Map — module: <client-mgmt>

   UI surfaces:    Operations → Clients (verified §3 in ui_flows.md)
   DB tables:      users, client_accounts (per db_naming_map.md)
   Glossary:       Client (= users), Account (= client_accounts), Entity (legacy)
   Recipes:        2 active (open-client-card, attach-employee)
   Business rules: §3 visibility per role
   Insights:       12 (Email counter), 8 (bulk selection across pages)
   Recent bugs:    5 open, examples: <TICKET>-13812, <TICKET>-12153
   Allure:         47 cases, 92% pass rate (recent)
   Schema drift:   stage adds users.preferred_locale (rollout <TICKET>-XXXXX)

   Module identification confidence: HIGH (3 keyword matches)
   Confirm or override module? [confirm / override <module> / discover anyway]
```

If module mis-inferred → Yaroslav overrides → re-load.
```

### 6.2 Step 4.5 — Recipe lookup (existing) integrates Product Map

Refactor: instead of loading recipes index separately, recipes are already in `module.recipes`. Step 4.5 just filters those to relevant subset.

### 6.3 CLAUDE.md change — replace conditional KB reads

OLD:
```
- `insights.md` only if ticket area might match accumulated insights (email/2FA/KYC/etc keyword)
- `business_rules.md` only if 2FA/export/hierarchy/role keywords
- ...
```

NEW:
```
- `product_map.json` module slice on every ticket entry (Step 3.6)
- Targeted reads only for sections explicitly listed in module node
```

Net effect: same or fewer tokens, much higher signal, eliminated guesswork.

---

## 7. Connection to Flow Cache (recipes ↔ map)

### 7.1 Recipe schema doesn't need `kb_refs` (Path A subsumed)

Recipes already have `area` field which classifies them to module. Map regenerates and includes recipes per module. No need for redundant `kb_refs` per recipe.

### 7.2 Recipe lookup hits Product Map first

Brain's recipe lookup query becomes:

```python
# Was: search flows/_index.json by tags + TRD
# Now: load module slice, get recipes from there + filter by AC keywords
node = map.modules[inferred_module]
candidates = [r for r in node.recipes if matches_ac(r, ac_keywords)]
```

This is the same operation, but enriched with context.

### 7.3 Recipes feed Product Map updates

When a new recipe is auto-distilled (Phase B of flow_cache_v1):
1. Recipe written to `flows/<area>/<id>.recipe.md`
2. `refresh-flows-index.py` updates `flows/_index.json`
3. `refresh-product-map.py` regenerates (detects flows index hash change)
4. Module node now includes new recipe

Pipeline: **discovery → recipe → flows index → product map** — each layer auto-cascades.

---

## 8. Schema enrichments needed in source files

For Product Map to classify entries reliably, some source files benefit from explicit module tags. Optional but recommended:

### 8.1 Insights

Currently:
```markdown
## Insight 12 — Email Builder counter

**One-line summary**

Short explanation...
```

Recommended:
```markdown
## Insight 12 — Email Builder counter

> module: client-mgmt
> tags: [email, ui-counter, bulk-action]

**One-line summary**

Short explanation...
```

### 8.2 Business rules

Currently:
```markdown
## §3 Client visibility per role

Rule body...
```

Recommended:
```markdown
## §3 Client visibility per role

> module: client-mgmt
> related_db: users, attach_employees

Rule body...
```

### 8.3 Glossary

Currently a flat table. Add `module` column:

```markdown
| Term | Definition | UI/DB notes | Module |
|---|---|---|---|
| Client | Customer in CRM | UI: Clients section, DB: users | client-mgmt |
```

### 8.4 db_naming_map

Currently entity-based. Add module mapping:

```markdown
| UI term | DB table | Module | Notes |
|---|---|---|---|
| Client | users | client-mgmt, auth | Soft-delete via deleted_at |
```

**Migration strategy:** add fields opportunistically when touching sections. Don't bulk-rewrite — let it grow organically. Crawler falls back to keyword heuristic when explicit field missing.

---

## 9. Token economy model

### 9.1 Current cost (status quo, conditional reads)

Per session start (Step 3):
- Read 2-3 conditional KB files: ~10K tokens
- Often 30-50% irrelevant content (file is bigger than just the relevant section)
- Plus grep bugs.json: ~500 tokens
- Plus query Allure: ~200 tokens
- **Total: ~10-15K tokens** for KB context, ~30% high-signal

### 9.2 With Product Map

Per session start (Step 3 + 3.6):
- Read product_map module slice: ~1-2K tokens (full module node)
- Targeted KB reads (only sections explicitly in node): ~2-3K tokens (offset/limit reads)
- bugs.json grep avoided (recent_bugs already in map)
- Allure stats from map (no MCP call needed for overview)
- **Total: ~3-5K tokens**, ~90% high-signal

**Savings: ~7-10K tokens per session start.** Less than flow cache, but compounding.

### 9.3 Combined with flow cache

Combined budget per session:

| Phase | Status quo | With flow cache only | With map only | With both |
|---|---|---|---|---|
| Pre-load (Step 3) | ~6K | ~6K | ~3-5K | ~3-5K |
| KB reads | ~10-15K | ~10-15K | ~3-5K | ~3-5K |
| Phase 3 UI work | ~30K (discovery) | ~1K (recipe) | ~30K | ~1K |
| **Total per typical session** | **~46K** | **~17K (-63%)** | **~36-40K (-15%)** | **~7-11K (-77%)** |

Combined with flow cache (v0.6): **~77% reduction** in average session token cost.

### 9.4 Steady-state monthly

20 sessions/week × 4 weeks = 80 sessions/month.
- Status quo: 80 × 46K = **3.7M tokens/month** ($24)
- With both: 80 × 9K = **720K tokens/month** ($5)
- Savings: **~$19/month + 4-5× faster session completion**

---

## 10. Risks & mitigations

| Risk | Likelihood | Impact | Mitigation |
|---|---|---|---|
| **Module taxonomy outdated** | Medium | Medium | `_module_taxonomy.json` hand-edited, versioned, periodic review |
| **Crawler bugs cause stale map** | Medium | High | Hash-based invalidation, `--check` mode for CI, lint script |
| **Classification accuracy poor** | High initially, low after tuning | Medium | Audit log for unclassified, iterate keyword/synonym lists |
| **Brain over-trusts map, misses unclassified content** | Medium | Medium | Map node always includes link to source files, brain can fall back to direct read |
| **Source files reorganized → all refs break** | Low | High | Hash check forces regeneration; section anchors stable per-file |
| **Performance: crawler slow on large bugs.json** | Low | Low | Bugs.json is 3.6MB — parses in <1s. Allure MCP call is the slowest dep. |
| **Map file becomes huge** | Low | Medium | Currently estimate ~30-50KB for qa-cortex instance. If grows past 200KB → split per-module files |
| **Friend's brain has no taxonomy** | Medium | Low | Template ships skeleton taxonomy; friend customizes per his stack |

---

## 11. Phased rollout

### Phase A — Schema + minimal crawler (3-4 hours)

**Goal:** prove the concept on 2 simplest sources.

Tasks:
1. Define `knowledge_base/_module_taxonomy.json` with 12 modules from §3.2
2. Write `scripts/refresh-product-map.py` skeleton
3. Implement parsers for **2 sources only:**
   - `flows/_index.json` (already structured)
   - `bugs.json` (JSON walk + tag-based classification)
4. Generate `product_map.json` v0.1 — partial module nodes (only recipes + bugs sections)
5. Validate: spot-check 3 modules manually — bugs/recipes correctly classified?
6. Add `--check` mode (CI-friendly)

Validation:
- Generated map has 12 modules, each with bugs + recipes lists
- Manual check: <10% misclassified entries
- Crawler runs in <5s

### Phase B — Extend to all KB sources (4-6 hours)

Tasks:
1. Extend crawler with parsers for:
   - `business_rules.md` (heading-based + module tags if added)
   - `ui_flows.md` (heading-based)
   - `glossary.md` (table parse)
   - `db_naming_map.md` (table parse)
   - `insights.md` (numbered insight extraction)
   - `db_diff__stage_vs_release.md` (heading-based)
   - Allure MCP query (cases per tag → count + pass rate)
2. Write unclassified audit log (`product_map_unclassified.md`)
3. Iterate keyword/synonym lists in taxonomy until <5% unclassified

Validation:
- All 9 source types represented in map
- Unclassified rate <5%
- Per-module nodes contain all expected fields

### Phase C — Skill integration (1-2 hours)

Tasks:
1. Add Step 3.6 to `start-ticket-test/SKILL.md` (Product Map load)
2. Update CLAUDE.md `Where to read what` table — Product Map first
3. Refactor Step 4.5 (recipe lookup) to use Product Map slice
4. Update token economy notes in skill

Validation:
- 1+ real session uses Product Map module slice
- Token budget per session reduced (compare to baseline)
- Yaroslav qualitative thumbs-up

### Phase D — Schema enrichment migration (ongoing, 2-3h)

Tasks:
1. Add `module:` field to existing insights, business_rules sections, glossary table (opportunistic)
2. Improve classification accuracy via taxonomy iteration
3. Periodic `unclassified.md` review + triage

Validation:
- Unclassified rate <2%
- Cross-module ambiguity logged + resolved

### Phase E — Cross-link enrichment (later)

- Recipes get explicit `related_insights`, `related_business_rules` if needed
- Bugs index extended with `module` field at write time
- Two-way navigation: from bug → module → all related artifacts

---

## 12. Validation criteria

### 12.1 Phase A (week 1)

- [ ] `product_map.json` generated with 12 modules
- [ ] Each module has recipes + bugs sections populated
- [ ] Manual spot-check: <10% misclassification
- [ ] Crawler runs in <5s on full repo

### 12.2 Phase B (week 2)

- [ ] All 9 source types represented
- [ ] Unclassified rate <5%
- [ ] Map file size <100KB

### 12.3 Phase C (week 3)

- [ ] 3+ real sessions used Step 3.6
- [ ] Average KB-related tokens reduced ≥50%
- [ ] No false-positive module assignments observed

### 12.4 Steady-state (week 8+)

- [ ] Map regenerated <weekly (low drift)
- [ ] Brain consistently uses module slice, doesn't read full files unprompted
- [ ] Token cost per session reduced ≥40% vs pre-map baseline

---

## 13. Migration & rollback

### 13.1 Forward — purely additive

Phase A doesn't modify existing files (other than skill addition). Map is a new file, taxonomy is a new file. Existing reads still work.

Phase B same (extends crawler).

Phase C modifies skill (Step 3.6 added) + CLAUDE.md (read priority changed). Both reversible.

### 13.2 Rollback

If concept fails:
- Delete `knowledge_base/product_map.json` and `_module_taxonomy.json`
- Delete `scripts/refresh-product-map.py`
- Remove Step 3.6 from skill, restore conditional KB read instructions in CLAUDE.md
- Recipes/flows untouched (independent system)

Each phase independently revertible. Low risk.

---

## 14. Open questions

1. **Module taxonomy versioning** — when modules merge/split, how to handle existing references? Proposal: `taxonomy_version` field, migration scripts on bump.

2. **`misc` module sprawl** — if too many entries fall into misc, is taxonomy too narrow? Suggested threshold: >20% misc → taxonomy review.

3. **Cross-module entries** — Insight 17 (UI nav anti-hallucination) applies to all modules. Should it have multiple module assignments, or stay in `misc`/`meta`? Proposal: allow `modules: ["meta"]` for cross-cutting, surface in all module slices.

4. **Recipe `area` ↔ module — same field?** Proposal: yes, unify. `area` field in recipe = `module` ID. Already aligned in current taxonomy.

5. **Taxonomy seed for friend's brain** — does `templates/_module_taxonomy.json.tmpl` ship pre-populated or empty? Proposal: empty + README pointing to qa-cortex instance example.

6. **Map file split when large** — at what size threshold split into per-module files? Proposal: 200KB total → split. Current estimate well under.

7. **Allure stats freshness** — Allure MCP query is the slowest dep. Cache stats per module with TTL? Proposal: 24h TTL, refreshed on-demand.

8. **Should Product Map be CLAUDE.md-loaded?** — No. Map is lazy-loaded per-task (Step 3.6), not always-loaded. CLAUDE.md just points to it.

---

## 15. Comparison to alternatives

| Approach | Pros | Cons |
|---|---|---|
| **Product Map (this proposal)** | Self-bootstrapping, integrates existing KB, cheap, JSON | Crawler complexity, classification ambiguity |
| Status quo (conditional reads) | Zero effort | Brittle, scales badly |
| Embedding-based RAG (e.g. ChromaDB + OpenAI embeddings) | High recall, semantic | Heavy infrastructure, cost, slow query, not deterministic |
| Wiki / Notion / Confluence | Human-readable, good for stakeholders | Out of brain workflow, manual sync |
| Full graph DB (Neo4j) | Powerful relations | Way overkill, infrastructure |
| Per-module isolated files | Simple | Lose cross-cutting view |

**Why Product Map wins:** simple JSON, cheap reads, integrates flow cache, self-healing via crawler, portable, deterministic.

---

## 16. Decision points (need Yaroslav input)

Before Phase A implementation:

1. **Approve concept?** Yes / No / Iterate-on-design
2. **Module taxonomy** — accept §3.2 list as-is, or modify?
3. **Schema enrichment migration** — opportunistic (Phase D, gradual) or upfront mass-edit?
4. **Allure stats inclusion** — yes/no for Phase A? (slow but high-value)
5. **`area` field rename to `module` in recipes** — for consistency? Or keep `area` as alias?
6. **Friend's portability template** — ship taxonomy seed or empty?

---

## 17. Why approve

- **Highest-impact next move after flow cache.** Flow cache amortizes execution; Product Map amortizes navigation/lookup.
- **Both stack: combined ~77% session token reduction vs status quo.**
- **Self-bootstrapping** — no parallel "write Product Map" project, just crawl what we already have.
- **Self-healing** — crawler regenerates on source change, hash-invalidated.
- **Recipe integration is automatic** — no separate kb_refs schema needed (Path A subsumed).
- **Phased + revertible** — Phase A is 3-4h proof, low risk.
- **Portable** — concept transfers to friend's stack; friend customizes taxonomy.

**Decision asked:** approve Phase A implementation, or request design changes, or shelve.

---

## 18. Glossary

- **Module** — top-level product area (auth, client-mgmt, brand, ...)
- **Taxonomy** — hand-curated module definitions with keywords/synonyms
- **Source file** — KB or other artifact that crawler reads
- **Module node** — JSON object in product_map.json containing all references for one module
- **Classification** — assigning a KB entry to a module
- **Unclassified** — entry that classifier couldn't confidently assign
- **Map slice** — fragment of product_map.json containing one module's node (lazy-load unit)
- **Crawler** — `scripts/refresh-product-map.py`
- **Hash invalidation** — re-running crawler only when source file SHA changed
