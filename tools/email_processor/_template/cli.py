"""CLI del tool — skeleton Typer per nuovi tool del Team Olimpo.

Uso:
    Copia questa cartella, rinomina in tools/<nome_tool>/,
    sostituisci TOOL_NAME e implementa la logica nei comandi.

Struttura per tool con subcommand:
    app = typer.Typer()

    @app.command()
    def primo_comando(...): ...

    @app.command()
    def secondo_comando(...): ...

Struttura per tool senza subcommand (comando singolo):
    app = typer.Typer()

    @app.command()
    def main(...): ...
"""

from __future__ import annotations

import sys
from pathlib import Path

import typer
from loguru import logger

# ---------------------------------------------------------------------------
# App Typer
# ---------------------------------------------------------------------------

app = typer.Typer(
    name="TOOL_NAME",
    help="Descrizione breve del tool.",
    no_args_is_help=True,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _setup_logging(verbose: bool) -> None:
    """Configura loguru: WARNING di default, DEBUG con --verbose."""
    logger.remove()
    level = "DEBUG" if verbose else "WARNING"
    logger.add(sys.stderr, level=level, format="<level>{level}</level>: {message}")


# ---------------------------------------------------------------------------
# Comandi
# ---------------------------------------------------------------------------


@app.command()
def main(
    input: Path = typer.Argument(
        ...,
        help="File di input.",
        exists=True,
        readable=True,
    ),
    output: Path = typer.Option(
        None,
        "--output",
        "-o",
        help="File o cartella di output. Se omesso, viene generato automaticamente.",
    ),
    verbose: bool = typer.Option(
        False,
        "--verbose",
        "-v",
        help="Output debug dettagliato su stderr.",
    ),
) -> None:
    """Descrizione estesa del comando principale."""
    _setup_logging(verbose)

    logger.debug(f"Input: {input}")
    logger.debug(f"Output: {output}")

    # --- logica qui ---

    typer.echo(f"Elaborazione di {input.name}...")
