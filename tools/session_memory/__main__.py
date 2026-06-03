"""Entry point: python -m tools.session_memory

Behaviour depends on arguments:
- With subcommand (e.g. ``compress``): runs CLI mode
- Without arguments: starts the MCP server on stdio transport
"""

from __future__ import annotations

import sys

if __name__ == "__main__":
    # Check if we have a subcommand
    if len(sys.argv) > 1 and sys.argv[1] in ("compress",):
        from tools.session_memory.cli import app

        app()
    else:
        from tools.session_memory.server import main_server

        main_server()
