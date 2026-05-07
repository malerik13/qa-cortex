# Installation

> **Two paths:** wizard (recommended, ~10 min) or manual (~30 min). Both work.

---

## Prerequisites

- **macOS or Linux** (Windows via WSL — untested)
- **Python 3.10+**
- **Claude Code** — https://claude.ai/code
- **Git**
- Credentials for your stack (see "Stack credentials" below)

---

## Path A — Wizard (recommended)

```bash
git clone https://github.com/malerik13/qa-cortex.git ~/Documents/qa-cortex
cd ~/Documents/qa-cortex

python3 -m venv .venv
source .venv/bin/activate
pip install -e ".[dev]"
pip install atlassian-python-api testrail-api slack-sdk

python scripts/setup.py
```

Wizard asks:
1. Ticketing system (Jira / Linear / GitHub / YouTrack) — pick **jira** for v1.0
2. Jira URL, email, API token, project key
3. Test management (TestRail / skip)
4. Documentation (Confluence / skip — share Atlassian creds with Jira)
5. Chat (Slack / skip)
6. Brain language preferences

Generates `qa-cortex.config.toml` + `.env` (mode 0600). Validates config.

```bash
python scripts/setup.py --check    # validates existing config
claude                              # launches Claude Code with qa-cortex
```

---

## Path B — Manual

### 1. Clone + venv

```bash
git clone https://github.com/malerik13/qa-cortex.git ~/Documents/qa-cortex
cd ~/Documents/qa-cortex

python3 -m venv .venv
source .venv/bin/activate
pip install -e ".[dev]"
```

### 2. Install adapter deps

Install only those you'll use:

```bash
pip install atlassian-python-api      # Jira + Confluence
pip install testrail-api              # TestRail
pip install slack-sdk                 # Slack
```

### 3. Create `.env`

`.env` is **gitignored** — never commit. Mode 0600 recommended.

```bash
cat > .env << 'EOF'
JIRA_EMAIL=you@example.com
JIRA_API_TOKEN=ATATT3xFf...

TESTRAIL_USERNAME=you@example.com
TESTRAIL_API_KEY=...

SLACK_BOT_TOKEN=xoxb-...
EOF
chmod 0600 .env
```

### 4. Create `qa-cortex.config.toml`

See `docs/examples/jira-config.toml` for full example. Edit per your stack.

### 5. Validate + run

```bash
python scripts/setup.py --check       # validates config
pytest tests/                          # 78 unit tests should pass
claude                                 # launch
```

---

## Stack credentials

### Jira (Atlassian Cloud)

1. Sign in at https://id.atlassian.com
2. **Security → API tokens** (https://id.atlassian.com/manage-profile/security/api-tokens)
3. Create token → label "qa-cortex" → copy
4. URL: `https://<your-org>.atlassian.net`
5. Project key: from any ticket ID — e.g. `PROJ` from `PROJ-123`

### TestRail

1. **My Settings → API Keys → Add Key** → label "qa-cortex"
2. URL: `https://<your-org>.testrail.io`
3. Project ID: in URL `/index.php?/projects/overview/<ID>`
4. Linked ticket field: project-specific custom field name

### Confluence

If on Atlassian Cloud, **same credentials as Jira**. URL is `<jira_url>/wiki`.

### Slack

1. https://api.slack.com/apps → **Create New App** → "From scratch"
2. **OAuth & Permissions → Bot Token Scopes** — add:
   - `channels:history`, `channels:read`
   - `groups:history`, `groups:read` (optional)
   - `chat:write`, `reactions:write`
   - `users:read`, `users:read.email`
3. **Install to Workspace** → copy "Bot User OAuth Token" (`xoxb-...`)
4. Invite bot to channels: `/invite @qa-cortex`

---

## Verify install

```bash
python scripts/setup.py --check       # config validation
pytest tests/                          # 78 unit tests
pytest tests/integration/ --run-integration -v   # optional, requires creds
```

---

## First chat

```bash
claude
```

Try `доброе утро` → orchestrator persona, morning briefing.
Then `Тестируем PROJ-XXX` → engineer persona, intake, Cockpit, stops for approval.

---

## Troubleshooting

### `ConfigError: Env var ${X} not set`
Source `.env`: `set -a; source .env; set +a`. Or use `direnv`.

### `Provider 'X' not yet implemented`
v1.0 alpha ships only `jira`, `testrail`, `confluence`, `slack`. Other providers: see `docs/adding-providers.md`.

### MCP server fails to start
- Check `.claude-plugin/plugin.json` paths
- Run server manually: `python -m qa_cortex.servers.ticketing_server`

### Slack bot not seeing channels
Bot must be **invited** to each channel: `/invite @qa-cortex`.

---

## Maintenance

```bash
git pull                              # update qa-cortex
pip install -e ".[dev]"               # if deps changed
pytest tests/                          # verify
python scripts/refresh-flows-index.py
python scripts/refresh-product-map.py
```

---

## Next

- **First QA flow** → `HOWTO.md`
- **Architecture** → `docs/architecture.md`
- **Trust tiers** → `docs/trust-tiering.md`
- **Add new provider** → `docs/adding-providers.md`
