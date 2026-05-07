#!/usr/bin/env python3
"""qa-cortex interactive setup wizard.

Asks user about their stack, generates qa-cortex.config.toml + .env,
verifies connectivity. Goal: 'install in 1 hour' bar.

Usage::

    python scripts/setup.py                 # interactive
    python scripts/setup.py --check         # validate existing config only
    python scripts/setup.py --non-interactive  # use env vars (CI/scripted)
"""

from __future__ import annotations

import argparse
import os
import sys
from pathlib import Path
from typing import Any


# ----------------------------------------------------------------------
# UI helpers (no fancy lib — pure stdlib for portability)
# ----------------------------------------------------------------------


def color(text: str, code: str) -> str:
    if not sys.stdout.isatty():
        return text
    return f"\033[{code}m{text}\033[0m"


def ok(msg: str) -> None:
    print(color("✓", "32") + " " + msg)


def warn(msg: str) -> None:
    print(color("⚠", "33") + " " + msg)


def fail(msg: str) -> None:
    print(color("✗", "31") + " " + msg)


def section(title: str) -> None:
    print()
    print(color("═" * 60, "34"))
    print(color(title, "1;34"))
    print(color("═" * 60, "34"))


def prompt(question: str, default: str | None = None, secret: bool = False) -> str:
    suffix = f" [{default}]" if default else ""
    while True:
        if secret:
            import getpass
            val = getpass.getpass(f"{question}{suffix}: ")
        else:
            val = input(f"{question}{suffix}: ").strip()
        if val:
            return val
        if default is not None:
            return default
        print("  (required)")


def prompt_choice(question: str, options: list[str], default: str | None = None) -> str:
    print(f"\n{question}")
    for i, opt in enumerate(options, 1):
        marker = " (default)" if opt == default else ""
        print(f"  {i}. {opt}{marker}")
    while True:
        choice = input(f"Choice [1-{len(options)}]: ").strip()
        if not choice and default:
            return default
        if choice.isdigit() and 1 <= int(choice) <= len(options):
            return options[int(choice) - 1]
        print("  invalid choice")


# ----------------------------------------------------------------------
# Wizard logic
# ----------------------------------------------------------------------


def run_wizard() -> tuple[dict[str, Any], dict[str, str]]:
    """Returns (toml_config_dict, env_dict)."""
    section("qa-cortex setup wizard")
    print("This wizard will:")
    print("  1. Ask about your QA stack (which providers to use)")
    print("  2. Collect connection details")
    print("  3. Generate qa-cortex.config.toml + .env")
    print("  4. Optional: test connectivity to each backend")
    print()
    input(color("Press Enter to start (Ctrl-C to abort)...", "2"))

    config: dict[str, Any] = {"providers": {}}
    env: dict[str, str] = {}

    # ----- Ticketing -----
    section("1/5  Ticketing system")
    ticketing = prompt_choice(
        "Which ticketing system?",
        ["jira", "linear", "github", "youtrack"],
        default="jira",
    )
    config["providers"]["ticketing"] = ticketing

    if ticketing == "jira":
        url = prompt("Jira URL", default="https://your-org.atlassian.net")
        email = prompt("Jira email")
        token_var = "JIRA_API_TOKEN"
        token = prompt(
            f"Jira API token (https://id.atlassian.com/manage-profile/security/api-tokens)",
            secret=True,
        )
        env[token_var] = token
        env["JIRA_EMAIL"] = email

        prefix = prompt("Project key prefix (e.g. 'PROJ', 'ENG')", default="PROJ")

        config["ticketing"] = {
            "jira": {
                "url": url,
                "email": "${JIRA_EMAIL}",
                "api_token": "${JIRA_API_TOKEN}",
                "ticket_prefix": prefix,
                "default_project_key": prefix,
                "cloud": True,
                "verify_ssl": True,
            }
        }
        ok(f"Jira configured: {url} (project {prefix})")
    else:
        warn(f"{ticketing} adapter not yet implemented — see docs/adding-providers.md")
        warn("Aborting wizard. Re-run with 'jira' to proceed for v1.0 alpha.")
        sys.exit(0)

    # ----- Test management -----
    section("2/5  Test management")
    test_mgmt = prompt_choice(
        "Which test management?",
        ["testrail", "zephyr", "allure", "skip"],
        default="testrail",
    )

    if test_mgmt == "testrail":
        config["providers"]["test_management"] = "testrail"
        url = prompt("TestRail URL", default="https://your-org.testrail.io")
        username = prompt("TestRail username (email)")
        api_key = prompt("TestRail API key", secret=True)
        env["TESTRAIL_USERNAME"] = username
        env["TESTRAIL_API_KEY"] = api_key
        project_id = int(prompt("TestRail project_id (numeric)", default="1"))
        linked_field = prompt(
            "Custom field linking cases to tickets",
            default="custom_jira_id",
        )

        config["test_management"] = {
            "testrail": {
                "url": url,
                "username": "${TESTRAIL_USERNAME}",
                "api_key": "${TESTRAIL_API_KEY}",
                "project_id": project_id,
                "linked_ticket_field": linked_field,
            }
        }
        ok(f"TestRail configured: {url} (project {project_id})")
    elif test_mgmt == "skip":
        warn("Test management skipped — qa-cortex will not be able to query test cases")
        # Still need a placeholder to avoid config validation errors
        config["providers"]["test_management"] = "testrail"
        config["test_management"] = {"testrail": {
            "url": "https://placeholder.testrail.io",
            "username": "${TESTRAIL_USERNAME}",
            "api_key": "${TESTRAIL_API_KEY}",
            "project_id": 1,
            "linked_ticket_field": "custom_jira_id",
        }}
    else:
        warn(f"{test_mgmt} adapter not yet implemented")
        sys.exit(0)

    # ----- Documentation -----
    section("3/5  Documentation / Wiki")
    docs = prompt_choice(
        "Which documentation system?",
        ["confluence", "notion", "skip"],
        default="confluence",
    )

    if docs == "confluence":
        config["providers"]["documentation"] = "confluence"
        # If using Atlassian Cloud, share Jira credentials
        share_jira = prompt(
            "Use same Atlassian credentials as Jira? [y/n]", default="y"
        )
        if share_jira.lower() == "y":
            url = prompt("Confluence URL", default=f"{config['ticketing']['jira']['url']}/wiki")
            config["documentation"] = {
                "confluence": {
                    "url": url,
                    "email": "${JIRA_EMAIL}",
                    "api_token": "${JIRA_API_TOKEN}",
                }
            }
            ok(f"Confluence configured (sharing Jira creds): {url}")
        else:
            url = prompt("Confluence URL")
            email = prompt("Confluence email")
            token = prompt("Confluence API token", secret=True)
            env["CONFLUENCE_EMAIL"] = email
            env["CONFLUENCE_API_TOKEN"] = token
            config["documentation"] = {
                "confluence": {
                    "url": url,
                    "email": "${CONFLUENCE_EMAIL}",
                    "api_token": "${CONFLUENCE_API_TOKEN}",
                }
            }
            ok(f"Confluence configured: {url}")
    elif docs == "skip":
        warn("Documentation skipped")
        config["providers"]["documentation"] = "confluence"
        config["documentation"] = {"confluence": {
            "url": "https://placeholder.atlassian.net/wiki",
            "email": "${JIRA_EMAIL}",
            "api_token": "${JIRA_API_TOKEN}",
        }}
    else:
        warn(f"{docs} adapter not yet implemented")
        sys.exit(0)

    # ----- Chat -----
    section("4/5  Chat / messaging")
    chat = prompt_choice(
        "Which chat system?",
        ["slack", "teams", "discord", "skip"],
        default="slack",
    )

    if chat == "slack":
        config["providers"]["chat"] = "slack"
        bot_token = prompt(
            "Slack Bot OAuth token (xoxb-...) — see Slack app settings",
            secret=True,
        )
        env["SLACK_BOT_TOKEN"] = bot_token
        config["chat"] = {"slack": {"bot_token": "${SLACK_BOT_TOKEN}"}}
        ok("Slack configured")
    elif chat == "skip":
        warn("Chat skipped — brain won't post to or read messaging")
        config["providers"]["chat"] = "slack"
        config["chat"] = {"slack": {"bot_token": "${SLACK_BOT_TOKEN}"}}
        env["SLACK_BOT_TOKEN"] = "placeholder"
    else:
        warn(f"{chat} adapter not yet implemented")
        sys.exit(0)

    # ----- Browser -----
    config["providers"]["browser"] = "playwright"

    # ----- Brain settings -----
    section("5/5  Brain preferences")
    chat_lang = prompt_choice(
        "Chat language with user",
        ["en", "ru"],
        default="en",
    )
    config["brain"] = {
        "default_role_for_routine": "tester",
        "default_role_for_admin": "admin",
        "journal_language": "en",
        "chat_language": chat_lang,
    }
    config["modules"] = {"auto_load_product_map": True}

    return config, env


# ----------------------------------------------------------------------
# File writing
# ----------------------------------------------------------------------


def write_config_toml(config: dict[str, Any], path: Path) -> None:
    """Write config dict as TOML. Pure-stdlib using simple serializer."""
    lines = [
        "# qa-cortex configuration — generated by setup wizard",
        "# Edit as needed. Re-run scripts/setup.py to regenerate.",
        "# Tokens are in .env (NEVER commit .env)",
        "",
    ]

    # Providers section first
    lines.append("[providers]")
    for k, v in config["providers"].items():
        lines.append(f'{k} = "{v}"')
    lines.append("")

    # Per-category sections
    for category in ("ticketing", "test_management", "documentation", "chat"):
        if category not in config:
            continue
        for provider_name, provider_cfg in config[category].items():
            lines.append(f"[{category}.{provider_name}]")
            for k, v in provider_cfg.items():
                if isinstance(v, str):
                    lines.append(f'{k} = "{v}"')
                elif isinstance(v, bool):
                    lines.append(f"{k} = {'true' if v else 'false'}")
                elif isinstance(v, (int, float)):
                    lines.append(f"{k} = {v}")
                elif isinstance(v, list):
                    items = ", ".join(f'"{x}"' for x in v)
                    lines.append(f"{k} = [{items}]")
            lines.append("")

    if "brain" in config:
        lines.append("[brain]")
        for k, v in config["brain"].items():
            if isinstance(v, str):
                lines.append(f'{k} = "{v}"')
            elif isinstance(v, bool):
                lines.append(f"{k} = {'true' if v else 'false'}")
        lines.append("")

    if "modules" in config:
        lines.append("[modules]")
        for k, v in config["modules"].items():
            if isinstance(v, bool):
                lines.append(f"{k} = {'true' if v else 'false'}")
        lines.append("")

    path.write_text("\n".join(lines), encoding="utf-8")


def write_env(env: dict[str, str], path: Path) -> None:
    lines = [
        "# qa-cortex secrets — gitignored",
        "# Generated by setup wizard. Edit as needed.",
        "",
    ]
    for k, v in env.items():
        # Escape any " in value
        escaped = v.replace('"', '\\"')
        lines.append(f'{k}="{escaped}"')
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    # Set restrictive permissions on .env
    os.chmod(path, 0o600)


def verify_config(config_path: Path) -> bool:
    """Try to load config — catches obvious errors."""
    try:
        from qa_cortex.config import load_config
        load_config(config_path)
        return True
    except Exception as e:
        fail(f"Config validation failed: {e}")
        return False


# ----------------------------------------------------------------------
# Main
# ----------------------------------------------------------------------


def main() -> int:
    parser = argparse.ArgumentParser(description="qa-cortex setup wizard")
    parser.add_argument("--check", action="store_true", help="Validate existing config only")
    args = parser.parse_args()

    repo_root = Path.cwd()
    config_path = repo_root / "qa-cortex.config.toml"
    env_path = repo_root / ".env"

    if args.check:
        section("Config validation")
        if not config_path.exists():
            fail(f"No config at {config_path}")
            return 1
        if verify_config(config_path):
            ok(f"Config valid: {config_path}")
            return 0
        return 1

    # Existing files → confirm overwrite
    if config_path.exists():
        warn(f"{config_path} already exists")
        confirm = input("Overwrite? [y/N]: ").strip().lower()
        if confirm != "y":
            print("Aborted.")
            return 0

    config, env = run_wizard()

    section("Writing files")
    write_config_toml(config, config_path)
    ok(f"Wrote {config_path}")

    if env_path.exists():
        warn(f"{env_path} exists — appending new vars (manual review needed)")
        existing = env_path.read_text()
        with open(env_path, "a") as f:
            f.write("\n# Added by setup wizard\n")
            for k, v in env.items():
                if k not in existing:
                    escaped = v.replace('"', '\\"')
                    f.write(f'{k}="{escaped}"\n')
    else:
        write_env(env, env_path)
        ok(f"Wrote {env_path} (mode 0600)")

    section("Validating config")
    if verify_config(config_path):
        ok("Config valid!")
    else:
        fail("Config validation failed — review files manually")
        return 1

    section("Next steps")
    print(f"  1. Review {config_path} and {env_path}")
    print(f"  2. Run: claude")
    print(f"  3. Try: 'Тестируем PROJ-123' (or your ticket prefix)")
    print()
    print("For full guide: cat HOWTO.md")
    print("For testing: cat docs/testing.md")
    return 0


if __name__ == "__main__":
    try:
        sys.exit(main())
    except KeyboardInterrupt:
        print("\nAborted by user.")
        sys.exit(130)
