"""CLI del tool file_stats — scansione directory e report estensioni file.

Uso:
    uv run python -m tools.file_stats scan <directory> [--recursive] [-v]
"""

from __future__ import annotations

import sys
from collections import Counter
from pathlib import Path

import typer
from loguru import logger

# ---------------------------------------------------------------------------
# App Typer
# ---------------------------------------------------------------------------

app = typer.Typer(
    name="file_stats",
    help="Scansiona una directory e produce un report delle estensioni file con conteggi ordinati.",
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


def _scan_directory(directory: Path, recursive: bool) -> tuple[Counter[str], int, int]:
    """Scansiona una directory e conta le estensioni dei file.

    Args:
        directory: Path della directory da scansionare.
        recursive: Se True, scansiona ricorsivamente le sottodirectory.

    Returns:
        Tupla (Counter estensioni, totale file, totale directory).

    Raises:
        FileNotFoundError: Se la directory non esiste.
        PermissionError: Se non si hanno permessi di lettura.
    """
    ext_counter: Counter[str] = Counter()
    total_files = 0
    total_dirs = 0

    if not directory.exists():
        raise FileNotFoundError(f"Directory non trovata: {directory}")
    if not directory.is_dir():
        raise NotADirectoryError(f"Non e' una directory: {directory}")

    iterator = directory.rglob("*") if recursive else directory.iterdir()

    for entry in iterator:
        try:
            if entry.is_file():
                ext = entry.suffix.lower() if entry.suffix else "(nessuna)"
                ext_counter[ext] += 1
                total_files += 1
                logger.debug(f"File: {entry.name} -> estensione: {ext}")
            elif entry.is_dir():
                total_dirs += 1
                logger.debug(f"Directory: {entry.name}")
        except PermissionError:
            logger.warning(f"Permesso negato, salto: {entry}")

    return ext_counter, total_files, total_dirs


def _print_report(
    ext_counter: Counter[str], total_files: int, total_dirs: int, directory: Path
) -> None:
    """Stampa il report delle estensioni su stdout.

    Args:
        ext_counter: Counter con le estensioni e i relativi conteggi.
        total_files: Numero totale di file trovati.
        total_dirs: Numero totale di directory trovate.
        directory: Path della directory scansionata.
    """
    typer.echo(f"Report estensioni per: {directory}")
    typer.echo("=" * 40)

    if not ext_counter:
        typer.echo("Nessun file trovato.")
        typer.echo(f"Totale directory: {total_dirs}")
        return

    typer.echo(f"{'Estensione':<20} {'Conteggio':>10}")
    typer.echo("-" * 40)

    for ext, count in ext_counter.most_common():
        typer.echo(f"{ext:<20} {count:>10}")

    typer.echo("-" * 40)
    typer.echo(f"{'TOTALE':<20} {total_files:>10}")
    typer.echo(f"Directory scansionate: {total_dirs}")


# ---------------------------------------------------------------------------
# Comandi
# ---------------------------------------------------------------------------


@app.command()
def scan(
    directory: Path = typer.Argument(
        ...,
        help="Directory da scansionare.",
    ),
    recursive: bool = typer.Option(
        False,
        "--recursive",
        "-r",
        help="Scansione ricorsiva delle sottodirectory.",
    ),
    verbose: bool = typer.Option(
        False,
        "--verbose",
        "-v",
        help="Output debug dettagliato su stderr.",
    ),
) -> None:
    """Scansiona una directory e conta le estensioni dei file.

    Produce un report ordinato per conteggio decrescente con
    il totale dei file e delle directory trovati.
    """
    _setup_logging(verbose)

    logger.debug(f"Directory: {directory}")
    logger.debug(f"Ricorsiva: {recursive}")

    try:
        ext_counter, total_files, total_dirs = _scan_directory(directory, recursive)
    except (FileNotFoundError, NotADirectoryError) as exc:
        logger.error(str(exc))
        raise typer.Exit(code=1) from exc

    _print_report(ext_counter, total_files, total_dirs, directory)
