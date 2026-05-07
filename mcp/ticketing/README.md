# ticketing provider adapters (Phase 2)

> **Status: empty (Phase 2 work).**
>
> This directory will hold concrete provider implementations:

- \`jira.py\` — wraps `sooperset/mcp-atlassian`
- `linear.py` — community Linear MCP wrapper
- `github.py` — wraps `@modelcontextprotocol/server-github`
- `youtrack.py` — kept in scalefinal-qa-assistant (private instance)

All implement `qa_cortex.providers.TicketingProvider` Protocol.

See `knowledge_base/design_docs/qa_cortex_v1.md` §7 for interface definition.
