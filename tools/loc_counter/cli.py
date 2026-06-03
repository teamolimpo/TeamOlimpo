"""CLI per loc_counter — conta righe totali e non-vuote nei file .md degli agenti."""

from __future__ import annotations

import sys
from pathlib import Path

import typer
from loguru import logger
from rich.console import Console
from rich.table import Table

from tools.common.paths import project_root

# ---------------------------------------------------------------------------
# App Typer
# ---------------------------------------------------------------------------

app = typer.Typer(
    name="loc_counter",
    help="Conta le righe di codice nei file .md sotto .opencode/agents/.",
    no_args_is_help=True,
)

# ---------------------------------------------------------------------------
# Costanti
# ---------------------------------------------------------------------------

PROJECT_ROOT = project_root()
AGENTS_DIR = PROJECT_ROOT / ".opencode" / "agents"

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _setup_logging(verbose: bool) -> None:
    """Configura loguru: WARNING di default, DEBUG con --verbose."""
    logger.remove()
    level = "DEBUG" if verbose else "INFO"
    logger.add(sys.stderr, level=level, format="<level>{level}</level>: {message}")


def _count_lines(file_path: Path) -> tuple[int, int]:
    """Conta righe totali e non-vuote in un file.

    Returns:
        Tupla (total_lines, non_empty_lines).
    """
    total = 0
    non_empty = 0
    with file_path.open("r", encoding="utf-8") as fh:
        for line in fh:
            total += 1
            if line.strip():
                non_empty += 1
    return total, non_empty


# ---------------------------------------------------------------------------
# Comando principale
# ---------------------------------------------------------------------------


@app.command()
def count(
    verbose: bool = typer.Option(
        False,
        "--verbose",
        "-v",
        help="Output debug dettagliato su stderr.",
    ),
) -> None:
    """Conta le righe di tutti i file .md in .opencode/agents/ e stampa un riepilogo."""
    _setup_logging(verbose)

    if not AGENTS_DIR.is_dir():
        logger.error(f"Directory agenti non trovata: {AGENTS_DIR}")
        raise typer.Exit(code=1)

    md_files = sorted(AGENTS_DIR.glob("*.md"))

    if not md_files:
        logger.warning("Nessun file .md trovato in .opencode/agents/")
        typer.echo("Nessun file .md trovato.")
        raise typer.Exit(code=0)

    logger.info(f"Trovati {len(md_files)} file .md in {AGENTS_DIR.relative_to(PROJECT_ROOT)}")

    console = Console()
    table = Table(title="Line Counter — .opencode/agents/")
    table.add_column("File", style="cyan", no_wrap=True)
    table.add_column("Total Lines", justify="right", style="green")
    table.add_column("Non-Empty Lines", justify="right", style="yellow")

    grand_total = 0
    grand_non_empty = 0

    for md_file in md_files:
        total, non_empty = _count_lines(md_file)
        grand_total += total
        grand_non_empty += non_empty
        logger.debug(f"{md_file.name}: {total} total, {non_empty} non-empty")
        table.add_row(md_file.name, str(total), str(non_empty))

    table.add_row(
        "[bold]TOTAL[/bold]",
        f"[bold]{grand_total}[/bold]",
        f"[bold]{grand_non_empty}[/bold]",
        style="bold",
    )

    console.print(table)
    logger.info(f"Totale: {grand_total} righe, {grand_non_empty} non-vuote")
