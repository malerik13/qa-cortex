# Design Doc — qa-cortex (Public QA Scaffold) v1.0

> **Status:** PROPOSAL · awaiting Yaroslav approval before implementation
> **Author:** [company]-qa-assistant brain (with Yaroslav)
> **Created:** 2026-05-07
> **Related:** flow_cache_v1.md, product_map_v1.md (architecture inherited)
> **Reading time:** ~25 min
> **Decision needed:** approve concept + answer §18 decision points

---

## TL;DR

**qa-cortex** — open-source QA scaffold built around the same architecture as `[company]-qa-assistant`, but stack-agnostic and customizable. Default integrations: Jira + TestRail + Confluence + Slack + Playwright (with flow cache). Anyone can clone, configure for their stack, and have a working autonomous-on-routine + approval-gated-on-critical QA co-engineer in <1 hour.

**Vision:** Yaroslav's `[company]-qa-assistant` is a private *instance* of a *general framework*. Extracting that framework as `qa-cortex` lets:
1. Yaroslav run brain on 2nd computer / другой работе with same architecture, different stack
2. Friend run brain on his Jira+TestRail without custom build
3. Eventually (if public) other QA-engineers worldwide adopt the pattern

**Initial visibility:** PRIVATE on github.com/malerik13/qa-cortex. Public release gated on Phase 4 validation (real install on 2nd computer + friend's stack).

**Scope:** real product, not template-rename. ~20-30 focused sessions, 4-8 weeks calendar time, in parallel with continuing [company]-qa-assistant operationalization.

**Decision asked:** approve concept + answer 6 decision points in §18.

---

## 1. Problem statement

### 1.1 Current state — single private instance

`[company]-qa-assistant` is a working production-grade QA brain at v0.7.1:
- 2-mode persona (engineer + orchestrator)
- 6-phase ticket lifecycle
- Trust tiering (autonomous on routine, gated on critical)
- Flow cache + product map architecture (Phase A in both)
- 5 skills, 2 custom MCPs (YouTrack, Allure)
- Browser token economy patterns
- 4 validated fixes + 6 awaiting validation

**It works. But it works for one stack.**

### 1.2 Three reasons to extract

**Reason 1 — Yaroslav's own multi-context life:**
- 2nd computer (private home) with possibly different stack
- Если перейдёт на другую работу — заберёт architecture, оставит [COMPANY]-specific KB
- Forces clean separation, exposes what's actually generic vs [COMPANY]-isms

**Reason 2 — Friend's Jira/TestRail stack:**
- Already discussed: friend doesn't have YouTrack/Allure
- Currently no clean path: copy [company]-qa, manually swap MCP servers, hope skills don't break
- With qa-cortex: clone, configure, go

**Reason 3 — Open source contribution:**
- Habr articles confirm space is hot (Karpathy x473 surge)
- Convergent design with industry direction
- Could be valuable contribution if architecture is solid
- **But this is bonus, not driver.** Primary drivers: reasons 1+2.

### 1.3 Why now (vs later)

- Architecture is **stable** at v0.7.1 — extracting earlier would mean continuous churn
- Friend will need it eventually — better build cleanly than retrofit
- 2-computer goal is concrete near-term (months, not years)
- Trust tiering provides the **autonomy contract** that's universal — anyone's brain can use it

### 1.4 Why this is BIG (honest scope)

Not «templates rename». Real product engineering:
- Extract generic from specific (architectural surgery)
- Build adapter layer (provider interfaces)
- 3-4 default MCP servers (Jira, TestRail, Confluence — Slack/Playwright already exist)
- Documentation that **anyone** can follow (high bar)
- Setup wizard (otherwise install friction kills adoption)
- License + governance (public commitment)

20-30 sessions over 4-8 weeks, in parallel with [company]-qa-assistant operationalization. Real time investment.

---

## 2. Naming — qa-cortex

### 2.1 Why qa-cortex (chosen)

**«Cortex»** — reference to brain's outer layer where higher-order thinking happens. Matches the «extra brain» framing Yaroslav explicitly invoked. Clear technical metaphor without anthropomorphizing too far.

**Plus:**
- ✅ Available on npm, PyPI, GitHub (verified — checked earlier)
- ✅ Searchable / unique (not collision with «assistant», «copilot», «agent»)
- ✅ Memorable (3 syllables, distinct sound)
- ✅ Engineer-resonant (technical but not corporate)
- ✅ Implies higher-order processing, not passive helper
- ✅ International (works in English, Russian transliteration читается)

### 2.2 What qa-cortex is NOT

- Not «assistant» (passive helper)
- Not «copilot» (GitHub Copilot collision, over-used)
- Not «agent» (over-loaded term in AI space)
- Not «bot» (implies dumber than reality)

### 2.3 Brand identity (provisional)

- **Name:** qa-cortex
- **Tagline:** «Senior QA co-engineer for any stack. Autonomous on routine, gated on critical.»
- **Logo / icon:** TBD (later phase)
- **GitHub:** github.com/malerik13/qa-cortex (initial private)

### 2.4 Naming for related artifacts

- **Plugin name:** `qa-cortex` (in plugin.json)
- **CLI command:** `qa-cortex` или `cortex` (decide later — probably `cortex` shorter)
- **Default config dir:** `qa-cortex/` (when installed elsewhere)

---

## 3. Goals & non-goals

### 3.1 Goals

1. **Anyone-can-install-in-1-hour bar** — clear README, setup wizard, sane defaults
2. **Stack-agnostic core** — provider adapter pattern, not hardcoded MCPs
3. **Default backends supported out of box** — Jira, TestRail, Confluence, Slack, Playwright
4. **Same architecture as [company]-qa-assistant** — trust tiering, flow cache, product map, skills bridges
5. **Easy customization** — clone, edit config, add domain KB, ready
6. **Self-documenting** — design docs included, не «black box»
7. **Reusable for Yaroslav's 2nd computer** — primary validation case

### 3.2 Non-goals

1. **Not multi-tenant SaaS** — это file-on-disk product, не cloud service
2. **Not stack-everything-included** — pick 4-5 default backends, others = community contributions later
3. **Not framework для арбитрного AI agents** — focused QA scope
4. **Not Yaroslav's day job** — it's project alongside [company]-qa-assistant operationalization, не вместо
5. **Not «open source community»** initially — private until validated, public is bonus phase
6. **Not configurable everything** — opinionated defaults > infinite flexibility

### 3.3 Explicit exclusions from v1.0

- Custom MCP server builder UI
- Multi-language support (English только)
- Web UI (CLI + file editing only)
- Authentication / multi-user (single-user assumption)
- CI/CD test infrastructure (manual install verification)
- Visual flow diagram editor
- Recipe marketplace / sharing platform

---

## 4. Target user

### 4.1 Primary persona — Senior QA engineer

```
Name:        Senior QA engineer at SaaS / fintech / e-commerce company
Stack:       Jira + TestRail (or Zephyr) + Confluence + Slack + Playwright
                OR Linear + GitHub + Notion + Slack + Cypress
                (configurable via adapters)
Pain:        - Repetitive QA work (login → navigate → test → file bug → log)
             - LLM tools too generic (don't know product)
             - Building custom AI agent = too time-consuming
             - Existing tools don't have «trust tiering» (paranoid by default
               OR auto-everything no approval)
Mindset:     Engineer-driven, evidence-based, paranoid about prod
Skills:      Technical QA, comfortable with CLI/git/Markdown
Time budget: Will spend 1-2 hours installing IF clear value upfront
             Won't tolerate 1-day setup
```

### 4.2 Secondary persona — Friend (concrete)

Yaroslav's friend on Jira+TestRail+Confluence+Slack stack. Will be primary external validation case for v0.6.0 (Phase 4 of qa-cortex rollout).

### 4.3 NOT-target

- Junior QA / new to LLM tools (too much CLI overhead)
- Manual-only QA without programming (architecture assumes some technical)
- BDD-heavy teams using Cucumber/Gherkin (different mental model — could be later phase)
- Mobile-only QA (Playwright is web-only — for mobile need adapter to Detox/Appium, out of v1.0 scope)

---

## 5. Architecture overview

### 5.1 Three layers (separation of concerns)

```
┌─────────────────────────────────────────────────────────────────────┐
│                LAYER 1: qa-cortex CORE (the scaffold)               │
│                                                                     │
│  - CLAUDE.md (master prompt template with placeholders)             │
│  - knowledge_base/ skeleton + design docs                           │
│  - skills/ (start-ticket-test, bug-report, test-planning,           │
│              daily-journal, kb-refresh) — abstract over providers   │
│  - flows/ structure + recipe schema                                 │
│  - scripts/ (journal.sh, refresh-flows-index.py,                    │
│              refresh-product-map.py, setup.sh)                      │
│  - templates/ (CONTEXT.md.tmpl, business_rules.md.tmpl, ...)        │
│  - persona files (qa_persona, orchestrator_persona, qa_workflow)    │
│  - Trust tiering (codified in CLAUDE.md)                            │
│                                                                     │
│  Owns: WHAT brain does, HOW it reasons, WHEN to gate                │
└─────────────────────────────────────────────────────────────────────┘
                             │
                             │ (skills call provider methods)
                             ▼
┌─────────────────────────────────────────────────────────────────────┐
│                LAYER 2: PROVIDER ADAPTERS                           │
│                                                                     │
│  Abstract interfaces (Python Protocol):                             │
│  - TicketingProvider (get_ticket, search, create, transition, ...)  │
│  - TestManagementProvider (get_case, search, create_case, ...)      │
│  - DocumentationProvider (search_kb, get_page, ...)                 │
│  - ChatProvider (post_message, read_history, ...)                   │
│  - BrowserProvider (already abstracted via Playwright MCP)          │
│                                                                     │
│  Concrete implementations (default ships):                          │
│  - mcp/ticketing/jira.py        (sooperset/mcp-atlassian wrapper)   │
│  - mcp/ticketing/linear.py      (community option)                  │
│  - mcp/ticketing/github.py      (built-in MCP)                      │
│  - mcp/test-mgmt/testrail.py    (bun913/mcp-testrail wrapper)       │
│  - mcp/docs/confluence.py       (sooperset/mcp-atlassian wrapper)   │
│  - mcp/docs/notion.py           (later — community)                 │
│  - mcp/chat/slack.py            (korotovsky/slack-mcp wrapper)      │
│                                                                     │
│  Owns: HOW to talk to specific backend                              │
└─────────────────────────────────────────────────────────────────────┘
                             │
                             │ (config selects which provider)
                             ▼
┌─────────────────────────────────────────────────────────────────────┐
│                LAYER 3: USER INSTANCE (configured fork)             │
│                                                                     │
│  User clones qa-cortex → fills:                                     │
│  - .env (tokens)                                                    │
│  - qa-cortex.config.toml (provider selection + endpoints)           │
│  - knowledge_base/business_rules.md (own product rules)             │
│  - knowledge_base/_module_taxonomy.json (own modules)               │
│  - context/CONTEXT.md (own stack details)                           │
│  - flows/<area>/*.recipe.md (own UI flows — accumulates organically)│
│                                                                     │
│  Brain runs against THEIR stack via configured providers.           │
└─────────────────────────────────────────────────────────────────────┘
```

### 5.2 Configuration file (new — `qa-cortex.config.toml`)

```toml
[providers]
ticketing = "jira"          # or "linear" / "github" / "youtrack"
test_management = "testrail" # or "zephyr" / "allure"
documentation = "confluence" # or "notion" / "github-wiki"
chat = "slack"               # or "teams" / "discord"
browser = "playwright"       # only option for v1.0

[ticketing.jira]
url = "https://your-org.atlassian.net"
email = "${JIRA_EMAIL}"      # from .env
api_token = "${JIRA_API_TOKEN}"
ticket_prefix = "PROJ"       # your project prefix, e.g. "ENG", "PROJ", "QA"

[test_management.testrail]
url = "https://your-org.testrail.io"
username = "${TESTRAIL_USERNAME}"
api_key = "${TESTRAIL_API_KEY}"
project_id = 1               # specify your project

[documentation.confluence]
url = "https://your-org.atlassian.net/wiki"
email = "${CONFLUENCE_EMAIL}"
api_token = "${CONFLUENCE_API_TOKEN}"

[chat.slack]
# (per slack-mcp setup)

[brain]
default_role_for_routine = "tester"  # for autonomous testing
default_role_for_admin = "admin"     # for admin actions when needed
journal_language = "en"              # or "ru" — affects journal entries
chat_language = "en"                 # or "ru" — chat with user

[modules]
# Module taxonomy lives in knowledge_base/_module_taxonomy.json
# This file just enables auto-load
auto_load_product_map = true
```

Config validation script: `scripts/validate-config.py` — checks all required fields, tests connectivity to each provider, writes validated config hash.

### 5.3 What changes vs [company]-qa-assistant

**Skills become provider-agnostic:**

```python
# Before ([company]-qa-assistant skills/start-ticket-test/SKILL.md):
mcp__plugin_[company]-qa-assistant_youtrack__get_ticket(ticket_id="TRD-XXXXX")

# After (qa-cortex skills/start-ticket-test/SKILL.md):
mcp__qa_cortex_ticketing__get_ticket(ticket_id="<TICKET_PREFIX>-XXXXX")
```

The MCP server `qa_cortex_ticketing` dispatches to chosen provider (jira/linear/github/youtrack) based on config. Skill doesn't care which.

**Templates become real templates:**

`{COMPANY}` → `{TICKET_PREFIX}` → `{TICKETING_SYSTEM}` etc. — placeholders that get filled at install time via setup wizard.

**[COMPANY]-specific KB content removed:**

- `knowledge_base/business_rules.md` — empty template, user fills
- `knowledge_base/insights.md` — empty template
- `knowledge_base/ui_flows.md` — empty template
- `knowledge_base/glossary.md` — empty template
- `knowledge_base/_module_taxonomy.json` — generic skeleton (auth + infra + misc + placeholders)
- `flows/` — empty (no [COMPANY] recipes)

**[COMPANY] stays in [company]-qa-assistant:**

- Specific business rules
- Specific UI flows
- Specific module taxonomy (12 modules of CRM)
- Specific recipes
- Specific MCPs (mcp/youtrack/, mcp/allure/)
- Specific KB content

---

## 6. Repo strategy

### 6.1 Decision: Two separate repos (Option A)

```
github.com/malerik13/qa-cortex                    PRIVATE initially → PUBLIC later
   ├── Stack-agnostic scaffold
   ├── Provider adapters (Jira/TestRail/Confluence/Slack)
   ├── Default templates
   └── Setup wizard

github.com/malerik13/[company]-qa-assistant     PRIVATE forever
   ├── Inherits from qa-cortex (manual sync, not git submodule initially)
   ├── [COMPANY]-specific MCPs (YouTrack, Allure)
   ├── [COMPANY] KB content
   ├── [COMPANY] flow recipes
   └── [COMPANY] config + secrets
```

**Sync mechanism:** Manual cherry-pick from qa-cortex → [company]-qa-assistant when generic improvements happen. Initially manual; possibly automated later via shared submodule pattern.

### 6.2 Why not Option B (template + overlay)

Considered: qa-cortex is template, [company] generates from it.

**Rejected because:**
- Adds complexity early (need template engine, overlay merge logic)
- [COMPANY] already has historical commits — rebasing onto template structure = git history surgery
- Can evolve to B later if A pain manifests

### 6.3 Why not Option C (branches)

GitHub doesn't support per-branch privacy. Public master + private branch ≠ secure. Rejected.

### 6.4 Initial setup tasks

```bash
# Create qa-cortex private
gh repo create malerik13/qa-cortex \
  --private \
  --description "Senior QA co-engineer for any stack. Trust-tiered, with flow cache + product map." \
  --license mit

# Initial commit: README + LICENSE + design doc + structure skeleton
# (no code yet — Phase 1 deliverable)
```

Once created, qa-cortex repo becomes the **scaffold source of truth.** [company]-qa-assistant pulls generic improvements via cherry-pick.

---

## 7. Adapter architecture

### 7.1 Provider interface (Python Protocol)

```python
# qa_cortex/providers/base.py

from typing import Protocol, Any
from abc import abstractmethod

class TicketingProvider(Protocol):
    """Abstract ticketing system provider.

    Implementations: jira.py, linear.py, github.py, youtrack.py
    """

    @abstractmethod
    def get_ticket(self, ticket_id: str) -> dict[str, Any]:
        """Fetch ticket by ID. Returns canonical dict with:
        - id, summary, description, status, priority, type
        - acceptance_criteria (list of str if structured, else raw)
        - linked_tickets (list of dicts)
        - labels, assignee, reporter
        - custom_fields (dict — provider-specific stuff)
        """
        ...

    @abstractmethod
    def search_tickets(self, query: str, max_results: int = 50) -> list[dict]:
        """Search tickets by free-text query OR provider-specific syntax (JQL/etc)."""
        ...

    @abstractmethod
    def create_ticket(
        self,
        ticket_type: str,
        summary: str,
        description: str,
        custom_fields: dict | None = None,
        approved: bool = False,
    ) -> dict:
        """Create ticket. Two-step approval gate:
        - approved=False (default): returns preview without creating
        - approved=True: creates and returns new ticket dict
        """
        ...

    @abstractmethod
    def add_comment(self, ticket_id: str, body: str, approved: bool = False) -> dict:
        """Add comment. Two-step approval (same as create_ticket)."""
        ...

    @abstractmethod
    def transition_ticket(
        self, ticket_id: str, new_status: str, approved: bool = False
    ) -> dict:
        """Transition status. Two-step approval."""
        ...

    @abstractmethod
    def get_linked_tickets(self, ticket_id: str) -> list[dict]:
        """Fetch tickets linked to this one (parents, blocks, blocked_by, etc)."""
        ...

    @abstractmethod
    def get_comments(self, ticket_id: str, max_results: int = 50) -> list[dict]:
        """Fetch comments on ticket."""
        ...
```

Similar interfaces for `TestManagementProvider`, `DocumentationProvider`, `ChatProvider`.

### 7.2 Concrete implementations

```python
# qa_cortex/providers/jira.py

from .base import TicketingProvider
from atlassian import Jira  # or whatever community lib

class JiraProvider(TicketingProvider):
    def __init__(self, config: dict):
        self.client = Jira(
            url=config["url"],
            username=config["email"],
            password=config["api_token"]
        )
        self.prefix = config["ticket_prefix"]

    def get_ticket(self, ticket_id: str) -> dict:
        raw = self.client.issue(ticket_id)
        return self._normalize(raw)  # convert Jira-specific schema → canonical

    def create_ticket(self, ticket_type, summary, description, custom_fields=None, approved=False):
        if not approved:
            return {"preview": True, "payload": {...}, "idempotency_check": [...]}

        # actual creation
        result = self.client.create_issue({...})
        return self._normalize(result)

    # ... etc
```

### 7.3 MCP server wrapper

Currently each MCP is its own server (`mcp/youtrack/server.py`). For qa-cortex:

```python
# qa_cortex/mcp/ticketing_server.py
# Single MCP server that dispatches to whatever provider is configured

from mcp.server import Server
from qa_cortex.providers import load_ticketing_provider

provider = load_ticketing_provider()  # reads qa-cortex.config.toml

@server.tool("get_ticket")
def get_ticket(ticket_id: str):
    return provider.get_ticket(ticket_id)

# ... etc
```

This way: skills call `mcp__qa_cortex_ticketing__get_ticket()` and underneath it dispatches to Jira/Linear/GitHub based on config. Skills don't need provider-specific tool names.

### 7.4 Why this architecture matters

**For [company]-qa-assistant** (private instance):
- Currently has hardcoded `mcp/youtrack/server.py`. Would migrate to:
  - Use qa-cortex's `qa_cortex.mcp.ticketing_server` framework
  - Provide `qa_cortex.providers.youtrack.YouTrackProvider` extending base interface
  - Config: `ticketing = "youtrack"` in `qa-cortex.config.toml`
- Benefit: skills become identical between [company] and qa-cortex (sync becomes trivial)

**For friend's instance:**
- Config: `ticketing = "jira"` in `qa-cortex.config.toml`
- No code changes needed
- Skills work the same

---

## 8. Default backends (v1.0 ships)

### 8.1 Ticketing

| Provider | Status | Source | Skills support |
|---|---|---|---|
| **Jira** | ✅ default | `sooperset/mcp-atlassian` (5.1k★, MIT) | Full |
| **Linear** | 🟡 community | `cline/linear-mcp` или own wrapper | Full |
| **GitHub Issues** | 🟡 community | `@modelcontextprotocol/server-github` (official) | Full |
| **YouTrack** | 🔒 via [company] | own MCP — stays in [company]-qa-assistant repo | Full |

v1.0 scope: **Jira out-of-box.** Linear/GitHub adapters as «extras» but tested.

### 8.2 Test Management

| Provider | Status | Source | Skills support |
|---|---|---|---|
| **TestRail** | ✅ default | `bun913/mcp-testrail` | Full |
| **Zephyr** | 🟡 later | community or own | Partial |
| **Xray** | 🟡 later | community | Partial |
| **Allure** | 🔒 via [company] | own MCP — stays in [company] | Full |

v1.0 scope: **TestRail out-of-box.**

### 8.3 Documentation

| Provider | Status | Source | Skills support |
|---|---|---|---|
| **Confluence** | ✅ default | `sooperset/mcp-atlassian` (same as Jira) | Read |
| **Notion** | 🟡 later | community MCP | Read |
| **GitHub Wiki** | 🟡 later | gh CLI wrapper | Read |

v1.0 scope: **Confluence out-of-box.**

### 8.4 Chat

| Provider | Status | Source | Skills support |
|---|---|---|---|
| **Slack** | ✅ default | `korotovsky/slack-mcp-server` (1.6k★) | Full |
| **Teams** | 🟡 later | community | Read |
| **Discord** | 🟡 later | community | Read |

v1.0 scope: **Slack out-of-box.**

### 8.5 Browser (universal)

Playwright MCP — already universal, no provider abstraction needed. Same as [company].

### 8.6 Why these choices

- All have mature community MCP servers (no need to build from scratch)
- Cover ~80% of QA stacks worldwide
- Atlassian ecosystem dominance (Jira+Confluence pair = single MCP via sooperset/mcp-atlassian — leverage)
- Slack dominance for tech teams
- Playwright for browser automation = current best-in-class

---

## 9. License decision

### 9.1 Recommended: **MIT**

**Why MIT:**
- Most permissive
- No friction for adoption
- Compatible with all dependencies (qa-orchestra is MIT, sooperset/mcp-atlassian is MIT, etc.)
- Yaroslav loses no rights (still owns [company]-qa-assistant private fork)
- Standard for QA / dev tools

**Alternatives considered:**

| License | Pros | Cons |
|---|---|---|
| Apache 2.0 | Patent grant clause | Slightly more friction |
| GPL v3 | Forces derivatives open | Friend's use case may not work if his company has policies |
| AGPL | Closes SaaS loophole | Not relevant — qa-cortex is local tool, не SaaS |
| BSL | Time-delayed open source | Complicated, rarely good fit |
| Proprietary | Maximum control | Defeats public release purpose |

**Decision:** MIT. Add LICENSE file at repo root.

### 9.2 Copyright attribution

```
Copyright (c) 2026 Yaroslav Shcherbinsky
Copyright contributions by individual contributors as noted in commits.
Released under MIT License — see LICENSE file.
```

### 9.3 Trademark (qa-cortex name)

For private phase: not a concern.
For public phase: consider whether to file informal trademark declaration in README. Not required for software product names but provides clarity.

---

## 10. Documentation strategy

### 10.1 Documentation hierarchy

```
qa-cortex/
├── README.md                  ← Front door: what is it, who's it for, quick install
├── INSTALL.md                 ← Detailed install steps (extends current [company] version)
├── HOWTO.md                   ← Daily playbook for users
├── CONTRIBUTING.md            ← How to contribute (when public)
├── LICENSE                    ← MIT
├── CHANGELOG.md               ← Version history
├── docs/
│   ├── architecture.md        ← Layer diagram + provider model explanation
│   ├── trust-tiering.md       ← Tier 1/2/3 explanation
│   ├── flow-cache.md          ← Recipe library concept
│   ├── product-map.md         ← KB graph concept
│   ├── adding-providers.md    ← How to add a new backend (community contrib)
│   ├── examples/
│   │   ├── jira-testrail.md   ← Full walkthrough for default stack
│   │   ├── linear-zephyr.md   ← Alternative stack
│   │   └── ...
│   └── design_docs/           ← Architectural decision records
│       ├── flow_cache_v1.md   ← Ported from [company]
│       ├── product_map_v1.md  ← Ported from [company]
│       └── qa_cortex_v1.md    ← This doc
```

### 10.2 README content (front-door priorities)

1. **One-paragraph description** — what is it, why
2. **Animated GIF / screenshot** — show it working (later phase)
3. **Quick install** — 5 commands to working brain
4. **Customize section** — how to point at your stack
5. **Architecture overview** (1 paragraph + link to full)
6. **License + contributing**

### 10.3 Quality bar

For private phase: «good enough that Yaroslav можем install on 2nd computer without notes from previous»

For public phase: «good enough that random Senior QA engineer can install in 1 hour without asking questions»

This is significant gap. Public release requires real DX work.

---

## 11. Sync model (qa-cortex ↔ [company]-qa-assistant)

### 11.1 Initial state — fresh fork

When qa-cortex is first created:
- Files in qa-cortex are **clean version** of [company] files ([COMPANY]-isms removed)
- [company]-qa-assistant **does not yet** depend on qa-cortex — keeps its current code

### 11.2 Migration of [company]-qa-assistant onto qa-cortex foundation

**Phase A** (during qa-cortex Phase 2): build adapter layer in qa-cortex.
**Phase B** (after qa-cortex v0.5): migrate [company] to use qa-cortex framework:
- [company] keeps `mcp/youtrack/` (own MCP server) but it implements `qa_cortex.providers.TicketingProvider` interface
- Skills get rewritten to use generic tool names (`mcp__qa_cortex_ticketing__get_ticket`)
- Trust tiering, flow cache, product map — inherited from qa-cortex (no duplication)

**Phase C** (steady state): [company]-qa-assistant = qa-cortex + [COMPANY] overlay (KB, recipes, providers).

### 11.3 Dependency model — initially manual

```
qa-cortex (source of truth for generic)
   │
   │ (Yaroslav cherry-picks generic commits to [company]-qa-assistant)
   ▼
[company]-qa-assistant (instance with overlays)
```

Manual sync via `git cherry-pick`. Risk: drift. Mitigation: monthly «sync sweep» where qa-cortex changes audit which apply to [company].

### 11.4 Future automation (not v1.0)

Once both are stable:
- Could use `git submodule` (qa-cortex as submodule в [company])
- Could use shared package (qa-cortex publishes to PyPI, [company] pip installs)
- Decide later, not v1.0 burden

---

## 12. Phased rollout

### Phase 0 — Design + decisions (NOW)

**Goal:** align on design before code.

Tasks:
- ✅ Write this design doc (you're reading)
- ⏳ Yaroslav reviews + answers §18 decision points
- ⏳ Approve / iterate / shelve
- ⏳ Naming finalized: qa-cortex
- ⏳ License finalized: MIT
- ⏳ Visibility: private initially

Deliverable: this doc with §18 answered.
Effort: 1-2 sessions.

### Phase 1 — Skeleton (Week 1)

**Goal:** empty private repo with clear structure, no code yet.

Tasks:
1. `gh repo create malerik13/qa-cortex --private --license mit`
2. README.md (concise — what is it, status: «alpha, building»)
3. CHANGELOG.md (start tracking from v0.0.1)
4. LICENSE (MIT)
5. Initial directory structure:
   ```
   qa-cortex/
   ├── .claude-plugin/plugin.json
   ├── CLAUDE.md  (ported from [company] templates/CLAUDE.md.tmpl)
   ├── knowledge_base/
   │   ├── design_docs/
   │   │   ├── qa_cortex_v1.md  (this doc, ported)
   │   │   ├── flow_cache_v1.md (ported)
   │   │   └── product_map_v1.md (ported)
   │   ├── qa_persona.md (cleaned of [COMPANY] refs)
   │   ├── orchestrator_persona.md
   │   ├── qa_workflow.md
   │   ├── _module_taxonomy.json (generic skeleton)
   │   ├── business_rules.md (empty template)
   │   ├── insights.md (empty template)
   │   ├── glossary.md (empty template)
   │   └── ...
   ├── skills/  (5 skills, generic tool names)
   ├── flows/   (empty + README)
   ├── scripts/ (journal.sh, refresh-flows-index.py, etc — all generic)
   ├── templates/
   ├── mcp/     (empty placeholder dirs for ticketing/, test-mgmt/, docs/, chat/)
   ├── tests/   (test infrastructure — pytest)
   ├── docs/
   ├── examples/
   ├── INSTALL.md
   ├── HOWTO.md
   └── CONTRIBUTING.md
   ```
6. Initial CLAUDE.md (ported from [company], [COMPANY]-isms removed)
7. Trust tiering codified (copy-paste from [company] CLAUDE.md, generalize)
8. v0.0.1 tag

Validation:
- Repo exists, clone works
- Structure matches plan
- README is honest («alpha, no working brain yet»)

Effort: 3-4 sessions.

### Phase 2 — Adapter framework + Jira+TestRail (Weeks 2-4)

**Goal:** working brain on default stack (Jira+TestRail+Confluence+Slack+Playwright).

Tasks:
1. Build `qa_cortex/providers/base.py` — abstract Protocol interfaces
2. Build `JiraProvider` wrapping `sooperset/mcp-atlassian`
3. Build `TestRailProvider` wrapping `bun913/mcp-testrail`
4. Build `ConfluenceProvider` (subset of mcp-atlassian)
5. Build `SlackProvider` wrapping `korotovsky/slack-mcp`
6. Build dispatch MCP servers (`qa_cortex/mcp/ticketing_server.py`, etc.)
7. Refactor skills to use abstract tool names
8. Setup wizard: `scripts/setup-qa-cortex.sh` interactive — asks stack, tokens, generates config
9. Config validator: `scripts/validate-config.py`
10. Integration tests (against test instance of Jira)

Validation:
- Full QA flow works на test Jira+TestRail instance
- Setup wizard руководит через 30-минутный install
- Yaroslav может clone+config+run на 2-й машине against test stack

Effort: 8-12 sessions.

### Phase 3 — Documentation + DX (Week 5)

**Goal:** install bar = «random QA can do it in 1 hour without asking questions».

Tasks:
1. README rewrite (полированная версия)
2. INSTALL.md detailed walkthrough
3. HOWTO.md daily playbook
4. docs/architecture.md
5. docs/trust-tiering.md (важная — это уникальное value prop)
6. docs/adding-providers.md (для community)
7. examples/jira-testrail.md complete walkthrough
8. Screenshots of working setup
9. Maybe: 5-min demo video

Validation:
- Yaroslav clones to fresh machine following ТОЛЬКО README — no shortcuts. Works.
- Friend follows README on his stack — works.

Effort: 4-6 sessions.

### Phase 4 — Validation (Week 6-7)

**Goal:** real installs by 2 different people on 2 different stacks.

Tasks:
1. Yaroslav 2nd computer install (его stack — possibly Jira based если на другой работе уже)
2. Friend install on his stack
3. Iterate on friction points found
4. v1.0.0-rc1 tag

Validation:
- 2 successful installs on different stacks
- Both report «brain works for routine QA»
- No critical bugs in 1-week usage

Effort: 2-3 sessions of fix + iteration.

### Phase 5 — Public release (Week 8, optional)

**Goal:** make repo public.

Decision gate: only if Phase 4 succeeded clearly.

Tasks:
1. Final README polish
2. CONTRIBUTING.md polish
3. Issue templates / PR template
4. `gh repo edit --visibility public`
5. v1.0.0 tag
6. Optional: Twitter / Habr / HackerNews announcement

Validation:
- Public, accessible
- Search-able («qa-cortex» findable)
- (Future): community PRs / issues come in

Effort: 1 session.

---

## 13. Token economy / cost model

### 13.1 For Yaroslav (development cost)

20-30 sessions = roughly:
- Average session: 50K tokens (mix of design + code)
- Total: 1-1.5M tokens for development
- At Sonnet 4.7 ~$6.6/M blended: **~$7-10**
- (Negligible — main cost is time, not tokens)

### 13.2 For users (runtime cost — same as [company])

Trust tiering + flow cache + product map combine for ~77% reduction in per-session token cost compared to «no infrastructure» baseline. Per [company] projections: ~$5-10/month for active QA usage.

### 13.3 Maintenance time cost

- Initial Phase 1-3: ~20-30 sessions over 4-6 weeks
- Ongoing maintenance: ~5-10% of Yaroslav's brain-improvement time goes to qa-cortex sync, rest to [company]-specific work
- If public: add ~2-5h/month for issues/PRs (estimation; could be more)

---

## 14. Risks & mitigations

| Risk | Likelihood | Impact | Mitigation |
|---|---|---|---|
| **Two products = double maintenance** | High | High | Discipline: qa-cortex is source of truth for generic, [company] sync via cherry-pick. Monthly audit. |
| **Adapter abstraction is leaky** (provider-specific behavior leaks into skills) | Medium | High | Strong typing (Protocol), integration tests against multiple providers, code review of skills changes |
| **«[COMPANY]-isms» trap** (subtle [COMPANY] assumptions in code) | High initially | Medium | Diff review at extraction time; first install on different stack will surface remaining isms |
| **Friend's setup fails** (validation case) | Medium | Medium | Phase 4 explicit validation step; iterate before release |
| **Public release brings unwanted attention** | Low | Low | Private until Phase 5 decision; can re-private if needed |
| **Naming taken / disputed later** | Low | Medium | Verified availability now; trademark watch later |
| **License incompatibility with deps** | Low | Medium | All key deps verified MIT/Apache compatible |
| **Setup wizard breaks on edge cases** (Windows? non-Atlassian Jira?) | Medium | Medium | Phase 4 validation; docs explicitly state «macOS/Linux, Atlassian Cloud» as primary |
| **Recipe distillation Phase B blocking** | Low | Medium | Recipes work as Tier-2 stub; full distillation can come later |
| **Yaroslav burnout** (this is a lot) | Medium | High | Realistic scope (4-8 weeks), hard limit on session count, parallel with [company] not instead |

---

## 15. Validation criteria

### 15.1 Phase 1 (skeleton) success

- [ ] Repo exists, README clear about «alpha»
- [ ] Structure matches design
- [ ] Yaroslav can clone fresh and see what's there
- [ ] `qa-cortex_v1.md` ported and visible
- [ ] CHANGELOG starts tracking

### 15.2 Phase 2 (adapters) success

- [ ] Provider Protocol classes defined
- [ ] 4 default providers implemented (Jira, TestRail, Confluence, Slack)
- [ ] Skills work end-to-end на test Jira+TestRail
- [ ] Setup wizard runs to completion на fresh install
- [ ] Validate-config script catches missing tokens

### 15.3 Phase 3 (docs) success

- [ ] README quality bar: «I'd install based on this»
- [ ] INSTALL.md: complete, no «figure it out» blanks
- [ ] HOWTO.md: daily playbook clear
- [ ] Architecture doc explains 3 layers
- [ ] At least 1 example walkthrough complete

### 15.4 Phase 4 (validation) success

- [ ] Yaroslav installs on 2nd computer following ONLY published docs
- [ ] Friend installs on his stack
- [ ] Both have working brain within 1 hour
- [ ] No critical issues in 1 week of usage

### 15.5 Phase 5 (public release) success — only if 4 succeeded

- [ ] Repo public
- [ ] No accidental [COMPANY] leakage in commit history (git filter-branch if needed)
- [ ] License valid
- [ ] Issue/PR templates set up

### 15.6 Steady state (3 months after v1.0)

- [ ] Yaroslav using on 2 computers
- [ ] Friend using productively
- [ ] (Optional) 1+ external user
- [ ] qa-cortex / [company] sync drift <1 month
- [ ] Brain has accumulated ≥5 recipes на каждый instance

---

## 16. Open questions

1. **Does [company]-qa-assistant become qa-cortex + overlay or stay independent?**
   - Proposal: migrate after qa-cortex Phase 2 stable
   - Trade-off: clean architecture vs migration disruption

2. **CLI command name: `qa-cortex` or `cortex` or `qac`?**
   - `cortex` is short but ambiguous
   - `qa-cortex` matches package name but verbose
   - Probably: `cortex` for commands, `qa-cortex` for package/repo names

3. **Setup wizard: shell script or Python CLI tool?**
   - Shell: lightweight, no install
   - Python: prompt validation, type safety
   - Probably Python — already required dep

4. **Config format: TOML vs YAML vs JSON?**
   - TOML: clean for nested config, growing in popularity
   - YAML: ubiquitous but indentation traps
   - JSON: machine-friendly but no comments
   - Recommend TOML

5. **Multi-language support for personas?**
   - Currently personas mix English structure + RU phrases
   - Public users may want pure English or other languages
   - Possibly: English-only initially, RU stays in [company]-qa-assistant for now

6. **How опен to «adding providers» community contributions?**
   - Easy adapter pattern → invites contributions
   - But each new provider = test surface burden
   - Recommend: clear `docs/adding-providers.md`, but moderate-pace acceptance

7. **Should qa-cortex include a working demo / sample backend?**
   - Pro: easier to demo/test без real Jira/TestRail
   - Con: maintenance burden (mock backend code)
   - Recommend: skip in v1.0, add later if friction reported

8. **Versioning strategy: semver strict or date-based?**
   - Recommend: SemVer (v0.x → v1.0 → v1.x)
   - v1.0 = first public release
   - v0.x = private, alpha

9. **Should design docs live in qa-cortex repo or separate?**
   - Recommend: in repo (`docs/design_docs/`) — easier discoverability

10. **Should this design doc itself be ported to qa-cortex repo at Phase 1?**
    - Yes — `docs/design_docs/qa_cortex_v1.md`

---

## 17. Comparison to alternatives

| Approach | Pros | Cons |
|---|---|---|
| **qa-cortex (this proposal)** | Real product, full architecture, multi-stack | High effort, maintenance burden |
| Just better docs in [company] | Low effort | Doesn't help friend's stack, doesn't enable 2nd machine flexibility |
| Hand-written templates only | Low effort | No adapter pattern, every install requires custom code edits |
| Use existing tool (DustAI? ChatGPT plugins? other Claude plugins?) | Zero build | None offer this combination of trust tiering + flow cache + product map |
| Build SaaS instead | Network effects, recurring revenue | Out of scope, distracts from primary goals (Yaroslav's QA work) |

**Why qa-cortex wins:** unique architecture (trust tiering + flow cache + product map = nothing else has all three), serves concrete near-term goals (2nd computer + friend), modest effort relative to value, optionality for public release later.

---

## 18. Decision points (need Yaroslav input)

Before Phase 1 implementation:

### D1. Approve concept overall?
- [ ] **Yes — proceed with Phase 1 (skeleton creation)**
- [ ] No — too big, focus on [company] only
- [ ] Iterate — design issues to address first

### D2. Naming: qa-cortex confirmed?
- [ ] **Yes — qa-cortex final**
- [ ] Different name (specify)

### D3. Repo strategy: Option A (separate repos)?
- [ ] **Yes — separate repos, manual sync**
- [ ] Option B (template + overlay) — risk taking on
- [ ] Other (specify)

### D4. License: MIT?
- [ ] **Yes — MIT**
- [ ] Apache 2.0
- [ ] Other (specify)

### D5. Initial visibility: private?
- [ ] **Yes — private until Phase 4 validation, then decide on public**
- [ ] Public from start
- [ ] Private permanently (no public release intent)

### D6. Default backends scope (v1.0 ships):
- [ ] **Jira + TestRail + Confluence + Slack + Playwright (proposal)**
- [ ] Add Linear/GitHub Issues to v1.0
- [ ] Drop Confluence to keep scope tight (Phase 2 quicker)
- [ ] Other (specify)

### D7. Phase 0 next steps after this doc:
- [ ] **Approve doc → start Phase 1 (skeleton creation) immediately**
- [ ] Approve doc → wait, return to [company] operationalization first
- [ ] Iterate doc — issues to address
- [ ] Pause

---

## 19. Why approve this

- **Unique architecture** in QA tooling space (trust tiering + flow cache + product map = no competitor has all three)
- **Concrete near-term value** for Yaroslav (2nd computer) and friend
- **Forces clean architecture** — extracting generic from specific exposes [COMPANY]-isms, improves both products
- **Optional public release** — preserves option without forcing it
- **Phased + revertible** — Phase 1 is purely additive (new private repo), zero risk to [company]
- **Validates universality** of the patterns we've built — best test of architecture is can-it-be-reused

**Decision asked:** approve concept (D1) + answer D2-D7 + start Phase 1.

---

## 20. Glossary

- **qa-cortex** — name of public QA scaffold product
- **[company]-qa-assistant** — Yaroslav's private instance of qa-cortex (or its predecessor, depending on migration phase)
- **Provider** — backend integration (Jira, TestRail, Confluence, Slack, etc.)
- **Provider Protocol** — abstract interface in Python defining provider methods
- **Adapter** — concrete provider implementation (`JiraProvider`, `TestRailProvider`, etc.)
- **Dispatch MCP server** — single MCP that delegates to configured provider
- **Setup wizard** — interactive CLI tool that scaffolds new install (`scripts/setup-qa-cortex.sh` или Python equivalent)
- **Instance** — a configured user copy of qa-cortex (e.g. [company]-qa-assistant is an instance with YouTrack+Allure providers)
- **Overlay** — instance-specific files (KB content, recipes, custom MCPs) layered on qa-cortex base
- **Sync drift** — divergence between qa-cortex и [company]-qa-assistant when commits aren't synced
