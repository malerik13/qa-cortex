# Testing qa-cortex

## Quick run

```bash
# Unit tests (78 tests, ~0.3s)
pytest tests/

# Just one provider
pytest tests/providers/test_jira.py -v

# Integration tests (require real backend creds)
pytest tests/ --run-integration
```

## Test layers

```
tests/
├── providers/         ← unit tests (mocked APIs)
│   ├── test_protocols.py    — Protocol structural integrity
│   ├── test_jira.py         — JiraProvider + canonical conversion
│   ├── test_testrail.py
│   ├── test_confluence.py
│   └── test_slack.py
├── config/
│   └── test_loader.py       — config parsing + env var resolution
└── integration/       ← e2e tests against real backends (opt-in)
    ├── conftest.py    — fixtures + skip markers
    ├── test_jira_e2e.py
    └── test_full_workflow.py — Phase 2 success gate
```

## Integration test setup

Integration tests verify the full pipeline against real services. Required for
Phase 2 validation, optional otherwise.

### 1. Set up test instances

**Jira (free Atlassian Cloud trial):**
1. Sign up at https://www.atlassian.com/software/jira/free
2. Create dedicated project (e.g. "QACT — qa-cortex test")
3. Generate API token: https://id.atlassian.com/manage-profile/security/api-tokens
4. Create at least 1 ticket manually (some tests require existing ticket)

**TestRail (free trial):**
1. Sign up at https://www.gurock.com/testrail/
2. Create dedicated project
3. Generate API key in user settings
4. Configure custom field for linked tickets (e.g. `custom_jira_id`)

**Confluence:** Same Atlassian Cloud account as Jira (single token).

**Slack:** Free workspace + bot app with scopes from `qa_cortex/providers/slack.py` docstring.

### 2. Set environment variables

```bash
# .env (gitignored) or shell export
export QA_CORTEX_TEST_JIRA_URL=https://your-test.atlassian.net
export QA_CORTEX_TEST_JIRA_EMAIL=you@example.com
export QA_CORTEX_TEST_JIRA_TOKEN=ATATT3xFf...
export QA_CORTEX_TEST_JIRA_PROJECT=QACT

export QA_CORTEX_TEST_TR_URL=https://your.testrail.io
export QA_CORTEX_TEST_TR_USER=you@example.com
export QA_CORTEX_TEST_TR_KEY=...
export QA_CORTEX_TEST_TR_PROJECT=1
export QA_CORTEX_TEST_TR_LINKED_FIELD=custom_jira_id

export QA_CORTEX_TEST_CONF_URL=https://your-test.atlassian.net/wiki
export QA_CORTEX_TEST_CONF_EMAIL=you@example.com
export QA_CORTEX_TEST_CONF_TOKEN=ATATT3xFf...

export QA_CORTEX_TEST_SLACK_TOKEN=xoxb-...
export QA_CORTEX_TEST_SLACK_CHANNEL=C001234
```

### 3. Run

```bash
pytest tests/integration/ --run-integration -v
```

Tests skip individually if their credentials are missing — partial setup OK.

## Phase 2 validation gate

`tests/integration/test_full_workflow.py::test_phase_1_full_intake` is the gate.
If it passes against real Jira+TestRail, qa-cortex Phase 2 is validated.

Run:

```bash
pytest tests/integration/test_full_workflow.py --run-integration -v
```

Expected output: ✓ Phase 1 intake complete for `<TICKET-ID>`: ticket info,
linked tickets count, comments count, TestRail cases count.

## CI configuration (when public)

Public release will add `.github/workflows/test.yml`:

```yaml
on: [push, pull_request]
jobs:
  unit:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-python@v5
      - run: pip install -e ".[dev]"
      - run: pytest tests/  # unit only, no --run-integration
```

Integration tests run separately on schedule with secrets-based credentials.
