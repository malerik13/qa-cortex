# Example walkthrough — Jira + TestRail + Confluence + Slack

> Full setup walkthrough on the v1.0 default stack. ~30-60 min including credential setup.

---

## Goal

Get qa-cortex running on Jira + TestRail + Confluence + Slack, then test a real ticket end-to-end.

---

## Pre-flight checklist

- [ ] Atlassian Cloud account with Jira + Confluence (free trial OK)
- [ ] TestRail account (free trial OK)
- [ ] Slack workspace (free OK) + ability to create a Slack app
- [ ] Python 3.10+ + Claude Code installed
- [ ] ~30 min for credential setup, ~10 min for wizard

---

## 1. Atlassian setup

### Create test project in Jira

1. Sign in https://id.atlassian.com → your Atlassian site
2. **Projects → Create project** → "Scrum" template
3. Name: "qa-cortex Test", Key: `QACT`
4. Create at least one ticket in the project (any type)

### Generate API token

1. https://id.atlassian.com/manage-profile/security/api-tokens
2. **Create API token** → label "qa-cortex" → copy (one-time view!)
3. Save somewhere temporarily — you'll paste in wizard

---

## 2. TestRail setup

### Create test project

1. Sign in TestRail → **Administration → Projects → Add Project**
2. Name: "qa-cortex Test"
3. Note the project ID from URL after creation (e.g. `/projects/overview/3`)

### Generate API key

1. **Top-right user menu → My Settings → API Keys**
2. **Add Key** → label "qa-cortex" → copy

### Configure linked-ticket custom field

For `find_cases_by_linked_ticket` to work, TestRail needs a custom field holding the Jira ticket reference.

1. **Administration → Customizations → Case Fields → Add Field**
2. Field type: **String**
3. System Name: `custom_jira_id`
4. Apply to all projects + all templates
5. Save

Add at least one test case with `custom_jira_id = QACT-1` (your test ticket key from step 1).

---

## 3. Slack setup

### Create Slack app

1. https://api.slack.com/apps → **Create New App** → "From scratch"
2. App Name: "qa-cortex" (or anything)
3. Workspace: pick test workspace

### Configure scopes

**OAuth & Permissions → Bot Token Scopes** — add:

```
channels:history    — read public channel history
channels:read       — list public channels
groups:history      — read private channel history (optional)
groups:read         — list private channels (optional)
chat:write          — post messages
reactions:write     — add reactions
users:read          — list users
users:read.email    — find user by email
```

### Install + get token

1. **Install to Workspace** → authorize
2. Copy **Bot User OAuth Token** (`xoxb-...`)

### Invite bot to channel

In Slack, go to a test channel:

```
/invite @qa-cortex
```

Bot only sees channels it's invited to.

---

## 4. qa-cortex install

```bash
git clone https://github.com/malerik13/qa-cortex.git ~/Documents/qa-cortex
cd ~/Documents/qa-cortex

python3 -m venv .venv
source .venv/bin/activate
pip install -e ".[dev]"
pip install atlassian-python-api testrail-api slack-sdk
```

---

## 5. Run setup wizard

```bash
python scripts/setup.py
```

Wizard prompts:

```
1/5 Ticketing system → 1 (jira)
   Jira URL: https://your-org.atlassian.net
   Jira email: you@example.com
   Jira API token: [paste token from step 1]
   Project key prefix: QACT

2/5 Test management → 1 (testrail)
   TestRail URL: https://your-org.testrail.io
   TestRail username: you@example.com
   TestRail API key: [paste key from step 2]
   TestRail project_id: 3
   Custom field: custom_jira_id

3/5 Documentation → 1 (confluence)
   Same Atlassian creds? y
   Confluence URL: [auto-suggested as <jira>/wiki]

4/5 Chat → 1 (slack)
   Slack Bot Token: [paste xoxb-... from step 3]

5/5 Brain → en (or ru)
```

Wizard validates config, writes `qa-cortex.config.toml` + `.env`.

---

## 6. Verify

```bash
python scripts/setup.py --check       # config valid
pytest tests/                          # 78 unit tests pass

# Optional integration test (requires creds set as QA_CORTEX_TEST_*)
# pytest tests/integration/ --run-integration -v
```

---

## 7. First chat

```bash
claude
```

In Claude Code:

```
> Тестируем QACT-1
```

Brain executes:

1. **Loads engineer persona** → `Read knowledge_base/qa_persona.md`
2. **Sets journal mission** → `journal.sh mission "test QACT-1"`
3. **Pre-load batch** (single message, 4 parallel tool calls):
   - `mcp__qa_cortex_ticketing__get_ticket("QACT-1")`
   - `mcp__qa_cortex_ticketing__get_linked_tickets("QACT-1")`
   - `mcp__qa_cortex_ticketing__get_comments("QACT-1")`
   - `mcp__qa_cortex_test_mgmt__find_cases_by_linked_ticket("QACT-1")`
4. **Writes** `qa-output/intake.md` with structured analysis
5. **Phase 1.5** — checks if QA subtask exists (since QACT-1 is User Story type)
6. **Outputs Cockpit summary**:
   ```
   🎯 Cockpit — QACT-1

   §0 Bridge
     Object:   <ticket summary>
     Goal:     full lifecycle test
     Approach: Phase 1 done, awaiting Phase 2
     Risk:     <key risks>
     Status:   Awaiting Phase 2 approval

   §1 AC count: N · Test cases linked: M
   §2 Linked tickets: [graph]
   §3 Past bugs cluster: [N matches in bugs.json]
   §4 PO open questions: [list]
   §5 Phase 1.5: [USE_EXISTING TRD-X | CREATE_NEW | N/A]
   ```
7. **STOPS** — waits for your approval

You review intake, approve Phase 2, brain proceeds to browser validation.

---

## 8. Try filing a bug

```
> Оформи баг: 500 error на edit profile в QACT
```

Brain executes Phase A-E (see `HOWTO.md`):

- **Phase A**: gather facts (env, steps, expected, actual)
- **Phase B**: 1st cohort verbatim ask + severity walk
- **Phase C**: preview via `mcp__qa_cortex_ticketing__create_ticket(approved=False)`
- **Phase D**: you say "yes" → submit with `approved=True`
- **Phase E**: `journal.sh bug QACT-NEW "..." staging "1st-cohort"`

Brain returns new ticket URL.

---

## 9. Verify cleanup (optional)

If you want to clean up test tickets:

1. In Jira UI: Project → ticket → Delete (requires admin)
2. Or set up dedicated `QACT` project that gets wiped periodically

---

## What you should see

After steps 1-7 complete:

✅ `qa-cortex.config.toml` and `.env` (mode 0600) in repo root
✅ `pytest tests/` returns "78 passed"
✅ Brain loads persona, fetches Jira ticket, finds linked TestRail cases, builds Cockpit
✅ Brain stops before Phase 2, asks for approval (Tier 3 gate)
✅ `qa-output/intake.md` exists with structured ticket analysis
✅ `journal/<DATE>.md` has `mission` entry

---

## Troubleshooting

### "Provider 'jira' not found"
Adapter dep missing. Install:
```bash
pip install atlassian-python-api
```

### "ConfigError: Env var ${JIRA_API_TOKEN} not set"
`.env` not loaded. Source it:
```bash
set -a; source .env; set +a
```

### Brain fetches empty `linked_tickets`
Your Jira ticket has no `issuelinks` field populated. Add a link via Jira UI (e.g. "Relates to") and retry.

### `find_cases_by_linked_ticket` returns empty
Custom field name mismatch. Check:
1. TestRail has a case with `custom_jira_id = QACT-1`
2. `qa-cortex.config.toml` has `linked_ticket_field = "custom_jira_id"`

### Slack errors "not_in_channel"
Bot wasn't invited to the channel. In Slack channel:
```
/invite @qa-cortex
```

### Brain auto-creates ticket without approval
**This is a serious bug.** File issue. The `approved: bool = False` gate is tested at Protocol level — should never regress.

---

## Next: customize for your product

After getting the default stack working:

1. Edit `knowledge_base/business_rules.md` — your product's domain rules
2. Edit `knowledge_base/_module_taxonomy.json` — your product's modules (auth, billing, users, ...)
3. Edit `knowledge_base/glossary.md` — your terminology
4. As you do real QA work, brain accumulates `flows/<area>/*.recipe.md` files
5. Run `python scripts/refresh-product-map.py` to rebuild module index

This is the customization seam — your stack-specific knowledge layered on top of the universal scaffold.
