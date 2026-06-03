"""
Entry point CLI per il tool kba_resolver.

Legge un file Excel DeltaV, naviga ricorsivamente i fix_reference di ogni KBA
e produce una mappa delle dipendenze documentali con stato di presenza.

Utilizzo:
  python -m tools.kba_resolver resolve Inbox/KnowledgeBaseArticles.xlsx
  python -m tools.kba_resolver resolve Inbox/KnowledgeBaseArticles.xlsx --max-depth 2
  python -m tools.kba_resolver resolve Inbox/KnowledgeBaseArticles.xlsx --verbose
"""

from __future__ import annotations

import sys
from pathlib import Path
from typing import Any

import openpyxl
import typer
from loguru import logger
from rich.console import Console
from tools.kba_resolver.config import LOG_FILE, PROJECT_ROOT
from tools.kba_resolver.resolver import resolve_dependencies

console = Console(highlight=False)

app = typer.Typer(
    name="kba_resolver",
    help="Mappa le dipendenze documentali KBA navigando i fix_reference.",
    no_args_is_help=True,
)


# ---------------------------------------------------------------------------
# Configurazione logging
# ---------------------------------------------------------------------------


def _setup_logging(verbose: bool = False) -> None:
    """
    Configura loguru: handler su file + stderr.

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
    """Risolve le dipendenze documentali KBA per il Team Olimpo."""
    _setup_logging(verbose)


# ---------------------------------------------------------------------------
# Utilita' lettura Excel input
# ---------------------------------------------------------------------------


def _read_deltav_excel(path: Path) -> tuple[list[str], list[dict[str, Any]]]:
    """
    Legge il file Excel DeltaV e restituisce headers + righe come dizionari.

    Args:
        path: Path al file .xlsx di input.

    Returns:
        Tupla (headers, rows) dove headers e' la lista delle intestazioni
        e rows e' la lista di dizionari {header: valore}.

    Raises:
        ValueError: Se il file non ha un foglio attivo o e' vuoto.
        OSError: Se il file non e' leggibile.
    """
    wb = openpyxl.load_workbook(path, read_only=True, data_only=True)
    ws = wb.active
    if ws is None:
        raise ValueError(f"Nessun foglio attivo nel file: {path.name}")

    rows_iter = ws.iter_rows(values_only=True)

    try:
        raw_headers = next(rows_iter)
    except StopIteration:
        raise ValueError(f"File vuoto: {path.name}")

    headers = [str(h).strip() if h is not None else "" for h in raw_headers]

    rows: list[dict[str, Any]] = []
    for raw_row in rows_iter:
        if all(v is None or str(v).strip() == "" for v in raw_row):
            continue
        row_dict: dict[str, Any] = {}
        for col_idx, header in enumerate(headers):
            value = raw_row[col_idx] if col_idx < len(raw_row) else None
            row_dict[header] = value
        rows.append(row_dict)

    wb.close()
    logger.debug(f"Lette {len(rows)} righe da {path.name}")
    return headers, rows


# ---------------------------------------------------------------------------
# Risoluzione path input
# ---------------------------------------------------------------------------


def _resolve_input(raw: Path) -> Path:
    """
    Risolve il path di input: se relativo, lo considera rispetto a PROJECT_ROOT.

    Args:
        raw: Path come fornito dall'utente.

    Returns:
        Path assoluto risolto.
    """
    if raw.is_absolute():
        return raw
    candidate = PROJECT_ROOT / raw
    if candidate.exists():
        return candidate
    return raw


# ---------------------------------------------------------------------------
# Stampa ad albero dipendenze
# ---------------------------------------------------------------------------


def _print_tree(kba_ids: list[str], tree: dict[str, list[str]]) -> None:
    """
    Stampa le dipendenze in formato ad albero per le KBA di input.

    Formato:
      KBA NK-2400-0150  ->  NK-1900-0840  ->  NK-1800-0210
                                         ->  NK-1800-0315
      KBA NK-2400-0180  ->  NK-2000-0044  (nessun riferimento)
      KBA NK-2400-0200  ->  (nessun fix reference)

    Args:
        kba_ids: Lista ordinata delle KBA di input.
        tree: Mappa {kba_id: [dep1, dep2, ...]} costruita da resolve_dependencies.
    """
    for kba in kba_ids:
        deps = tree.get(kba, [])
        if not deps:
            console.print(f"KBA [cyan]{kba}[/cyan]  ->  [dim](nessun fix reference)[/dim]")
            continue

        # Prefisso per le righe successive della stessa KBA (allineamento)
        prefix = " " * (4 + len(kba) + 2)  # "KBA " + kba + "  "

        for i, dep in enumerate(deps):
            sub_deps = tree.get(dep, [])

            if i == 0:
                line_start_plain = f"KBA {kba}  ->  {dep}"
                line_start_rich = f"KBA [cyan]{kba}[/cyan]  ->  [cyan]{dep}[/cyan]"
            else:
                line_start_plain = f"{prefix}->  {dep}"
                line_start_rich = f"{prefix}->  [cyan]{dep}[/cyan]"

            if not sub_deps:
                # Nodo foglia: nessun riferimento trovato (record assente o fix_reference vuoto)
                record_absent = dep not in tree
                note = "  [dim](nessun riferimento)[/dim]" if record_absent else ""
                console.print(f"{line_start_rich}{note}")
            else:
                # Il nodo ha a sua volta dipendenze: le mostriamo in catena
                sub_prefix = " " * (len(line_start_plain) + 2)
                for j, sub_dep in enumerate(sub_deps):
                    if j == 0:
                        console.print(f"{line_start_rich}  ->  [cyan]{sub_dep}[/cyan]")
                    else:
                        console.print(f"{sub_prefix}->  [cyan]{sub_dep}[/cyan]")


# ---------------------------------------------------------------------------
# Comando principale: resolve
# ---------------------------------------------------------------------------


@app.command()
def resolve(
    input: Path = typer.Argument(
        ...,
        help="File Excel DeltaV (.xlsx) da cui estrarre le KBA.",
        exists=False,  # gestione manuale per path relativi a PROJECT_ROOT
    ),
    max_depth: int = typer.Option(
        3,
        "--max-depth",
        "-d",
        help="Profondita' massima di navigazione BFS dei fix_reference (default: 3).",
        min=1,
        max=10,
    ),
) -> None:
    """
    Legge le KBA dal file Excel DeltaV e mappa le dipendenze documentali.

    Naviga ricorsivamente i fix_reference fino a MAX_DEPTH livelli e verifica
    quali documenti dipendenti sono gia' presenti in lib/documents/.

    Exit code 0 se nessun documento mancante, 1 se ci sono mancanti.
    """
    # Risolvi path
    resolved = _resolve_input(input)
    if not resolved.exists():
        logger.error(f"File non trovato: {input}")
        console.print(f"[bold red]Errore:[/bold red] file non trovato: {input}", stderr=True)
        raise typer.Exit(1)

    # Valida estensione
    if resolved.suffix.lower() != ".xlsx":
        logger.error(f"File non valido (atteso .xlsx): {resolved.name}")
        console.print(
            f"[bold red]Errore:[/bold red] il file deve essere .xlsx, ricevuto: {resolved.suffix}",
            stderr=True,
        )
        raise typer.Exit(1)

    logger.debug(f"Input risolto: {resolved}")
    logger.debug(f"Max depth: {max_depth}")

    # Lettura Excel
    try:
        _, rows = _read_deltav_excel(resolved)
    except (ValueError, OSError) as exc:
        logger.error(f"Errore lettura Excel: {exc}")
        console.print(f"[bold red]Errore:[/bold red] {exc}", stderr=True)
        raise typer.Exit(1)

    # Estrai KBA Number unici (ordine preservato)
    kba_ids: list[str] = []
    seen: set[str] = set()
    for row in rows:
        kba = str(row.get("KBA Number") or "").strip().upper()
        if kba and kba not in seen:
            seen.add(kba)
            kba_ids.append(kba)

    if not kba_ids:
        console.print("[yellow]Nessuna KBA trovata nel file Excel.[/yellow]", stderr=True)
        raise typer.Exit(1)

    logger.debug(f"KBA uniche estratte: {len(kba_ids)}")

    # Risoluzione dipendenze
    result = resolve_dependencies(kba_ids, max_depth=max_depth)
    tree: dict[str, list[str]] = result["tree"]
    present: set[str] = result["present"]
    missing: set[str] = result["missing"]
    all_deps: set[str] = result["all_deps"]

    # --- Output ---

    if not all_deps:
        console.print(
            "[green]Nessuna dipendenza trovata -- tutti i documenti necessari sono presenti.[/green]"
        )
        raise typer.Exit(0)

    # Albero dipendenze
    _print_tree(kba_ids, tree)
    console.print("")

    # Riepilogo documenti
    total = len(all_deps)
    console.print(f"Documenti necessari: [bold]{total}[/bold]")

    # Ordine: prima presenti, poi mancanti — alfabetico dentro ogni gruppo
    for slug in sorted(present):
        console.print(f"  [green]OK[/green]  [dim]{slug:<30}[/dim]  presente in lib/documents/")
    for slug in sorted(missing):
        console.print(f"  [red]NO[/red]  [cyan]{slug:<30}[/cyan]  [bold red]MANCANTE[/bold red]")

    # Azioni richieste
    if missing:
        console.print("")
        missing_list = ", ".join(sorted(missing))
        console.print("[bold]Azioni richieste prima del merge:[/bold]")
        console.print(f"  Aggiungi PDF e converti: [cyan]{missing_list}[/cyan]")
        raise typer.Exit(1)

    raise typer.Exit(0)
