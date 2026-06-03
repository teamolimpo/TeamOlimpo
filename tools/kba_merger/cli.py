"""
Entry point CLI per il tool kba_merger.

Comandi disponibili:
  merge   Legge export DeltaV, esegue merge + enrichment, produce Excel output
  learn   Legge Excel revisionato e costruisce/aggiorna il prontuario KBA
  gap     Pre-check KBA mancanti: classifica ogni KBA come ok / da_analizzare / da_convertire

Utilizzo:
  python -m tools.kba_merger merge Inbox/KnowledgeBaseArticles_260325_155224.xlsx
  python -m tools.kba_merger merge <input.xlsx> --output "Owner's Inbox/output.xlsx"
  python -m tools.kba_merger merge <input.xlsx> --no-enrich
  python -m tools.kba_merger gap Inbox/KnowledgeBaseArticles_260325_155224.xlsx
"""

from __future__ import annotations

import sys
from datetime import date
from pathlib import Path
from typing import Any

import openpyxl
import typer
from loguru import logger
from rich.console import Console

from tools.kba_merger.config import LOG_FILE, OUTPUT_DIR, PROJECT_ROOT

console = Console()

app = typer.Typer(
    name="kba_merger",
    help="Merge, enrichment e gap analysis KBA DeltaV.",
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
    """Merge e gap check dell'export DeltaV KBA per il Team Olimpo."""
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
        ValueError: Se il file non ha un foglio attivo o header mancanti.
        OSError: Se il file non e' leggibile.
    """
    wb = openpyxl.load_workbook(path, read_only=True, data_only=True)
    ws = wb.active
    if ws is None:
        raise ValueError(f"Nessun foglio attivo nel file: {path.name}")

    rows_iter = ws.iter_rows(values_only=True)

    # Prima riga = header
    try:
        raw_headers = next(rows_iter)
    except StopIteration:
        raise ValueError(f"File vuoto: {path.name}")

    headers = [str(h).strip() if h is not None else "" for h in raw_headers]

    rows: list[dict[str, Any]] = []
    for raw_row in rows_iter:
        # Salta righe completamente vuote
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
    Risolve il path di input relativo rispetto a PROJECT_ROOT.

    Args:
        raw: Path dall'argomento CLI.

    Returns:
        Path assoluto risolto.
    """
    if not raw.is_absolute():
        raw = PROJECT_ROOT / raw
    return raw.resolve()


# ---------------------------------------------------------------------------
# Helper provider
# ---------------------------------------------------------------------------


def _init_provider(provider_name: str, model_override: str | None) -> Any:
    """
    Istanzia il provider LLM richiesto leggendo la API key dal .env.

    Args:
        provider_name: Nome del provider (es. "grok", "gemini").
        model_override: Modello override opzionale (passato poi a .chat()).

    Returns:
        Istanza del provider.

    Raises:
        SystemExit(1): Se la API key non e' disponibile o il provider non esiste.
        ImportError: Se la dipendenza del provider non e' installata.
    """
    from tools.consulto.config import get_api_key
    from tools.consulto.providers import PROVIDERS

    provider_cls = PROVIDERS.get(provider_name)
    if provider_cls is None:
        available = ", ".join(PROVIDERS.keys())
        console.print(
            f"[bold red]Errore:[/bold red] Provider '{provider_name}' non riconosciuto. "
            f"Disponibili: {available}"
        )
        raise typer.Exit(code=1)

    api_key = get_api_key(provider_name)
    return provider_cls(api_key)


# ---------------------------------------------------------------------------
# Comando: merge
# ---------------------------------------------------------------------------


@app.command()
def merge(
    input: Path = typer.Argument(..., help="File Excel KBA_Guardian export.", exists=True),
    output: Path = typer.Option(None, "--output", "-o", help="Path output Excel."),
    no_enrich: bool = typer.Option(False, "--no-enrich", help="Disabilita enrichment."),
    no_ai: bool = typer.Option(
        False, "--no-ai", help="Disabilita AI enrichment per Suggested Notes."
    ),
    provider: str = typer.Option("grok", "--provider", help="Provider LLM per Suggested Notes."),
    model: str = typer.Option(None, "--model", help="Override modello LLM."),
) -> None:
    """Merge + enrichment: Excel con Suggested Note e Stefano's Notes."""
    from tools.kba_merger.enricher import enrich_rows
    from tools.kba_merger.merger import merge_rows
    from tools.kba_merger.writer import write_merge_excel

    input_path = _resolve_input(input)
    if input_path.suffix.lower() != ".xlsx":
        console.print(f"[bold red]Errore:[/bold red] Il file non e' un .xlsx: {input_path.name}")
        raise typer.Exit(code=1)

    # Lettura
    try:
        headers, raw_rows = _read_deltav_excel(input_path)
    except (ValueError, OSError) as exc:
        console.print(f"[bold red]Errore lettura file:[/bold red] {exc}")
        logger.error(f"Errore lettura {input_path}: {exc}")
        raise typer.Exit(code=1)

    input_count = len(raw_rows)

    # Merge
    try:
        merged = merge_rows(raw_rows, headers)
    except ValueError as exc:
        console.print(f"[bold red]Errore merge:[/bold red] {exc}")
        logger.error(f"Errore merge: {exc}")
        raise typer.Exit(code=1)

    merged_count = len(merged)

    # Enrichment (opzionale)
    in_catalog = 0
    total_unique = 0

    if not no_enrich:
        enriched, in_catalog, total_unique = enrich_rows(
            merged,
            use_ai=not no_ai,
            provider_name=provider,
            model=model,
        )
    else:
        enriched = [
            {
                **row,
                "Risk Score": "",
                "Risk Level": "",
                "Problem Type": "",
                "Workaround": "",
                "Fix Available": "",
                "Emerson Category": "",
                "FIS Notes": "",
                "Suggested Note": "",
            }
            for row in merged
        ]
        total_unique = len({r["KBA Number"] for r in merged})

    # Output path
    output_path: Path | None = None
    if output:
        raw_out = output
        if not raw_out.is_absolute():
            raw_out = PROJECT_ROOT / raw_out
        output_path = raw_out.resolve()

    # Scrittura
    try:
        out_file = write_merge_excel(enriched, output_path=output_path)
    except Exception as exc:
        console.print(f"[bold red]Errore scrittura Excel:[/bold red] {exc}")
        logger.exception(f"Errore scrittura Excel: {exc}")
        raise typer.Exit(code=1)

    # Report su stderr
    not_analyzed = total_unique - in_catalog
    pct = f"({in_catalog / total_unique * 100:.0f}%)" if total_unique else "(N/A)"
    sys.stderr.write(
        f"Righe input:                 {input_count}\n"
        f"Righe merged:                {merged_count}\n"
        f"KBA in catalogo:              {in_catalog} / {total_unique}  {pct}\n"
        f"KBA nel file non analizzate: {not_analyzed}\n"
        f"Output: {out_file}\n"
    )

    console.print(f"[green]Output:[/green] {out_file}")


# ---------------------------------------------------------------------------
# Comando: learn
# ---------------------------------------------------------------------------


@app.command()
def learn(
    input: Path = typer.Argument(..., help="File Excel revisionato.", exists=True),
    provider: str = typer.Option(None, "--provider", help="Provider LLM."),
    model: str = typer.Option(None, "--model", help="Override modello."),
) -> None:
    """Aggiorna il prontuario KBA da revisioni umane."""
    from tools.kba_merger.learner import run_learn

    input_path = _resolve_input(input)
    if input_path.suffix.lower() != ".xlsx":
        console.print(f"[bold red]Errore:[/bold red] Il file non e' un .xlsx: {input_path.name}")
        raise typer.Exit(code=1)

    # Provider opzionale per rules.md
    provider_instance = None
    if provider:
        try:
            provider_instance = _init_provider(provider, model)
        except (ImportError, SystemExit) as exc:
            console.print(f"[bold red]Errore provider:[/bold red] {exc}")
            raise typer.Exit(code=1)

    try:
        run_learn(input_xlsx=input_path, provider=provider_instance, model=model)
    except (ValueError, OSError) as exc:
        console.print(f"[bold red]Errore learn:[/bold red] {exc}")
        logger.exception(f"Errore learn: {exc}")
        raise typer.Exit(code=1)


# ---------------------------------------------------------------------------
# Comando: gap
# ---------------------------------------------------------------------------


@app.command()
def gap(
    input: Path = typer.Argument(..., help="File Excel KBA_Guardian export.", exists=True),
    recursive: bool = typer.Option(
        False, "--recursive", "-r", help="Espande check ricorsivo via fix_reference."
    ),
) -> None:
    """Gap check: classifica KBA mancanti nel catalogo."""
    from tools.kba_merger.gap import compute_gap
    from tools.kba_merger.writer import write_gap_excel, write_gap_txt

    input_path = _resolve_input(input)
    if input_path.suffix.lower() != ".xlsx":
        console.print(f"[bold red]Errore:[/bold red] Il file non e' un .xlsx: {input_path.name}")
        raise typer.Exit(code=1)

    # Lettura
    try:
        headers, raw_rows = _read_deltav_excel(input_path)
    except (ValueError, OSError) as exc:
        console.print(f"[bold red]Errore lettura file:[/bold red] {exc}")
        raise typer.Exit(code=1)

    # Gap check
    try:
        gap_rows = compute_gap(raw_rows, recursive=recursive)
    except Exception as exc:
        console.print(f"[bold red]Errore gap check:[/bold red] {exc}")
        logger.exception(f"Errore gap check: {exc}")
        raise typer.Exit(code=1)

    today = date.today().isoformat()

    # Scrittura report
    try:
        txt_path = write_gap_txt(gap_rows, today)
        xlsx_path = write_gap_excel(gap_rows, today)
    except Exception as exc:
        console.print(f"[bold red]Errore scrittura report:[/bold red] {exc}")
        logger.exception(f"Errore scrittura gap report: {exc}")
        raise typer.Exit(code=1)

    # Riepilogo
    direct_rows = [r for r in gap_rows if not r.get("referenced_by")]
    ref_rows = [r for r in gap_rows if r.get("referenced_by")]
    total = len(direct_rows)
    ok = sum(1 for r in direct_rows if r["stato"] == "ok")
    da_rianalizzare = sum(1 for r in direct_rows if r["stato"] == "da_rianalizzare")
    da_analizzare = sum(1 for r in direct_rows if r["stato"] == "da_analizzare")
    da_convertire = sum(1 for r in direct_rows if r["stato"] == "da_convertire")

    console.print(f"\n[bold]Gap Check - {today}[/bold]")
    console.print(f"  KBA nel file DeltaV:         {total}")
    console.print(f"  In catalogo (ok):            [green]{ok}[/green]")
    console.print(f"  Da rianalizzare:             [orange1]{da_rianalizzare}[/orange1]")
    console.print(f"  Da analizzare:               [yellow]{da_analizzare}[/yellow]")
    console.print(f"  Da convertire:               [red]{da_convertire}[/red]")

    if recursive and ref_rows:
        ref_mancanti = sum(1 for r in ref_rows if r["stato"] != "ok")
        console.print(f"\n  [bold]Referenziate (ricorsivo):[/bold]  {len(ref_rows)} trovate")
        console.print(f"  Di cui mancanti:             [red]{ref_mancanti}[/red]")
        for r in ref_rows:
            if r["stato"] != "ok":
                parents = ", ".join(r["referenced_by"])
                console.print(f"    [red]{r['kba_number']}[/red]  [{r['stato']}]  <- {parents}")
    elif recursive:
        console.print("\n  [green]Nessuna KBA referenziata mancante.[/green]")

    console.print(f"\n  Report TXT:   {txt_path}")
    console.print(f"  Report Excel: {xlsx_path}")
