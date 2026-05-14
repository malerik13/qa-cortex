# INSTALL — qa-assistant for new computer / new project

> This file walks a NEW user through setting up qa-assistant on their machine for their stack.
> Existing instance owner (original deployer) — skip this file, use HOWTO.md.

---

## Prerequisites

- **macOS or Linux** (Windows via WSL untested)
- **Node 18+** (for Claude Code itself)
- **Python 3.9+** (for MCP servers + scripts)
- **Git**
- **Claude Code installed** — https://claude.com/claude-code
- **Anthropic API access** via Claude Code subscription

---

## Step 1 — Clone repo

```bash
cd ~/Documents
git clone <this-repo-url> my-qa-assistant   # rename folder per company
cd my-qa-assistant
```

If you got this folder via copy/rsync (no git) — that also works. Just `cd` into it.

---

## Step 2 — Run portable bootstrap

```bash
./scripts/install.sh                   # auto-detect PROJECT_ROOT
# or:
./scripts/install.sh /path/to/repo     # explicit
```

`install.sh` is the portable Phase 0 bootstrap — no stack-specific assumptions
(works for Jira/Linear/GitHub/YouTrack stacks). It will:

- Verify prerequisites (`python3` 3.10+, `git`; warns for missing `claude`, `gh`, `psql`)
- Create `.venv` + install Python deps (`requirements.txt` + each `mcp/*/requirements.txt`)
- **Generate `.mcp.json`** from `templates/.mcp.json.template` with this machine's `PROJECT_ROOT` substituted
- Copy `templates/env.template` → `.env` (warns to fill tokens)
- Validate `.claude/settings.json` hook commands use `$CLAUDE_PROJECT_DIR` (no hardcoded paths)
- Set executable bits on `scripts/*.sh` and `.claude/hooks/*.sh`

Idempotent — safe to re-run.

> ⚠ Re-run `install.sh` whenever you move the repo to a different directory —
> `.mcp.json` is regenerated with the new absolute path. Claude Code launches
> MCP servers directly (no shell expansion), so the absolute path inside
> `.mcp.json` is mandatory.

### Optional — Step 2b — Stack-specific extras

If your stack uses the bundled YouTrack/Allure MCPs and qa-orchestra
plugin, there's a separate legacy bootstrap:

```bash
./scripts/setup.sh
```

This one assumes YouTrack + Allure tokens are already in `.env` and will rebuild
the KB index. **Skip this if your stack differs** — Phase 1 will replace it
with fully stack-agnostic equivalents.

---

## Step 3 — Fill credentials

Copy template and fill:

```bash
cp templates/env.template .env
$EDITOR .env
```

Fill credentials for:

- Ticketing system (Jira / Linear / GitHub / YouTrack token)
- Test management (TestRail / Zephyr / Allure / etc. token)
- Database (read-only role recommended — see `qa_persona §11.7` rationale)
- Slack/Teams (optional — if you'll draft messages)
- Anthropic API key (if not auto-provided by Claude Code)

⚠ **NEVER commit `.env`** — gitignored by default.

---

## Step 4 — Customize CLAUDE.md

This is the **always-loaded** master prompt. Tailor it to your stack:

```bash
cp templates/CLAUDE.md.tmpl CLAUDE.md
$EDITOR CLAUDE.md
```

Replace placeholders (search for `{...}`):

- `{COMPANY}` — your project / company name
- `{TICKET_PREFIX}` — your ticket ID prefix (`JIRA`, `ENG`, `PRJ`)
- `{TICKETING_SYSTEM}` — Jira / Linear / GitHub Issues / YouTrack
- `{TEST_MGMT}` — TestRail / Zephyr / Allure / Xray
- `{TICKETING_MCP}`, `{TEST_MGMT_MCP}` — MCP server names you've configured
- `{CHAT_LANG}` — RU / EN
- `{ASSIGNEE_QUERY}` — query string for "what's assigned to me"

Keep CLAUDE.md lean. Per `Insight 16` (CLAUDE.md hygiene): if removing a line doesn't break brain — remove.

Target size: 3-5K tokens (~150-200 lines). Larger = expensive on every chat turn.

---

## Step 5 — Fill stack context

```bash
cp templates/CONTEXT.md.tmpl context/CONTEXT.md
$EDITOR context/CONTEXT.md
```

`context/CONTEXT.md` is auto-loaded by qa-orchestra agents — they need stack details (URLs, modules, conventions). Fill all relevant sections.

---

## Step 6 — Initialize KB skeleton

```bash
mkdir -p knowledge_base knowledge_base/design_docs
cp templates/business_rules.md.tmpl knowledge_base/business_rules.md
cp templates/insights.md.tmpl knowledge_base/insights.md
cp templates/glossary.md.tmpl knowledge_base/glossary.md
cp templates/db_naming_map.md.tmpl knowledge_base/db_naming_map.md
cp templates/_module_taxonomy.json.tmpl knowledge_base/_module_taxonomy.json
```

Open each, replace `{COMPANY}` placeholder + customize for your stack. Brain helps populate over time.

**`_module_taxonomy.json` is critical for Product Map** — define 6-12 modules of your product (e.g. `auth`, `billing`, `users`, `inventory`, ...). Replace `{your-module-N}` placeholders. See the source repo for a working 12-module example.

### Initialize Flow Cache skeleton

```bash
mkdir -p flows/playwright
cp templates/flows/_index.json.tmpl flows/_index.json
cp templates/flows/_traps.json.tmpl flows/_traps.json
cp templates/flows/README.md flows/README.md
```

Empty start is fine — recipes accumulate organically as you do real QA work. See `knowledge_base/design_docs/flow_cache_v1.md` for the 3-tier architecture (if copied from source repo).

### Initialize Product Map (auto-generated)

```bash
python3 scripts/refresh-product-map.py
```

Generates `knowledge_base/product_map.json` aggregating module references from flows + bugs index (Phase A). Phase B extends to all KB sources. Re-run on demand or via git pre-commit hook.

---

## Step 7 — Initialize journal

```bash
mkdir -p journal
./scripts/journal.sh init
```

Creates `journal/_active.md` (per-session scratchpad) + today's daily file. Daily journal is your standup history.

---

## Step 8 — Configure MCP servers

You need MCP servers connected for brain to interact with your stack. **Prefer adopting community MCPs over building your own** — the approval gate (preview → human-confirm → write) lives in the skill layer (see `skills/bug-report/SKILL.md`), not in the MCP, so you don't need a custom server just for safety.

### Architecture decision: adopt + skill-level gate

`mcp/youtrack/server.py` and `mcp/allure/server.py` in this repo bake the two-step approval into the MCP itself (`approved: true` parameter). That was necessary in 2025 when no good YouTrack/Allure community MCP existed. **For Jira / TestRail / Slack, mature community servers exist** — adopt them as-is, then enforce the gate in your skills (skill drafts → shows preview → asks user → only on "yes" calls the write tool).

This means: **don't fork `mcp/youtrack/server.py`** unless your ticketing system has no community MCP at all.

### Recommended MCPs by stack

#### Jira (ticketing) — `sooperset/mcp-atlassian`

5.1k★, MIT, supports Jira Cloud + Server/DC + OAuth 2.0, also covers Confluence.

```bash
claude mcp add atlassian uvx mcp-atlassian \
  --env JIRA_URL=https://your-org.atlassian.net \
  --env JIRA_USERNAME=you@company.com \
  --env JIRA_API_TOKEN=xxx
```

Key tools: `jira_search` (JQL), `jira_get_issue`, `jira_create_issue`, `jira_update_issue`, `jira_transition_issue`, plus Confluence reads.

⚠ **No built-in approval gate** — `jira_create_issue` submits immediately. Your `bug-report` skill MUST preview the payload, ask "Create in Jira? [yes/edit/cancel]", and only call `jira_create_issue` on explicit yes.

GitHub: https://github.com/sooperset/mcp-atlassian

#### TestRail (test management) — `bun913/mcp-testrail`

Active 2026, npm-distributed, security-audited.

```bash
claude mcp add testrail npx @bun913/mcp-testrail@latest \
  --env TESTRAIL_URL=https://your-org.testrail.io \
  --env TESTRAIL_USERNAME=you@company.com \
  --env TESTRAIL_API_KEY=xxx
```

Key tools: `getCases`, `addCase`, `updateCase`, `addRun`, `updateRun`, `addResultForCase`, sections / suites / plans / milestones, BDD helpers.

⚠ Same approval-gate caveat as Jira. Wrap writes in skills.

⚠ Document your TestRail field schema in `CLAUDE.md` — the MCP passes params raw to TestRail without validation.

GitHub: https://github.com/bun913/mcp-testrail

#### Slack — `korotovsky/slack-mcp-server`

1.6k★, no permission requirements, GovSlack support. The original `modelcontextprotocol/servers/slack` was removed from the official repo — this is the community successor.

```bash
claude mcp add slack npx @korotovsky/slack-mcp-server
# Configure auth per their README
```

GitHub: https://github.com/korotovsky/slack-mcp-server

#### Playwright (browser automation)

Auto-installed via Anthropic. Should already appear in `claude mcp list` as `✓ Connected`.

#### Linear / GitHub Issues / other ticketing

Search for community MCPs first. Linear has `cline/linear-mcp` (community). GitHub has `@modelcontextprotocol/server-github` (official).

### Verify

```bash
claude mcp list
```

All MCPs needed by your stack should show `✓ Connected`.

### Custom MCP — only when no community option exists

If your ticketing/test-mgmt has no off-the-shelf MCP (rare in 2026), use `mcp/youtrack/server.py` as a reference template. Pattern:

- `list_tools` + `call_tool`
- Two-step approval gate for writes (`preview_*` returns payload, `create_*` requires `approved: true`)

Place your custom MCP in `mcp/<name>/server.py`. Wire it up in `.claude-plugin/plugin.json` under `mcpServers`.

---

## Step 9 — First-use sanity check

```bash
# Check plugin status
claude plugin list

# Should show:
#   ❯ qa-orchestra@claude-code-workflows  ✓ enabled
#   ❯ <your-plugin>                        ✓ enabled

# Check MCP servers
claude mcp list

# Should all be ✓ Connected

# Brain stats baseline
python3 scripts/brain-stats.py
```

---

## Step 10 — Open Claude Code, first chat

```bash
claude
```

In the chat, try:

```
> доброе утро
```

Brain should activate orchestrator persona, output morning briefing (empty journal initially — fine).

Then try:

```
> Тестируем JIRA-XXXXX
```

(Or your ticket prefix.) Brain should:
1. Output `🎯 Scope/Model/Effort` block
2. Activate `start-ticket-test` skill
3. Pre-load context via your MCP servers
4. Write `qa-output/intake.md`
5. Stop for review

---

## Maintenance

### Weekly hygiene

- `./scripts/cleanup-mcp-zombies.sh` — kills orphaned MCP server processes (Claude Code leak)
- `python3 scripts/brain-stats.py` — check token budgets
- Trim CLAUDE.md if grew >15K tokens (per Insight 16)

### Plugin updates

```bash
claude plugin update <plugin>@<marketplace>
# Restart Claude Code to apply
```

### qa-orchestra refresh

If qa-orchestra plugin breaks after upstream changes:

```bash
./scripts/qa-orchestra-fix.sh
```

Re-applies manifest patch + sparse-checkout disable.

---

## Troubleshooting

### Plugin shows ✘ failed to load

Run:
```bash
./scripts/qa-orchestra-fix.sh
```

If still failing, check Claude Code logs. Manifest schema may have evolved — file an issue.

### MCP not connecting

```bash
claude mcp list  # see error
```

Common causes:
- Missing env var (`.env` not loaded)
- API token expired
- Network / VPN

### Brain not using new skills/commands

Plugin install caches at install time. After adding new skills:

```bash
claude plugin update <plugin>@<marketplace>
# Then RESTART Claude Code (Cmd+Q + reopen)
```

### Journal not splitting QA / dev

Verify CLAUDE.md operative section has anti-pattern #7 about `dev-log`. If brain still pollutes QA journal — calibration round needed (see qa_persona §10).

---

## Where to get help

- This repo's `HOWTO.md` — daily playbook
- `knowledge_base/qa_persona.md` — engineer mode rules
- `knowledge_base/orchestrator_persona.md` — day-management rules
- `knowledge_base/qa_workflow.md` — 6-phase ticket lifecycle
- `knowledge_base/qa_brain_master_plan.md` — strategic context
- qa-orchestra: https://github.com/Anasss/qa-orchestra
- Claude Code docs: https://docs.claude.com/claude-code
