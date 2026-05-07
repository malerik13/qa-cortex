"""Integration test configuration.

Integration tests hit real backends. They're SKIPPED by default (no credentials
in CI). To run locally:

1. Create test instance(s) — Atlassian Cloud free trial, TestRail trial, Slack workspace
2. Set env vars in .env or shell:
   QA_CORTEX_TEST_JIRA_URL=https://your-test-instance.atlassian.net
   QA_CORTEX_TEST_JIRA_EMAIL=...
   QA_CORTEX_TEST_JIRA_TOKEN=...
   QA_CORTEX_TEST_JIRA_PROJECT=QACT  (dedicated test project)
   ...etc for testrail, confluence, slack
3. Run: pytest tests/integration/ -v --run-integration

Default behavior: tests skip if credentials not present. CI never runs them
unless explicitly enabled.
"""

from __future__ import annotations

import os

import pytest


def pytest_addoption(parser):
    parser.addoption(
        "--run-integration",
        action="store_true",
        default=False,
        help="Run integration tests against real backends",
    )


def pytest_collection_modifyitems(config, items):
    if config.getoption("--run-integration"):
        return  # don't skip
    skip_integration = pytest.mark.skip(
        reason="Integration tests skipped (use --run-integration to enable)"
    )
    for item in items:
        if "integration" in item.keywords:
            item.add_marker(skip_integration)


def _have(*var_names: str) -> bool:
    """Check if all env vars are set + non-empty."""
    return all(os.environ.get(v) for v in var_names)


# Skip markers for missing credentials
requires_jira = pytest.mark.skipif(
    not _have(
        "QA_CORTEX_TEST_JIRA_URL",
        "QA_CORTEX_TEST_JIRA_EMAIL",
        "QA_CORTEX_TEST_JIRA_TOKEN",
        "QA_CORTEX_TEST_JIRA_PROJECT",
    ),
    reason="Jira test credentials not set",
)

requires_testrail = pytest.mark.skipif(
    not _have(
        "QA_CORTEX_TEST_TR_URL",
        "QA_CORTEX_TEST_TR_USER",
        "QA_CORTEX_TEST_TR_KEY",
        "QA_CORTEX_TEST_TR_PROJECT",
    ),
    reason="TestRail test credentials not set",
)

requires_confluence = pytest.mark.skipif(
    not _have(
        "QA_CORTEX_TEST_CONF_URL",
        "QA_CORTEX_TEST_CONF_EMAIL",
        "QA_CORTEX_TEST_CONF_TOKEN",
    ),
    reason="Confluence test credentials not set",
)

requires_slack = pytest.mark.skipif(
    not _have(
        "QA_CORTEX_TEST_SLACK_TOKEN",
        "QA_CORTEX_TEST_SLACK_CHANNEL",
    ),
    reason="Slack test credentials not set",
)


@pytest.fixture
def jira_config() -> dict:
    return {
        "url": os.environ["QA_CORTEX_TEST_JIRA_URL"],
        "email": os.environ["QA_CORTEX_TEST_JIRA_EMAIL"],
        "api_token": os.environ["QA_CORTEX_TEST_JIRA_TOKEN"],
        "ticket_prefix": os.environ["QA_CORTEX_TEST_JIRA_PROJECT"],
        "default_project_key": os.environ["QA_CORTEX_TEST_JIRA_PROJECT"],
    }


@pytest.fixture
def testrail_config() -> dict:
    return {
        "url": os.environ["QA_CORTEX_TEST_TR_URL"],
        "username": os.environ["QA_CORTEX_TEST_TR_USER"],
        "api_key": os.environ["QA_CORTEX_TEST_TR_KEY"],
        "project_id": int(os.environ["QA_CORTEX_TEST_TR_PROJECT"]),
        "linked_ticket_field": os.environ.get(
            "QA_CORTEX_TEST_TR_LINKED_FIELD", "custom_jira_id"
        ),
    }


@pytest.fixture
def confluence_config() -> dict:
    return {
        "url": os.environ["QA_CORTEX_TEST_CONF_URL"],
        "email": os.environ["QA_CORTEX_TEST_CONF_EMAIL"],
        "api_token": os.environ["QA_CORTEX_TEST_CONF_TOKEN"],
    }


@pytest.fixture
def slack_config() -> dict:
    return {"bot_token": os.environ["QA_CORTEX_TEST_SLACK_TOKEN"]}
