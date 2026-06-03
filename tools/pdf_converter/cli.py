"""
Entry point CLI per il tool pdf_converter.

Comandi disponibili:
  init          Inizializza il database SQLite
  convert       Converte un singolo file PDF
  convert-all   Converte tutti i PDF nuovi nella inbox
  search        Cerca nei documenti indicizzati (FTS5)
  list          Elenca i documenti indicizzati
  stats         Mostra statistiche aggregate
  summarize     Genera pagine wiki per documenti convertiti (Auto-Summarizer V1+V2)

Utilizzo:
  python -m tools.pdf_converter <comando> [opzioni]
"""

from __future__ import annotations

import sys
from enum import Enum
from pathlib import Path
from typing import Optional

import typer
from loguru import logger
from rich.console import Console
from rich.progress import BarColumn, Progress, SpinnerColumn, TaskProgressColumn, TextColumn
from rich.table import Table

from tools.pdf_converter.config import paths as default_paths
from tools.pdf_converter.converter import convert_pdf
from tools.pdf_converter.indexer import DocumentIndexer
from tools.pdf_converter.models import ConversionResult
from tools.pdf_converter.post_processor import post_process
from tools.pdf_converter.utils import calculate_file_hash, slugify

# ---------------------------------------------------------------------------
# Console Rich condivisa
# ---------------------------------------------------------------------------
console = Console()

app = typer.Typer(
    name="pdf_converter",
    help="Converte PDF in Markdown per il vault Obsidian.",
    no_args_is_help=True,
)


class SortField(str, Enum):
    converted_at = "converted_at"
    filename = "filename"
    num_pages = "num_pages"
    file_size_bytes = "file_size_bytes"
    title = "title"


class StatusFilter(str, Enum):
    completed = "completed"
    error = "error"


# ---------------------------------------------------------------------------
# Configurazione logging
# ---------------------------------------------------------------------------


def _setup_logging(verbose: bool = False) -> None:
    """
    Configura loguru: rimuove l'handler default e ne aggiunge uno su file
    e uno su stderr (solo WARNING+ in modalita' normale, DEBUG se verbose).

    Args:
        verbose: Se True, mostra anche i messaggi DEBUG su stderr
    """
    logger.remove()

    # Log su file (tutti i livelli)
    log_level_file = "DEBUG"
    log_path = default_paths.log_file
    log_path.parent.mkdir(parents=True, exist_ok=True)
    logger.add(
        str(log_path),
        level=log_level_file,
        rotation="5 MB",
        retention="30 days",
        encoding="utf-8",
        format="{time:YYYY-MM-DD HH:mm:ss} | {level:<8} | {name}:{line} — {message}",
    )

    # Log su stderr (livello dipendente dalla modalita')
    log_level_console = "DEBUG" if verbose else "WARNING"
    logger.add(
        sys.stderr,
        level=log_level_console,
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
    """Tool di conversione PDF -> Markdown per il PKM del Team Olimpo."""
    _setup_logging(verbose)


# ---------------------------------------------------------------------------
# Logica di conversione condivisa
# ---------------------------------------------------------------------------


def _run_conversion(
    pdf_path: Path,
    force: bool,
    indexer: DocumentIndexer,
    no_wiki: bool = False,
) -> ConversionResult:
    """
    Esegue la conversione completa di un PDF: convert -> post_process -> wiki -> index.

    Controlla idempotenza (salta se gia' convertito e non modificato, a meno di --force).

    Args:
        pdf_path: Path assoluto al file PDF
        force: Se True, riconverte anche se gia' presente nel DB
        indexer: Istanza del DocumentIndexer da usare
        no_wiki: Se True, salta la generazione automatica della wiki page

    Returns:
        ConversionResult con lo stato finale dell'operazione
    """
    slug = slugify(pdf_path.stem)

    # Calcola hash per rilevare modifiche
    file_hash = ""
    try:
        file_hash = calculate_file_hash(pdf_path)
    except Exception as exc:
        logger.warning(f"Impossibile calcolare hash per {pdf_path.name}: {exc}")

    # Controllo idempotenza: salta se gia' convertito con stesso hash
    if not force and indexer.is_already_converted(slug, file_hash):
        logger.info(f"Saltato (non modificato): {pdf_path.name}. Usa --force per riconvertire.")
        from tools.pdf_converter.models import DocumentMetadata  # noqa: PLC0415

        metadata = DocumentMetadata(
            filename=pdf_path.name,
            slug=slug,
            pdf_path=pdf_path,
            num_pages=1,
            file_size_bytes=pdf_path.stat().st_size if pdf_path.exists() else 0,
            file_hash=file_hash,
        )
        return ConversionResult(metadata=metadata, status="skipped")

    # Conversione
    result = convert_pdf(pdf_path)

    # Post-processing (anche in caso di errore parziale, se il file MD esiste)
    if result.success:
        result = post_process(result)

    # Generazione wiki page (dopo post_process, prima dell'indicizzazione)
    if not no_wiki and result.success and result.md_path is not None:
        from tools.pdf_converter.auto_summarizer import generate_wiki_page  # noqa: PLC0415

        try:
            wiki_result = generate_wiki_page(result.md_path)
            if wiki_result.get("status") == "created":
                logger.info(f"Wiki page creata: {wiki_result['slug']}")
        except Exception as exc:
            logger.warning(f"Auto-summarizer skipped for {slug}: {exc}")

    # Indicizzazione nel DB (anche gli errori vengono registrati)
    indexer.index_document(result)

    return result


# ---------------------------------------------------------------------------
# Comando: init
# ---------------------------------------------------------------------------


@app.command(name="init")
def cmd_init() -> None:
    """Inizializza database e cartelle."""
    console.print("[bold cyan]Inizializzazione pdf_converter...[/bold cyan]")

    # Crea le cartelle
    for folder in [
        default_paths.inbox,
        default_paths.output,
        default_paths.assets,
        default_paths.database.parent,
    ]:
        folder.mkdir(parents=True, exist_ok=True)
        console.print(f"  Cartella: [green]{folder}[/green]")

    # Inizializza il DB
    indexer = DocumentIndexer()
    indexer.init_db()
    console.print(f"  Database: [green]{default_paths.database}[/green]")

    console.print("\n[bold green]Pronto.[/bold green]")


# ---------------------------------------------------------------------------
# Comando: convert
# ---------------------------------------------------------------------------


@app.command(name="convert")
def cmd_convert(
    pdf_path: Path = typer.Argument(..., help="Path al file PDF.", exists=True),
    force: bool = typer.Option(False, "--force", "-f", help="Riconverte se già presente."),
    no_wiki: bool = typer.Option(
        False, "--no-wiki", help="Salta la generazione automatica della wiki page."
    ),
) -> None:
    """Converte un singolo PDF in Markdown."""
    resolved = pdf_path.resolve()

    if resolved.suffix.lower() != ".pdf":
        console.print(f"[bold red]Errore:[/bold red] Il file non e' un PDF: {resolved}")
        raise typer.Exit(code=1)

    indexer = DocumentIndexer()
    indexer.init_db()

    console.print(f"Conversione: [bold]{resolved.name}[/bold]")

    result = _run_conversion(resolved, force=force, indexer=indexer, no_wiki=no_wiki)

    if result.status == "skipped":
        console.print(
            f"[yellow]Saltato:[/yellow] {resolved.name} e' gia' nel database. "
            "Usa [bold]--force[/bold] per riconvertire."
        )
        return

    if result.success:
        console.print(
            f"[green]Completato:[/green] {result.md_path} "
            f"({result.num_images} immagini, {result.processing_time_seconds:.2f}s)"
        )
    else:
        console.print(f"[bold red]Errore:[/bold red] {result.error_message}")
        raise typer.Exit(code=1)


# ---------------------------------------------------------------------------
# Comando: convert-all
# ---------------------------------------------------------------------------


@app.command(name="convert-all")
def cmd_convert_all(
    inbox_path: Path = typer.Option(
        None,
        "--inbox",
        "-i",
        help="Cartella sorgente PDF (default: Inbox/).",
    ),
    force: bool = typer.Option(False, "--force", "-f", help="Riconverte tutti i PDF."),
    no_wiki: bool = typer.Option(
        False, "--no-wiki", help="Salta la generazione automatica della wiki page."
    ),
) -> None:
    """Converte tutti i PDF nuovi nella inbox (o in una cartella specificata con --inbox)."""
    if inbox_path is not None:
        inbox = (
            inbox_path if inbox_path.is_absolute() else (default_paths.project_root / inbox_path)
        )
    else:
        inbox = default_paths.inbox

    if not inbox.exists():
        console.print(f"[bold red]Errore:[/bold red] Cartella inbox non trovata: {inbox}")
        raise typer.Exit(code=1)

    # Trova tutti i PDF nella inbox (non ricorsivo di default)
    pdf_files = sorted(inbox.glob("*.pdf"))

    if not pdf_files:
        console.print(f"[yellow]Nessun PDF trovato in:[/yellow] {inbox}")
        return

    indexer = DocumentIndexer()
    indexer.init_db()

    # Filtra i gia' convertiti (se non --force)
    if not force:
        to_convert = []
        for p in pdf_files:
            slug = slugify(p.stem)
            file_hash = ""
            try:
                file_hash = calculate_file_hash(p)
            except Exception as exc:
                logger.warning(f"Impossibile calcolare hash per {p.name}: {exc}")
            if not indexer.is_already_converted(slug, file_hash):
                to_convert.append(p)
        skipped = len(pdf_files) - len(to_convert)
    else:
        to_convert = pdf_files
        skipped = 0

    if not to_convert:
        console.print(
            f"[yellow]Tutti i {len(pdf_files)} PDF sono gia' stati convertiti.[/yellow] "
            "Usa [bold]--force[/bold] per riconvertire."
        )
        return

    console.print(
        f"PDF da convertire: [bold]{len(to_convert)}[/bold] (saltati gia' presenti: {skipped})"
    )

    # Contatori risultati
    completed = 0
    errors = 0
    error_list: list[tuple[str, str]] = []

    # Progress bar con Rich
    with Progress(
        SpinnerColumn(),
        TextColumn("[progress.description]{task.description}"),
        BarColumn(),
        TaskProgressColumn(),
        console=console,
    ) as progress:
        task = progress.add_task("Conversione batch...", total=len(to_convert))

        for pdf_path in to_convert:
            progress.update(task, description=f"[cyan]{pdf_path.name[:50]}[/cyan]")

            result = _run_conversion(pdf_path, force=force, indexer=indexer, no_wiki=no_wiki)

            if result.success:
                completed += 1
            elif result.status != "skipped":
                errors += 1
                error_list.append((pdf_path.name, result.error_message or "Errore sconosciuto"))
                logger.error(f"Fallito: {pdf_path.name} — {result.error_message}")

            progress.advance(task)

    # Riepilogo finale
    console.print("\n[bold]Riepilogo conversione:[/bold]")
    console.print(f"  Completati:  [green]{completed}[/green]")
    console.print(f"  Errori:      [red]{errors}[/red]")

    if error_list:
        console.print("\n[bold red]Documenti con errori:[/bold red]")
        for filename, msg in error_list:
            console.print(f"  • {filename}: {msg}")

    if errors > 0:
        raise typer.Exit(code=1)


# ---------------------------------------------------------------------------
# Comando: search
# ---------------------------------------------------------------------------


@app.command(name="search")
def cmd_search(
    query: str = typer.Argument(..., help="Testo da cercare (full-text)."),
    limit: int = typer.Option(20, "--limit", "-n", help="Numero max risultati."),
) -> None:
    """Ricerca full-text nei documenti indicizzati."""
    indexer = DocumentIndexer()
    results = indexer.search(query, limit=limit)

    if not results:
        console.print(f"[yellow]Nessun risultato per:[/yellow] {query}")
        return

    table = Table(title=f"Risultati per: '{query}' ({len(results)} trovati)")
    table.add_column("Filename", style="cyan", no_wrap=True)
    table.add_column("Titolo", style="white")
    table.add_column("Autore", style="dim")
    table.add_column("Pagine", justify="right")
    table.add_column("Convertito", style="dim")

    for doc in results:
        table.add_row(
            doc.get("filename", ""),
            doc.get("title", "") or "—",
            doc.get("author", "") or "—",
            str(doc.get("num_pages", "")),
            (doc.get("converted_at", "") or "")[:16],
        )

    console.print(table)


# ---------------------------------------------------------------------------
# Comando: list
# ---------------------------------------------------------------------------


@app.command(name="list")
def cmd_list(
    limit: int = typer.Option(50, "--limit", "-n", help="Numero max documenti."),
    sort: SortField = typer.Option(SortField.converted_at, "--sort", help="Campo ordinamento."),
    asc: bool = typer.Option(False, "--asc", help="Ordinamento crescente (default: decrescente)."),
    status: Optional[StatusFilter] = typer.Option(None, "--status", help="Filtro stato."),
) -> None:
    """Elenca i documenti nel database."""
    indexer = DocumentIndexer()
    docs = indexer.list_documents(
        sort_by=sort.value,
        ascending=asc,
        limit=limit,
        status_filter=status.value if status else None,
    )

    if not docs:
        console.print("[yellow]Nessun documento nel database.[/yellow]")
        return

    table = Table(title=f"Documenti indicizzati ({len(docs)} mostrati)")
    table.add_column("#", justify="right", style="dim")
    table.add_column("Filename", style="cyan", no_wrap=True)
    table.add_column("Titolo", style="white")
    table.add_column("Pagine", justify="right")
    table.add_column("Immagini", justify="right")
    table.add_column("Status", justify="center")
    table.add_column("Convertito", style="dim")

    for i, doc in enumerate(docs, 1):
        status_val = doc.get("status", "")
        status_display = (
            "[green]OK[/green]"
            if status_val == "completed"
            else "[red]ERR[/red]"
            if status_val == "error"
            else "[yellow]SKP[/yellow]"
        )
        table.add_row(
            str(i),
            doc.get("filename", ""),
            doc.get("title", "") or "—",
            str(doc.get("num_pages", "")),
            str(doc.get("num_images", 0)),
            status_display,
            (doc.get("converted_at", "") or "")[:16],
        )

    console.print(table)


# ---------------------------------------------------------------------------
# Comando: stats
# ---------------------------------------------------------------------------


@app.command()
def stats() -> None:
    """Statistiche aggregate sui documenti."""
    indexer = DocumentIndexer()
    stats_data = indexer.get_stats()

    if not stats_data or stats_data.get("total_documents", 0) == 0:
        console.print("[yellow]Nessun documento nel database.[/yellow]")
        return

    table = Table(title="Statistiche pdf_converter")
    table.add_column("Metrica", style="cyan")
    table.add_column("Valore", justify="right", style="bold white")

    table.add_row("Documenti totali", str(stats_data.get("total_documents", 0)))
    table.add_row("  Completati", f"[green]{stats_data.get('completed', 0)}[/green]")
    table.add_row("  Errori", f"[red]{stats_data.get('errors', 0)}[/red]")
    table.add_row("Pagine totali", str(stats_data.get("total_pages", 0)))
    table.add_row("Immagini totali", str(stats_data.get("total_images", 0)))
    table.add_row(
        "Tempo medio (s)",
        f"{stats_data.get('avg_processing_time', 0.0):.2f}",
    )
    table.add_row(
        "Dimensione totale PDF (MB)",
        f"{stats_data.get('total_size_mb', 0.0):.1f}",
    )

    console.print(table)


# ---------------------------------------------------------------------------
# Comando: summarize
# ---------------------------------------------------------------------------


@app.command(name="summarize")
def cmd_summarize(
    slug: str = typer.Argument(None, help="Slug del documento da processare (default: nessuno)."),
    all_docs: bool = typer.Option(False, "--all", help="Processa tutti i documenti convertiti."),
    force: bool = typer.Option(False, "--force", "-f", help="Sovrascrivi pagine wiki esistenti."),
    dry_run: bool = typer.Option(False, "--dry-run", "-n", help="Mostra output senza scrivere."),
) -> None:
    """Genera pagine wiki per documenti convertiti (Auto-Summarizer V1+V2)."""
    from tools.pdf_converter.auto_summarizer import (  # noqa: PLC0415
        generate_all_wiki_pages,
        generate_wiki_page,
    )
    from tools.pdf_converter.config import paths as converter_paths  # noqa: PLC0415,I001

    if not slug and not all_docs:
        console.print(
            "[bold red]Errore:[/bold red] Specifica uno slug o "
            "usa --all per processare tutti i documenti."
        )
        raise typer.Exit(code=2)

    if all_docs:
        console.print("[bold cyan]Generazione wiki pages per tutti i documenti...[/bold cyan]")
        if dry_run:
            console.print("[yellow]Modalità dry-run: nessun file verrà scritto[/yellow]")

        results = generate_all_wiki_pages(force=force, dry_run=dry_run)

        created = sum(1 for r in results if r.get("status") == "created")
        skipped = sum(1 for r in results if r.get("status") == "skipped")
        dry_run_count = sum(1 for r in results if r.get("status") == "dry_run")
        errors = sum(1 for r in results if r.get("status") == "error")

        console.print("\n[bold]Riepilogo:[/bold]")
        if dry_run:
            console.print(f"  Dry-run:     [cyan]{dry_run_count}[/cyan]")
        else:
            console.print(f"  Create:      [green]{created}[/green]")
            console.print(f"  Saltate:     [yellow]{skipped}[/yellow]")
        console.print(f"  Errori:      [red]{errors}[/red]")

        if errors > 0:
            error_list = [r for r in results if r.get("status") == "error"]
            console.print("\n[bold red]Errori:[/bold red]")
            for err in error_list:
                msg = err.get("error", "errore sconosciuto")
                console.print(f"  \u2022 {err.get('slug')}: {msg}")
            raise typer.Exit(code=1)

        return

    # Slug singolo
    doc_path = converter_paths.output / f"{slug}.md"
    if not doc_path.exists():
        console.print(f"[bold red]Errore:[/bold red] Documento non trovato: {doc_path}")
        raise typer.Exit(code=1)

    console.print(f"Processamento: [bold]{slug}[/bold]")
    result = generate_wiki_page(doc_path, force=force, dry_run=dry_run)

    status_display = {
        "created": "[green]Creata[/green]",
        "skipped": "[yellow]Saltata (gi\u00e0 esistente)[/yellow]",
        "dry_run": "[cyan]Dry-run[/cyan]",
        "error": "[red]Errore[/red]",
    }
    st = result.get("status", "unknown")
    console.print(f"  Status:  {status_display.get(st, st)}")
    console.print(f"  Wiki:    {result.get('wiki_path', '\u2014')}")
    if result.get("error"):
        console.print(f"  Errore:  {result['error']}")
        raise typer.Exit(code=1)
