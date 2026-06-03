"""
Entry point CLI per il tool handoff_register.

Comandi disponibili:
  sync      Rigenera Registro.md (scan ricorsivo su HANDOFF_DIR)
  registro  Solo rigenera Registro.md (read-only)

Flag globale:
  --verbose / -v    Abbassa la soglia di log su stderr a DEBUG

Utilizzo:
  python -m tools.handoff_register sync
  python -m tools.handoff_register registro
"""

from __future__ import annotations

import sys

import typer
from loguru import logger
from rich.console import Console

from tools.handoff_register.config import HANDOFF_DIR, LOG_FILE, REGISTRO_PATH
from tools.handoff_register.scanner import scan_all
from tools.handoff_register.writer import write_registro

console = Console(stderr=True)

app = typer.Typer(
    name="handoff_register",
    help="Gestione registro handoff Team Olimpo.",
    no_args_is_help=True,
)

_verbose_state: dict[str, bool] = {"verbose": False}


# ---------------------------------------------------------------------------
# Configurazione logging
# ---------------------------------------------------------------------------


def _setup_logging(verbose: bool = False) -> None:
    """
    Configura loguru: handler su file (tutti i livelli) + stderr (WARNING+).

    Args:
        verbose: Se True, abbassa la soglia stderr a DEBUG.
    """
    logger.remove()

    LOG_FILE.parent.mkdir(parents=True, exist_ok=True)
    logger.add(
        str(LOG_FILE),
        level="DEBUG",
        rotation="5 MB",
        retention="30 days",
        encoding="utf-8",
        format="{time:YYYY-MM-DD HH:mm:ss} | {level:<8} | {name}:{line} — {message}",
    )

    console_level = "DEBUG" if verbose else "WARNING"
    logger.add(
        sys.stderr,
        level=console_level,
        format="<level>{level:<8}</level> | {message}",
        colorize=True,
    )


# ---------------------------------------------------------------------------
# Callback globale (verbose)
# ---------------------------------------------------------------------------


@app.callback()
def common(
    verbose: bool = typer.Option(False, "--verbose", "-v", help="Output debug su stderr."),
) -> None:
    """Gestione registro e archiviazione file handoff del Team Olimpo."""
    _verbose_state["verbose"] = verbose
    _setup_logging(verbose)


# ---------------------------------------------------------------------------
# Comandi
# ---------------------------------------------------------------------------


@app.command()
def sync() -> None:
    """Scansiona e rigenera Registro.md."""
    logger.debug("[sync] Avvio sync completo")

    active, archived = scan_all(HANDOFF_DIR)

    try:
        write_registro(active, archived, REGISTRO_PATH)
    except OSError as exc:
        console.print(f"[bold red]ERRORE scrittura Registro:[/bold red] {exc}")
        logger.error(f"[sync] Errore scrittura Registro: {exc}")
        raise typer.Exit(code=1)

    console.print(f"[green]Registro aggiornato:[/green] {REGISTRO_PATH}")
    logger.info(f"[sync] Completato. {len(active)} attivi, {len(archived)} archiviati")


@app.command()
def registro() -> None:
    """Solo rigenerazione Registro.md (read-only)."""
    logger.debug("[registro] Rigenera Registro.md (solo lettura)")

    active, archived = scan_all(HANDOFF_DIR)

    try:
        write_registro(active, archived, REGISTRO_PATH)
    except OSError as exc:
        console.print(f"[bold red]ERRORE scrittura Registro:[/bold red] {exc}")
        logger.error(f"[registro] Errore scrittura Registro: {exc}")
        raise typer.Exit(code=1)

    console.print(
        f"Registro aggiornato: [bold]{REGISTRO_PATH}[/bold] "
        f"({len(active)} attivi, {len(archived)} archiviati)"
    )
