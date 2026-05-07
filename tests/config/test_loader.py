"""Unit tests for config loader."""

from __future__ import annotations

import os
from pathlib import Path

import pytest

from qa_cortex.config import load_config, get_provider_config, ConfigError


VALID_TOML = """
[providers]
ticketing = "jira"
test_management = "testrail"
documentation = "confluence"
chat = "slack"
browser = "playwright"

[ticketing.jira]
url = "https://test.atlassian.net"
email = "${TEST_EMAIL}"
api_token = "${TEST_TOKEN}"
ticket_prefix = "TEST"
default_project_key = "TEST"

[test_management.testrail]
url = "https://test.testrail.io"
username = "${TEST_TR_USER}"
api_key = "${TEST_TR_KEY}"
project_id = 1
linked_ticket_field = "custom_jira_id"

[documentation.confluence]
url = "https://test.atlassian.net/wiki"
email = "${TEST_EMAIL}"
api_token = "${TEST_TOKEN}"

[chat.slack]
bot_token = "${TEST_SLACK_TOKEN}"
"""


@pytest.fixture
def env_vars(monkeypatch):
    monkeypatch.setenv("TEST_EMAIL", "test@example.com")
    monkeypatch.setenv("TEST_TOKEN", "fake-token")
    monkeypatch.setenv("TEST_TR_USER", "tr-user")
    monkeypatch.setenv("TEST_TR_KEY", "tr-key")
    monkeypatch.setenv("TEST_SLACK_TOKEN", "xoxb-fake")


@pytest.fixture
def valid_config_file(tmp_path: Path, env_vars):
    p = tmp_path / "qa-cortex.config.toml"
    p.write_text(VALID_TOML)
    return p


class TestLoadConfig:
    def test_loads_and_resolves_env_vars(self, valid_config_file: Path) -> None:
        config = load_config(valid_config_file)

        assert config["providers"]["ticketing"] == "jira"
        # Env vars resolved
        assert config["ticketing"]["jira"]["email"] == "test@example.com"
        assert config["ticketing"]["jira"]["api_token"] == "fake-token"

    def test_searches_default_paths_when_no_path(self, monkeypatch, tmp_path: Path) -> None:
        # Place config in cwd
        config_file = tmp_path / "qa-cortex.config.toml"
        config_file.write_text(VALID_TOML)
        monkeypatch.chdir(tmp_path)
        monkeypatch.setenv("TEST_EMAIL", "test@example.com")
        monkeypatch.setenv("TEST_TOKEN", "fake-token")
        monkeypatch.setenv("TEST_TR_USER", "tr-user")
        monkeypatch.setenv("TEST_TR_KEY", "tr-key")
        monkeypatch.setenv("TEST_SLACK_TOKEN", "xoxb-fake")

        config = load_config()
        assert config["providers"]["ticketing"] == "jira"

    def test_missing_file_raises(self, tmp_path: Path) -> None:
        with pytest.raises(ConfigError, match="not found"):
            load_config(tmp_path / "nonexistent.toml")


class TestEnvVarResolution:
    def test_unset_env_var_raises(self, tmp_path: Path) -> None:
        p = tmp_path / "config.toml"
        p.write_text("""
[providers]
ticketing = "jira"
test_management = "testrail"
documentation = "confluence"
chat = "slack"
browser = "playwright"

[ticketing.jira]
url = "x"
email = "${UNSET_VAR_XYZ}"
api_token = "x"
ticket_prefix = "x"
default_project_key = "x"

[test_management.testrail]
url = "x"
username = "x"
api_key = "x"
project_id = 1
linked_ticket_field = "x"

[documentation.confluence]
url = "x"
email = "x"
api_token = "x"

[chat.slack]
bot_token = "x"
""")
        with pytest.raises(ConfigError, match="UNSET_VAR_XYZ.*not set"):
            load_config(p)


class TestValidation:
    def test_missing_providers_section_raises(self, tmp_path: Path) -> None:
        p = tmp_path / "config.toml"
        p.write_text('[ticketing.jira]\nurl = "x"\n')
        with pytest.raises(ConfigError, match="Missing.*providers.*section"):
            load_config(p)

    def test_invalid_provider_value_raises(self, tmp_path: Path, env_vars) -> None:
        p = tmp_path / "config.toml"
        p.write_text("""
[providers]
ticketing = "unknown_provider"
test_management = "testrail"
documentation = "confluence"
chat = "slack"
browser = "playwright"
""")
        with pytest.raises(ConfigError, match="not recognized"):
            load_config(p)

    def test_missing_provider_section_raises(self, tmp_path: Path, env_vars) -> None:
        p = tmp_path / "config.toml"
        p.write_text("""
[providers]
ticketing = "jira"
test_management = "testrail"
documentation = "confluence"
chat = "slack"
browser = "playwright"

# No [ticketing.jira] section!
""")
        with pytest.raises(ConfigError, match=r"\[ticketing\.jira\] section missing"):
            load_config(p)


class TestGetProviderConfig:
    def test_extracts_selected_provider(self, valid_config_file: Path) -> None:
        config = load_config(valid_config_file)
        jira_config = get_provider_config(config, "ticketing")
        assert jira_config["url"] == "https://test.atlassian.net"
        assert jira_config["ticket_prefix"] == "TEST"

    def test_unknown_category_raises(self, valid_config_file: Path) -> None:
        config = load_config(valid_config_file)
        with pytest.raises(ConfigError, match="not in providers"):
            get_provider_config(config, "unknown")
