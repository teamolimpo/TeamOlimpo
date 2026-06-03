"""
Entry point CLI per il tool kba_indexer.

Comandi disponibili:
  index    Parsa file batch MD e li indicizza nel catalogo KBA
  list     Elenca i record presenti nel catalogo
  stats    Mostra statistiche aggregate sul catalogo

Utilizzo:
  python -m tools.kba_indexer <comando> [opzioni]
"""

from __future__ import annotations

import sys
from enum import Enum
from pathlib import Path
from typing import Any

import typer
import yaml
from loguru import logger
from rich.console import Console
from rich.table import Table

from tools.common.paths import resolve_absolute
from tools.kba_indexer.config import (
    BATCH_DIR,
    INDEX_FILE,
    LOG_FILE,
    PROJECT_ROOT,
    RECORDS_DIR,
)
from tools.kba_indexer.parser import parse_batch_file
from tools.kba_indexer.writer import rebuild_index, write_record

console = Console()

app = typer.Typer(
    name="kba_indexer",
    help="Indicizza batch MD nel catalogo KBA.",
    no_args_is_help=True,
)


class SortField(str, Enum):
    score = "score"
    level = "level"
    id = "id"


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
    """Indicizzatore batch per il catalogo KBA del Team Olimpo."""
    _setup_logging(verbose)


# ---------------------------------------------------------------------------
# Risoluzione input path
# ---------------------------------------------------------------------------


def _resolve_input_path(raw: Path) -> Path:
    """
    Risolve il path di input passato da CLI.

    Se il path e' relativo lo interpreta rispetto a PROJECT_ROOT.

    Args:
        raw: Path dall'argomento --input.

    Returns:
        Path assoluto risolto.
    """
    return resolve_absolute(raw)


def _collect_batch_files(input_path: Path) -> list[Path]:
    """
    Raccoglie i file batch MD da processare.

    Se input_path e' una directory, restituisce tutti i *.md al suo interno
    (non ricorsivo). Se e' un file singolo, restituisce [input_path].

    Args:
        input_path: Path a directory o file MD.

    Returns:
        Lista ordinata di Path ai file MD.
    """
    if input_path.is_file():
        return [input_path]
    if input_path.is_dir():
        # Raccoglie .md, .json e .txt — il parser gestisce tutti e tre i formati
        files: list[Path] = []
        for ext in ("*.md", "*.json", "*.txt"):
            files.extend(input_path.glob(ext))
        return sorted(set(files))
    # Potrebbe essere un glob pattern parziale — prova come parent + pattern
    parent = input_path.parent
    pattern = input_path.name
    if parent.is_dir():
        return sorted(parent.glob(pattern))
    return []


# ---------------------------------------------------------------------------
# Comando: index
# ---------------------------------------------------------------------------


@app.command(name="index")
def cmd_index(
    input: Path = typer.Option(BATCH_DIR, "--input", "-i", help="Dir, file o glob pattern."),
    force: bool = typer.Option(False, "--force", "-f", help="Sovrascrive record esistenti."),
    dry_run: bool = typer.Option(False, "--dry-run", help="Mostra senza scrivere."),
) -> None:
    """Parsa file batch MD e li indicizza nel catalogo."""
    input_path = _resolve_input_path(input)
    batch_files = _collect_batch_files(input_path)

    if not batch_files:
        console.print(f"[yellow]Nessun file batch trovato in:[/yellow] {input_path}")
        return

    total = len(batch_files)
    indexed = 0
    skipped = 0
    errors = 0

    for i, file_path in enumerate(batch_files, 1):
        prefix = f"[{i:>3}/{total}]"

        # Prova a leggere il kba_id per l'output — se fallisce, usa il filename
        try:
            import re as _re
            import yaml as _yaml

            raw = file_path.read_text(encoding="utf-8")
            fm_match = _re.match(r"\A---\s*\n([\s\S]*?)\n---\s*\n", raw, _re.MULTILINE)
            kba_display = file_path.stem
            if fm_match:
                fm = _yaml.safe_load(fm_match.group(1))
                if isinstance(fm, dict) and fm.get("kba"):
                    kba_display = str(fm["kba"]).lower()
        except Exception:
            kba_display = file_path.stem

        # Controllo idempotenza
        slug = kba_display.lower()
        record_path = RECORDS_DIR / f"{slug}.md"
        already_exists = record_path.exists()

        if already_exists and not force:
            console.print(
                f"{prefix} [cyan]{kba_display:<20}[/cyan] "
                f"[yellow]-> skip[/yellow]    (gia' presente — usa --force per sovrascrivere)"
            )
            logger.info(f"Saltato (gia' presente): {kba_display}")
            skipped += 1
            continue

        # Parsing
        try:
            record = parse_batch_file(file_path)
        except Exception as exc:
            console.print(
                f"{prefix} [cyan]{kba_display:<20}[/cyan] [bold red]-> ERRORE[/bold red]  ({exc})"
            )
            logger.error(f"Errore parsing {file_path.name}: {exc}")
            errors += 1
            continue

        level = record.get("risk_level", "")
        score = record.get("risk_score", 0.0)

        if dry_run:
            action = "[yellow]-> dry-run[/yellow]"
            console.print(f"{prefix} [cyan]{kba_display:<20}[/cyan] {action}   ({level}, {score})")
            indexed += 1
            continue

        # Scrittura
        try:
            if already_exists and force:
                logger.warning(f"Sovrascrittura forzata: {kba_display}")
            write_record(record)
            console.print(
                f"{prefix} [cyan]{kba_display:<20}[/cyan] "
                f"[green]-> ok[/green]      ({level}, {score})"
            )
            indexed += 1
        except Exception as exc:
            console.print(
                f"{prefix} [cyan]{kba_display:<20}[/cyan] "
                f"[bold red]-> ERRORE[/bold red]  (scrittura: {exc})"
            )
            logger.error(f"Errore scrittura {kba_display}: {exc}")
            errors += 1

    # Riepilogo
    console.print("")
    console.print(
        f"Completato: [green]{indexed}[/green] indicizzati, "
        f"[yellow]{skipped}[/yellow] saltati, "
        f"[red]{errors}[/red] errori"
    )

    if not dry_run:
        total_records = rebuild_index()
        console.print(f"Catalogo: [bold]{total_records}[/bold] record totali")

    if errors > 0:
        raise typer.Exit(code=1)


# ---------------------------------------------------------------------------
# Comando: list
# ---------------------------------------------------------------------------


@app.command(name="list")
def cmd_list(
    limit: int = typer.Option(50, "--limit", "-n", help="Numero max record."),
    sort: SortField = typer.Option(SortField.score, "--sort", help="Campo ordinamento."),
) -> None:
    """Elenca i record del catalogo."""
    if not INDEX_FILE.exists():
        console.print("[yellow]Catalogo non inizializzato. Esegui prima 'index'.[/yellow]")
        return

    try:
        index_data: dict[str, Any] = yaml.safe_load(INDEX_FILE.read_text(encoding="utf-8")) or {}
    except Exception as exc:
        console.print(f"[bold red]Errore lettura index.yaml:[/bold red] {exc}")
        raise typer.Exit(code=1)

    entries: list[dict[str, Any]] = index_data.get("entries", [])

    if not entries:
        console.print("[yellow]Nessun record nel catalogo.[/yellow]")
        return

    # Ordinamento
    sort_key = sort.value
    reverse = True  # default: decrescente

    if sort_key == "id":
        entries = sorted(entries, key=lambda e: str(e.get("id", "")), reverse=False)
    elif sort_key == "score":
        entries = sorted(entries, key=lambda e: float(e.get("score", 0.0)), reverse=reverse)
    elif sort_key == "level":
        level_order = {
            "critical": 0,
            "warning": 1,
            "advisory": 2,
            "informational": 3,
            "negligible": 4,
        }
        entries = sorted(
            entries,
            key=lambda e: level_order.get(str(e.get("level", "")).lower(), 99),
        )

    # Limite
    if limit and limit > 0:
        entries = entries[:limit]

    table = Table(title=f"Catalogo KBA ({len(entries)} record mostrati)")
    table.add_column("#", justify="right", style="dim")
    table.add_column("ID", style="cyan", no_wrap=True)
    table.add_column("Livello", justify="center")
    table.add_column("Score", justify="right", style="bold white")
    table.add_column("Tipo", style="dim")
    table.add_column("Titolo", style="white")

    level_colors = {
        "critical": "[bold red]",
        "warning": "[bold yellow]",
        "advisory": "[bold cyan]",
        "informational": "[dim]",
        "negligible": "[dim]",
    }

    for i, entry in enumerate(entries, 1):
        level = str(entry.get("level", ""))
        color = level_colors.get(level.lower(), "")
        level_display = f"{color}{level}[/]" if color else level

        table.add_row(
            str(i),
            str(entry.get("id", "")),
            level_display,
            str(entry.get("score", "")),
            str(entry.get("type", "")),
            str(entry.get("title", "")) or "—",
        )

    console.print(table)


# ---------------------------------------------------------------------------
# Comando: stats
# ---------------------------------------------------------------------------


@app.command()
def stats() -> None:
    """Statistiche aggregate del catalogo."""
    if not INDEX_FILE.exists():
        console.print("[yellow]Catalogo non inizializzato. Esegui prima 'index'.[/yellow]")
        return

    try:
        index_data: dict[str, Any] = yaml.safe_load(INDEX_FILE.read_text(encoding="utf-8")) or {}
    except Exception as exc:
        console.print(f"[bold red]Errore lettura index.yaml:[/bold red] {exc}")
        raise typer.Exit(code=1)

    total = index_data.get("total_entries", 0)
    if total == 0:
        console.print("[yellow]Nessun record nel catalogo.[/yellow]")
        return

    dist: dict[str, int] = index_data.get("risk_distribution", {})
    updated = index_data.get("catalog_updated", "N/D")

    # Calcola score medio dai record
    entries: list[dict[str, Any]] = index_data.get("entries", [])
    scores = [float(e["score"]) for e in entries if "score" in e]
    avg_score = sum(scores) / len(scores) if scores else 0.0
    max_score = max(scores) if scores else 0.0
    min_score = min(scores) if scores else 0.0

    table = Table(title="Statistiche catalogo KBA")
    table.add_column("Metrica", style="cyan")
    table.add_column("Valore", justify="right", style="bold white")

    table.add_row("Ultimo aggiornamento", updated)
    table.add_row("Record totali", str(total))
    table.add_row("", "")
    table.add_row("  Critical", f"[bold red]{dist.get('critical', 0)}[/bold red]")
    table.add_row("  Warning", f"[bold yellow]{dist.get('warning', 0)}[/bold yellow]")
    table.add_row("  Advisory", f"[bold cyan]{dist.get('advisory', 0)}[/bold cyan]")
    table.add_row("  Informational", str(dist.get("informational", 0)))
    table.add_row("  Negligible", str(dist.get("negligible", 0)))
    table.add_row("", "")
    table.add_row("Score medio", f"{avg_score:.2f}")
    table.add_row("Score massimo", f"{max_score:.2f}")
    table.add_row("Score minimo", f"{min_score:.2f}")

    console.print(table)
