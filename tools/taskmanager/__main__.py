"""Entry point: python -m tools.taskmanager

Behaviour depends on arguments:
- With subcommand (e.g. ``compress``): runs CLI mode
- Without arguments: starts the MCP server on stdio transport
"""

from __future__ import annotations

import sys

if __name__ == "__main__":
    # Check if we have a subcommand (e.g. "compress")
    if len(sys.argv) > 1 and sys.argv[1] in ("compress",):
        from tools.taskmanager.main import app

        app()
    else:
        from tools.taskmanager.server import main_server

        main_server()
