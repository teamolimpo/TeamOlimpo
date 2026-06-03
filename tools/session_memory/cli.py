"""CLI for Session Memory — compress observations.

Usage::

    uv run python -m tools.session_memory compress --warm --dry-run
    uv run python -m tools.session_memory compress --cold --apply
"""

from __future__ import annotations

import json
import sys

import typer
from loguru import logger

from tools.session_memory.store import SessionStore

# ---------------------------------------------------------------------------
# CLI App
# ---------------------------------------------------------------------------

app = typer.Typer(
    name="session-memory",
    help="Session Memory — manage and compress observations",
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
        None, "--age-days", help="Only compress observations older than N days"
    ),
) -> None:
    """Compress old observations (hot/warm/cold).

    Progressive compression:
    - **Warm** (level 1): compress observation content to max 300 chars
    - **Cold** (level 2): group by ISO week per-session into period summaries
    """
    if not warm and not cold:
        logger.error("Devi specificare almeno --warm o --cold.")
        sys.exit(2)

    max_level = 2 if cold else 1
    do_apply = apply or not dry_run

    logger.info(
        f"Session compression: max_level={max_level}, age_days={age_days}, dry_run={not do_apply}"
    )

    try:
        store = SessionStore()
        results = store.compress_observations(
            age_days=age_days,
            max_level=max_level,
            dry_run=not do_apply,
        )
        # Convert set to list for JSON serialization
        if isinstance(results.get("sessions_affected"), set):
            results["sessions_affected"] = sorted(results["sessions_affected"])
        print(json.dumps(results, indent=2))
        store.close()
    except Exception as e:
        logger.error(f"Session compression failed: {e}")
        sys.exit(1)


@app.callback()
def main() -> None:
    """Session Memory CLI."""
    pass


if __name__ == "__main__":
    app()
