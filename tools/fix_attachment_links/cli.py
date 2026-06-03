"""CLI per fix-attachment-links — sistema riferimenti agli allegati nei file Markdown.

Uso:
    python -m tools.fix-attachment-links [OPTIONS]

Struttura:
    Tool singolo con comando main.
"""

from __future__ import annotations

import glob
import sys
from pathlib import Path
from typing import List

import typer
from loguru import logger

# ---------------------------------------------------------------------------
# App Typer
# ---------------------------------------------------------------------------

app = typer.Typer(
    name="fix-attachment-links",
    help="Sistema riferimenti agli allegati nei file Markdown del vault.",
    no_args_is_help=True,
)

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

OLD_REFS = ["../allegati/", "allegati/", "Inbox/allegati/"]
NEW_REF = "../attachments/"


def _setup_logging(verbose: bool) -> None:
    """Configura loguru: WARNING di default, DEBUG con --verbose."""
    logger.remove()
    level = "DEBUG" if verbose else "WARNING"
    logger.add(sys.stderr, level=level, format="<level>{level}</level>: {message}")


def find_md_files(base_path: Path) -> List[Path]:
    """Trova tutti i file .md nel percorso specificato con glob ricorsivo."""
    pattern = str(base_path / "**" / "*.md")
    files = glob.glob(pattern, recursive=True)
    return [Path(f) for f in files]


def fix_references_in_file(file_path: Path, dry_run: bool) -> int:
    """Sistema i riferimenti nel file e restituisce il numero di sostituzioni."""
    try:
        content = file_path.read_text(encoding="utf-8")
        original_content = content
        changes = 0
        for old_ref in OLD_REFS:
            new_content = content.replace(old_ref, NEW_REF)
            if new_content != content:
                changes += content.count(old_ref)
                content = new_content
        if content != original_content:
            logger.info(f"Modifiche in {file_path}: {changes} riferimenti aggiornati")
            if not dry_run:
                file_path.write_text(content, encoding="utf-8")
            return changes
        return 0
    except Exception as e:
        logger.error(f"Errore nel file {file_path}: {e}")
        return 0


# ---------------------------------------------------------------------------
# Comandi
# ---------------------------------------------------------------------------


@app.command()
def main(
    dry_run: bool = typer.Option(
        False,
        "--dry-run",
        help="Mostra le modifiche senza applicarle.",
    ),
    verbose: bool = typer.Option(
        False,
        "--verbose",
        "-v",
        help="Output debug dettagliato su stderr.",
    ),
) -> None:
    """Sistema riferimenti agli allegati nei file Markdown."""
    _setup_logging(verbose)

    base_path = Path("/home/stra/TeamOlimpo/vaults/email/Inbox/emails")
    logger.debug(f"Percorso base: {base_path}")
    logger.debug(f"Dry-run: {dry_run}")

    if not base_path.exists():
        logger.error(f"Percorso {base_path} non esiste.")
        raise typer.Exit(1)

    md_files = find_md_files(base_path)
    logger.debug(f"Trovati {len(md_files)} file .md")

    total_files_modified = 0
    total_references_updated = 0

    for file_path in md_files:
        changes = fix_references_in_file(file_path, dry_run)
        if changes > 0:
            total_files_modified += 1
            total_references_updated += changes

    typer.echo(
        f"Report: {total_files_modified} file modificati, {total_references_updated} riferimenti aggiornati."
    )
