"""Cron automation for warm/cold log compression.

This script is designed to be run on a schedule:
- Weekly: run warm compression on both Taskmanager and Session Memory
- Monthly: run cold compression on both systems
- Status: show current compression state

Usage::

    uv run python -m tools.log_compressor weekly    # warm (default: 7d threshold)
    uv run python -m tools.log_compressor monthly   # cold (default: 30d threshold)
    uv run python -m tools.log_compressor status    # show compression stats
    uv run python -m tools.log_compressor weekly --apply   # actually compress
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import typer
from loguru import logger

from tools.taskmanager.state import StateStore, compress_events

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

_LOG_FILE = Path("Library/System/Poros/log_compression.log")

# ---------------------------------------------------------------------------
# App
# ---------------------------------------------------------------------------

app = typer.Typer(
    name="log-compressor",
    help="Cron automation for warm/cold log compression",
)


def _log_result(phase: str, results: dict[str, Any]) -> None:
    """Append a result entry to the compression log file.

    Args:
        phase: ``weekly`` or ``monthly``.
        results: Result dict from compression.
    """
    from tools.taskmanager.models import now_iso

    entry = {
        "timestamp": now_iso(),
        "phase": phase,
        "results": results,
    }
    try:
        log_path = _LOG_FILE
        log_path.parent.mkdir(parents=True, exist_ok=True)
        with log_path.open("a", encoding="utf-8") as f:
            f.write(json.dumps(entry) + "\n")
    except Exception as e:
        logger.warning(f"Failed to write compression log: {e}")


def _run_taskmanager_compression(
    max_level: int,
    apply: bool,
) -> dict[str, Any]:
    """Run compression on taskmanager.

    Args:
        max_level: 1 for warm, 2 for cold.
        apply: If True, persist changes.

    Returns:
        Result dict from compress_events().
    """
    logger.info(f"Taskmanager compression: max_level={max_level}, apply={apply}")
    return compress_events(max_level=max_level, dry_run=not apply)


def _run_session_compression(
    max_level: int,
    apply: bool,
) -> dict[str, Any]:
    """Run compression on session memory observations.

    Args:
        max_level: 1 for warm, 2 for cold.
        apply: If True, persist changes.

    Returns:
        Result dict from compress_observations().
    """
    from tools.session_memory.store import SessionStore

    logger.info(f"Session compression: max_level={max_level}, apply={apply}")
    store = SessionStore()
    try:
        results = store.compress_observations(
            max_level=max_level,
            dry_run=not apply,
        )
        if isinstance(results.get("sessions_affected"), set):
            results["sessions_affected"] = sorted(results["sessions_affected"])
        return results
    finally:
        store.close()


# ---------------------------------------------------------------------------
# Commands
# ---------------------------------------------------------------------------


@app.command()
def weekly(
    apply: bool = typer.Option(False, "--apply", help="Apply changes (default: dry-run)"),
) -> None:
    """Run warm compression (weekly schedule).

    Compresses events/observations older than 7 days to warm level (level 1).
    """
    logger.info("=== Weekly warm compression ===")

    tm_results = _run_taskmanager_compression(max_level=1, apply=apply)
    sm_results = _run_session_compression(max_level=1, apply=apply)

    combined: dict[str, Any] = {
        "taskmanager": tm_results,
        "session_memory": sm_results,
    }

    _log_result("weekly", combined)

    print(json.dumps(combined, indent=2))
    logger.info("Weekly warm compression complete")


@app.command()
def monthly(
    apply: bool = typer.Option(False, "--apply", help="Apply changes (default: dry-run)"),
) -> None:
    """Run cold compression (monthly schedule).

    Compresses events/observations older than 30 days to cold level (level 2).
    """
    logger.info("=== Monthly cold compression ===")

    tm_results = _run_taskmanager_compression(max_level=2, apply=apply)
    sm_results = _run_session_compression(max_level=2, apply=apply)

    combined: dict[str, Any] = {
        "taskmanager": tm_results,
        "session_memory": sm_results,
    }

    _log_result("monthly", combined)

    print(json.dumps(combined, indent=2))
    logger.info("Monthly cold compression complete")


@app.command()
def status() -> None:
    """Show current compression status across both systems."""
    print("=== Compression Status ===\n")

    # Taskmanager status
    try:
        store = StateStore()
        data = store.load()
        tasks = data.get("tasks", {})
        total = len(tasks)
        level_counts: dict[int, int] = {}
        for t in tasks.values():
            lvl = t.get("compression_level", 0)
            level_counts[lvl] = level_counts.get(lvl, 0) + 1
        print(f"Taskmanager: {total} tasks")
        print(f"  Hot (level 0):   {level_counts.get(0, 0)}")
        print(f"  Warm (level 1):  {level_counts.get(1, 0)}")
        print(f"  Cold (level 2):  {level_counts.get(2, 0)}")
        total_events = sum(len(t.get("events", [])) for t in tasks.values())
        print(f"  Total events:    {total_events}")
        print()
    except Exception as e:
        print(f"Taskmanager: ERROR — {e}\n")

    # Session memory status
    try:
        from tools.session_memory.store import SessionStore

        sm_store = SessionStore()
        try:
            obs_count = sm_store._conn.execute(
                "SELECT COUNT(*) AS cnt FROM observations"
            ).fetchone()["cnt"]
            level_dist = sm_store._conn.execute(
                """SELECT compression_level, COUNT(*) AS cnt
                   FROM observations
                   GROUP BY compression_level
                   ORDER BY compression_level"""
            ).fetchall()
            summary_count = sm_store._conn.execute(
                "SELECT COUNT(*) AS cnt FROM summaries"
            ).fetchone()["cnt"]
            session_count = sm_store._conn.execute(
                "SELECT COUNT(*) AS cnt FROM sessions"
            ).fetchone()["cnt"]

            print(
                "Session Memory: "
                f"{session_count} sessions, {obs_count} obs, {summary_count} summaries"
            )
            for row in level_dist:
                lvl = row["compression_level"]
                lvl_name = {0: "Hot", 1: "Warm", 2: "Cold"}.get(lvl, f"Level {lvl}")
                print(f"  {lvl_name}: {row['cnt']}")
        finally:
            sm_store.close()
    except Exception as e:
        print(f"Session Memory: ERROR — {e}\n")

    # Log file
    log_path = _LOG_FILE
    if log_path.exists():
        line_count = len(log_path.read_text(encoding="utf-8").splitlines())
        print(f"Compression log: {log_path} ({line_count} entries)")
    else:
        print("Compression log: (none yet)")

    print()


@app.callback()
def main() -> None:
    """Log Compressor — cron automation."""
    pass


if __name__ == "__main__":
    app()
