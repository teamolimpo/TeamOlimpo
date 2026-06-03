"""Entry point CLI per kba.fermata.

Uso:
    python -m tools.kba.fermata "Owner's Inbox/KBA_Merged_xxx.xlsx"

Legge Stefano's Notes per classificare le KBA in {DEFER}.
STOP se una o più righe hanno Stefano's Notes vuota.
Produce: Owner's Inbox/fermata-DDMMYY.xlsx con 4 sheet.
"""

from __future__ import annotations

import sys
from pathlib import Path

import typer
from loguru import logger
from rich.console import Console

from tools.kba.reporter.classifier import load_excel
from tools.kba.reporter.config import (
    DEFER_KEYWORDS,
    OWNERS_INBOX_DIR,
    PROJECT_ROOT,
)
from tools.kba.reporter.patch_builder import build_patch_list
from tools.kba.fermata.writer import write_fermata_excel

console = Console()

DONE_NA = {"{DONE}", "{NA}", "{ACK}"}

app = typer.Typer(
    name="fermata",
    help="Genera Excel attività fermata da KBA con {DEFER}.",
    no_args_is_help=True,
)


def _setup_logging(verbose: bool) -> None:
    logger.remove()
    logger.add(
        sys.stderr,
        level="DEBUG" if verbose else "WARNING",
        format="<green>{time:HH:mm:ss}</green> | <level>{message}</level>",
    )


def _classify_stefano(rows: list[dict]) -> tuple[list[dict], list[dict]]:
    """
    Classifica le righe in base a Stefano's Notes.

    Returns:
        (defer_rows, empty_rows) — righe {DEFER} e righe con nota vuota.
    """
    defer: list[dict] = []
    empty: list[dict] = []

    for row in rows:
        if not row["kba_number"]:
            continue
        nota = row["stefano_notes"].strip()
        if not nota:
            # Controlla se la nota vecchia non è già chiusa (retrocompatibilità)
            old = row["user_notes"].upper()
            if any(tag in old for tag in DONE_NA):
                continue  # già chiusa nel vecchio campo — non blocca
            empty.append(row)
            continue
        # Controlla DONE/NA nel campo Stefano
        if any(tag in nota.upper() for tag in DONE_NA):
            continue
        # Classifica DEFER
        nota_low = nota.lower()
        if any(kw.lower() in nota_low for kw in DEFER_KEYWORDS):
            defer.append(row)

    return defer, empty


@app.command()
def main(
    input: Path = typer.Argument(..., help="File KBA_Merged Excel.", exists=True),
    output: Path = typer.Option(None, "--output", "-o", help="Path output Excel (auto se omesso)."),
    verbose: bool = typer.Option(False, "--verbose", "-v", help="Output debug su stderr."),
) -> None:
    """Genera Excel attività in fermata da KBA_Merged."""
    _setup_logging(verbose)

    console.print(f"\n[bold]kba_fermata[/bold] - {input.name}\n")

    rows = load_excel(input)
    defer_rows, empty_rows = _classify_stefano(rows)

    # ── STOP se Stefano's Notes ha righe vuote ───────────────────────────────
    if empty_rows:
        console.print("[bold red][STOP] Stefano's Notes incompleta[/bold red]\n")
        console.print("Le seguenti KBA non hanno ancora una nota in 'Stefano's Notes':")
        console.print()
        for r in empty_rows:
            console.print(f"  [yellow]{r['kba_number']}[/yellow]  {r['title'][:60]}")
        console.print()
        console.print(
            "Compila la colonna 'Stefano's Notes' per tutte le righe aperte, poi rilancia."
        )
        raise typer.Exit(code=1)
    # ─────────────────────────────────────────────────────────────────────────

    if not defer_rows:
        console.print("[yellow]Nessuna KBA con tag {DEFER} trovata in Stefano's Notes.[/yellow]")
        raise typer.Exit(code=0)

    console.print(f"KBA {'{DEFER}'}: [bold]{len(defer_rows)}[/bold]")

    patch_data = build_patch_list(defer_rows)

    output_path = output if output else None
    out = write_fermata_excel(patch_data, output_path=output_path, owners_inbox=OWNERS_INBOX_DIR)

    console.print(f"\n[green][OK][/green] Fermata Excel -> {out.relative_to(PROJECT_ROOT)}")

    # Riepilogo per sito
    for site, data in patch_data.items():
        n_ws = len(data.get("workstation_ms", {}))
        n_srv = len(data.get("server_ms", {}))
        n_fw = len(data.get("firmware", {}))
        console.print(f"  {site}: {n_ws} file WS, {n_srv} file SRV, {n_fw} firmware")
