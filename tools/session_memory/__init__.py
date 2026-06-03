"""Session Memory MCP server for Team Olimpo.

Auto-captures Poros session context between runs with 3-layer progressive
disclosure, entity linking, and FTS5 search.

Provides 5 MCP tools:
- session_init — initialize or resume a session
- session_observe — log an observation to the timeline
- session_context — retrieve progressive context (3 layers)
- session_recall — FTS5 search across sessions
- session_summarize — compress observations into summaries
"""

__version__ = "1.0.0"
