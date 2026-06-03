"""Entry point CLI per kba_reporter."""

import sys
from datetime import date
from pathlib import Path

import typer
from loguru import logger
from rich.console import Console

from tools.kba_reporter.config import (
    PROJECT_ROOT,
    OWNERS_INBOX_DIR,
    HANDOFF_DIR,
    LOG_FILE,
    ANALYSIS_MAX_AGE_DAYS,
)
from tools.kba_reporter.classifier import load_excel, classify_rows
from tools.kba_reporter.patch_builder import build_patch_list
from tools.kba_reporter.brief_builder import build_wip_brief
from tools.kba_reporter.writer import write_patch_list, write_wip_brief, write_kba_discussion

app = typer.Typer(
    name="kba_reporter",
    help="Genera brief WIP e lista patch da export DeltaV.",
    no_args_is_help=True,
)


def _setup_logging(verbose: bool) -> None:
    logger.remove()
    level = "DEBUG" if verbose else "WARNING"
    logger.add(
        sys.stderr,
        level=level,
        format="<green>{time:HH:mm:ss}</green> | <level>{message}</level>",
    )
    logger.add(LOG_FILE, rotation="1 MB", retention=3, level="DEBUG")


@app.command()
def main(
    input: Path = typer.Argument(..., help="File Excel KBA_Guardian export.", exists=True),
    max_age: int = typer.Option(
        ANALYSIS_MAX_AGE_DAYS, "--max-age", help="Giorni max per analysis fresca."
    ),
    verbose: bool = typer.Option(False, "--verbose", "-v", help="Output debug su stderr."),
) -> None:
    """Genera report operativi (lista patch fermata + brief WIP) da un file KBA_Merged Excel."""
    _setup_logging(verbose)
    console = Console()

    today_str = date.today().strftime("%d%m%y")

    console.print(f"\n[bold]kba_reporter[/bold] - {input.name}\n")

    # Fase 1 — Carica e classifica
    rows = load_excel(input)
    classified = classify_rows(rows)

    # Fase 2 — Lista patch fermata
    patch_data = build_patch_list(classified["defer"])
    patch_output = OWNERS_INBOX_DIR / f"attivita-fermata-{today_str}.md"
    write_patch_list(patch_data, patch_output)
    console.print(
        f"[green][OK][/green] Lista patch     -> {patch_output.relative_to(PROJECT_ROOT)}"
    )

    # Fase 3 — Brief WIP
    brief_data = build_wip_brief(classified["wip"], max_age_days=max_age)
    brief_output = HANDOFF_DIR / f"brief-wip-{today_str}.md"
    write_wip_brief(brief_data, brief_output)
    console.print(
        f"[green][OK][/green] Brief WIP       -> {brief_output.relative_to(PROJECT_ROOT)}"
    )

    # Riepilogo
    mancanti = [r for r in brief_data if r["stato"] == "MANCANTE"]
    da_analizzare = [r for r in brief_data if r["stato"] in ("ANALIZZA", "MANCANTE")]
    skip_count = len(brief_data) - len(da_analizzare)

    # ── STOP su KBA mancanti ────────────────────────────────────────────────
    if mancanti:
        console.print()
        console.print("[bold red][STOP] KBA MANCANTI - procedura interrotta[/bold red]")
        console.print()
        console.print(
            "I seguenti KBA non sono nel catalogo né in lib/documents/.\n"
            "Aggiungi i PDF mancanti e rilancia."
        )
        console.print()
        for r in mancanti:
            console.print(f"  [red]MANCANTE[/red]  {r['kba_number']}  -  {r['title'][:60]}")
        console.print()
        console.print("[bold]Azioni richieste:[/bold]")
        console.print("  1. Copia i PDF mancanti in:  Inbox/")
        console.print("  2. Converti:  python -m tools.pdf_converter convert-all")
        console.print(
            "  3. Analizza:  python -m tools.consulto --prompt Team/Prompts/kba/analisi-rischio-kba.md \\"
        )
        console.print("                  --input lib/documents/<slug>.md \\")
        console.print("                  --output Team/Handoff/kba_batch/ --provider grok")
        console.print(
            "  4. Indicizza: python -m tools.kba_indexer index --input Team/Handoff/kba_batch/"
        )
        console.print("  5. Rilancia:  python -m tools.kba_reporter <file.xlsx>")
        console.print()
        raise typer.Exit(code=1)
    # ────────────────────────────────────────────────────────────────────────

    # Fase 4 — File discussione cliente
    discussion_output = OWNERS_INBOX_DIR / f"kba-da-discutere-{today_str}.md"
    write_kba_discussion(brief_data, discussion_output)
    console.print(
        f"[green][OK][/green] KBA discussione -> {discussion_output.relative_to(PROJECT_ROOT)}"
    )

    console.print(f"\nKBA WIP trovate : {len(brief_data)}")
    console.print(f"  Da analizzare : {len(da_analizzare)}")
    console.print(f"  Skip (fresche): {skip_count}")

    if da_analizzare:
        console.print(
            "\n[yellow]Analisi non fresche presenti — rilancia dopo l'analisi Grok.[/yellow]"
        )
    else:
        console.print(
            "\n[green]Tutte le analisi sono fresche — nessuna chiamata AI necessaria.[/green]"
        )
