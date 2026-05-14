# qa-cortex

> Senior QA co-engineer for any stack. Autonomous on routine, gated on critical.

**Status:** v0.0.1 alpha — skeleton. Working brain requires configuration (see INSTALL.md).

---

## What it is

qa-cortex is a Claude Code scaffold that gives QA engineers a domain-aware co-engineer:

- Reads your tickets (Jira / Linear / YouTrack / GitHub Issues)
- Plans tests against Acceptance Criteria, not guesses
- Files bug reports in your template, with approval gate
- Logs daily journal, drives browser for evidence
- Autonomous on routine work, asks before anything critical (trust tiering)

## Quick install

```bash
git clone https://github.com/malerik13/qa-cortex.git qa-cortex
cd qa-cortex
./scripts/install.sh
$EDITOR .env          # fill your tokens
./scripts/setup.sh    # build KB index (YouTrack+Allure stack)
claude                # open Claude Code
```

Full walkthrough: [INSTALL.md](INSTALL.md)

## Architecture

Three layers:

```
qa-cortex CORE          — personas, skills, trust tiering, flow cache
     ↓
Provider adapters       — Jira / TestRail / YouTrack / Allure (configurable)
     ↓
Your instance           — your KB, your flows, your credentials
```

Design doc: [knowledge_base/design_docs/qa_cortex_v1.md](knowledge_base/design_docs/qa_cortex_v1.md)

## Default stacks supported

| Layer | Default | Alternatives |
|---|---|---|
| Ticketing | YouTrack (bundled MCP) | Jira, Linear, GitHub Issues |
| Test mgmt | Allure (bundled MCP) | TestRail, Zephyr |
| Browser | Playwright | — |
| Chat | Slack | — |

## License

MIT — see [LICENSE](LICENSE)
