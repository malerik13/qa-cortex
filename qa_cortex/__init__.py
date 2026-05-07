"""qa-cortex — Senior QA co-engineer scaffold.

Package layout:
    qa_cortex.providers   — Abstract Protocols + concrete provider adapters
    qa_cortex.servers     — MCP dispatch servers (one per provider category)
    qa_cortex.config      — Config loading (qa-cortex.config.toml)

Status: alpha — Phase 2 (adapter framework) in development.
See knowledge_base/design_docs/qa_cortex_v1.md for architecture.
"""

__version__ = "0.0.1-alpha"
