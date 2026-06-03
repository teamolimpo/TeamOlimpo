"""CLI per contare file .md con frontmatter YAML valido.

Scansione ricorsiva a partire da una directory radice (default: repo root).
Esclude automaticamente node_modules/, .git/, Archivio/.

Un file ha frontmatter valido se:
  - La riga 1 e' esattamente "---"
  - Esiste un secondo "---" in una riga successiva

Uso:
    uv run python -m tools.frontmatter_counter
    uv run python -m tools.frontmatter_counter /path/to/dir
    uv run python -m tools.frontmatter_counter --verbose
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
    name="frontmatter-counter",
    help="Conta file .md con frontmatter YAML valido in una directory (ricorsivo).",
    no_args_is_help=True,
)

# Directory da escludere dalla scansione
EXCLUDE_DIRS = frozenset({"node_modules", ".git", "Archivio"})


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _setup_logging(verbose: bool) -> None:
    """Configura loguru: WARNING di default, DEBUG con --verbose."""
    logger.remove()
    level = "DEBUG" if verbose else "WARNING"
    logger.add(sys.stderr, level=level, format="<level>{level}</level>: {message}")


def _has_valid_frontmatter(file_path: Path) -> bool:
    """Verifica se un file Markdown ha un frontmatter YAML valido.

    Un frontmatter e' valido se:
    - La prima riga e' esattamente "---"
    - Esiste un secondo "---" in una riga successiva (entro le prime 200 righe)

    Args:
        file_path: Percorso del file da analizzare.

    Returns:
        True se il frontmatter e' valido, False altrimenti.
    """
    try:
        with file_path.open("r", encoding="utf-8", errors="replace") as f:
            # Leggiamo solo le prime righe (il frontmatter e' all'inizio)
            first_line = f.readline().rstrip("\n\r")
            if first_line != "---":
                return False

            # Cerchiamo il secondo "---" entro 200 righe
            for _ in range(200):
                line = f.readline()
                if not line:  # EOF
                    return False
                if line.rstrip("\n\r") == "---":
                    return True

            return False

    except (OSError, UnicodeDecodeError) as exc:
        logger.debug(f"Errore lettura {file_path}: {exc}")
        return False


def _scan_markdown_files(root: Path) -> tuple[list[Path], list[Path]]:
    """Scansiona ricorsivamente i file .md escludendo directory note.

    Args:
        root: Directory radice da cui partire.

    Returns:
        Tupla (file_con_frontmatter, file_senza_frontmatter).
    """
    valid_files: list[Path] = []
    invalid_files: list[Path] = []

    for md_file in root.rglob("*.md"):
        # Controlliamo se il file e' in una directory esclusa
        parts = md_file.parts
        if any(excluded in parts for excluded in EXCLUDE_DIRS):
            logger.debug(f"Saltato (directory esclusa): {md_file}")
            continue

        logger.debug(f"Analizzo: {md_file}")

        if _has_valid_frontmatter(md_file):
            valid_files.append(md_file)
        else:
            invalid_files.append(md_file)

    return valid_files, invalid_files


# ---------------------------------------------------------------------------
# Comando principale
# ---------------------------------------------------------------------------


@app.command()
def count(
    directory: Path = typer.Argument(
        None,
        help="Directory radice da scansionare. Default: directory corrente.",
        exists=True,
        readable=True,
        file_okay=False,
    ),
    verbose: bool = typer.Option(
        False,
        "--verbose",
        "-v",
        help="Output debug dettagliato su stderr.",
    ),
) -> None:
    """Conta i file .md con e senza frontmatter YAML valido.

    Scansione ricorsiva che esclude node_modules/, .git/, Archivio/.
    """
    _setup_logging(verbose)

    root = directory or Path.cwd()
    logger.debug(f"Directory radice: {root}")

    valid_files, invalid_files = _scan_markdown_files(root)

    total = len(valid_files) + len(invalid_files)

    typer.echo(f"\n{'=' * 60}")
    typer.echo(f"Frontmatter Counter — {root}")
    typer.echo(f"{'=' * 60}")
    typer.echo(f"File .md totali analizzati:  {total}")
    typer.echo(f"Con frontmatter valido:      {len(valid_files)}")
    typer.echo(f"Senza frontmatter valido:    {len(invalid_files)}")
    typer.echo(f"{'=' * 60}\n")

    if verbose and valid_files:
        typer.echo("File con frontmatter valido:")
        for f in sorted(valid_files):
            typer.echo(f"  ✓ {f.relative_to(root)}")

    if verbose and invalid_files:
        typer.echo("\nFile senza frontmatter valido:")
        for f in sorted(invalid_files):
            typer.echo(f"  ✗ {f.relative_to(root)}")

    # Exit code: 0 = successo, indipendentemente dal risultato
    raise typer.Exit(code=0)
