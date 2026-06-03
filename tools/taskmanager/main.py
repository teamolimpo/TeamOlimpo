"""Facade that re-exports main_server for convenience imports.

Also provides a ``compress`` CLI command for running compression directly::

    uv run python -m tools.taskmanager compress --warm --dry-run
    uv run python -m tools.taskmanager compress --cold --apply
"""

from __future__ import annotations

import json
import sys

import typer
from loguru import logger

from tools.taskmanager.server import main_server
from tools.taskmanager.state import compress_events

# ---------------------------------------------------------------------------
# CLI App
# ---------------------------------------------------------------------------

app = typer.Typer(
    name="taskmanager",
    help="Task Manager — manage tasks and compress event logs",
)


@app.command()
def compress(
    warm: bool = typer.Option(False, "--warm", help="Compress to warm level (level 1)"),
    cold: bool = typer.Option(False, "--cold", help="Compress to cold level (level 2)"),
    dry_run: bool = typer.Option(True, "--dry-run", help="Show what would be done without saving"),
    apply: bool = typer.Option(
        False,
        "--apply",
        help="Apply compression (overrides --dry-run)",
    ),
    age_days: int | None = typer.Option(
        None, "--age-days", help="Only compress tasks older than N days"
    ),
) -> None:
    """Compress task event logs based on age (hot/warm/cold).

    Progressive compression:
    - **Warm** (level 1): compress event details to max 200 chars
    - **Cold** (level 2): replace events with period summaries
    """
    if not warm and not cold:
        logger.error("Devi specificare almeno --warm o --cold.")
        sys.exit(2)

    max_level = 2 if cold else 1
    do_apply = apply or not dry_run

    logger.info(f"Compression: max_level={max_level}, age_days={age_days}, dry_run={not do_apply}")

    try:
        results = compress_events(
            age_days=age_days,
            max_level=max_level,
            dry_run=not do_apply,
        )
        print(json.dumps(results, indent=2))
    except Exception as e:
        logger.error(f"Compression failed: {e}")
        sys.exit(1)


@app.callback()
def main() -> None:
    """Task Manager CLI."""
    pass


# ---------------------------------------------------------------------------
# Re-export main_server for MCP server entry
# ---------------------------------------------------------------------------

__all__ = ["main_server", "app"]

if __name__ == "__main__":
    app()
