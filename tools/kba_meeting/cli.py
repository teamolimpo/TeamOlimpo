"""Entry point CLI per kba_meeting.

Uso:
    python -m tools.kba_meeting "Owner's Inbox/KBA_Merged_xxx.xlsx"

Legge Stefano's Notes per classificare le KBA in {WIP}.
STOP se una o più righe hanno Stefano's Notes vuota.
Chiama Grok con il prompt report-meeting.md e Dike come system prompt.
Produce: Owner's Inbox/meeting-DDMMYY.md
"""

from __future__ import annotations

import sys
from datetime import datetime
from enum import Enum
from pathlib import Path

import typer
from loguru import logger
from rich.console import Console

from tools.kba_reporter.classifier import load_excel
from tools.kba_reporter.brief_builder import build_wip_brief, _kba_to_slug, _read_catalog_meta
from tools.kba_reporter.config import (
    WIP_KEYWORDS,
    OWNERS_INBOX_DIR,
    PROJECT_ROOT,
)
from tools.consulto.config import get_api_key, PROMPTS_DIR
from tools.consulto.providers import PROVIDERS
from tools.consulto.batch import extract_prompt_section

console = Console()

DONE_NA = {"{DONE}", "{NA}", "{ACK}"}
SYSTEM_PROMPT_PATH = PROJECT_ROOT / ".claude" / "agents" / "dike.md"
MEETING_PROMPT_PATH = PROJECT_ROOT / "lib" / "Prompts" / "kba" / "report-meeting.md"
DEFAULT_PROVIDER = "grok"
DEFAULT_MODEL = "grok-4.20-0309-reasoning"


class Provider(str, Enum):
    grok = "grok"
    gemini = "gemini"


app = typer.Typer(
    name="kba_meeting",
    help="Genera documento meeting cliente da KBA {WIP}.",
    no_args_is_help=True,
)


def _setup_logging(verbose: bool) -> None:
    logger.remove()
    logger.add(
        sys.stderr,
        level="DEBUG" if verbose else "WARNING",
        format="<green>{time:HH:mm:ss}</green> | <level>{message}</level>",
    )


def _classify_wip(rows: list[dict]) -> tuple[list[dict], list[dict]]:
    """
    Classifica le righe in base a Stefano's Notes.

    Returns:
        (wip_rows, empty_rows)
    """
    wip: list[dict] = []
    empty: list[dict] = []

    for row in rows:
        if not row["kba_number"]:
            continue
        nota = row["stefano_notes"].strip()
        if not nota:
            old = row["user_notes"].upper()
            if any(tag in old for tag in DONE_NA):
                continue
            empty.append(row)
            continue
        if any(tag in nota.upper() for tag in DONE_NA):
            continue
        nota_low = nota.lower()
        if any(kw.lower() in nota_low for kw in WIP_KEYWORDS):
            wip.append(row)

    return wip, empty


def _build_kba_input(wip_rows: list[dict]) -> str:
    """
    Costruisce il testo di input strutturato per Dike a partire dalle righe WIP.
    Carica sintesi/workaround/raccomandazione dal catalogo.
    """
    sections: list[str] = []

    # Deduplica per KBA, aggrega siti
    seen: dict[str, dict] = {}
    for row in wip_rows:
        kba = row["kba_number"]
        if kba not in seen:
            seen[kba] = {**row, "sites": set()}
        seen[kba]["sites"].add(row["site"].split(" - ")[0].strip())

    for kba, data in seen.items():
        slug = _kba_to_slug(kba)
        meta = _read_catalog_meta(slug)

        siti = ", ".join(sorted(data["sites"])) or "N/D"
        risk = meta.get("risk_level") or data.get("risk_level") or "N/D"
        sintesi = meta.get("sintesi") or ""
        workaround = meta.get("workaround_text") or ""
        nota_stefano = data["stefano_notes"].strip()

        block = f"### {kba} — {data['title']}\n\n"
        block += f"**Siti**: {siti}\n"
        block += f"**Rischio**: {risk}\n\n"
        if sintesi:
            block += f"**Sintesi**: {sintesi}\n\n"
        if workaround:
            block += f"**Workaround disponibile**: {workaround}\n\n"
        if nota_stefano:
            block += f"**Nota Stefano**: {nota_stefano}\n"

        sections.append(block)

    return "\n---\n\n".join(sections)


@app.command()
def main(
    input: Path = typer.Argument(..., help="File KBA_Merged Excel.", exists=True),
    output: Path = typer.Option(
        None, "--output", "-o", help="Path output Markdown (auto se omesso)."
    ),
    provider: Provider = typer.Option(Provider.grok, "--provider", help="Provider LLM."),
    model: str = typer.Option(DEFAULT_MODEL, "--model", help="Override modello LLM."),
    verbose: bool = typer.Option(False, "--verbose", "-v", help="Output debug su stderr."),
) -> None:
    """Genera documento meeting cliente da KBA_Merged Excel."""
    _setup_logging(verbose)

    console.print(f"\n[bold]kba_meeting[/bold] - {input.name}\n")

    rows = load_excel(input)
    wip_rows, empty_rows = _classify_wip(rows)

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

    if not wip_rows:
        console.print("[yellow]Nessuna KBA con tag {WIP} trovata in Stefano's Notes.[/yellow]")
        raise typer.Exit(code=0)

    console.print(f"KBA {{WIP}}: [bold]{len(wip_rows)}[/bold]")

    # Carica prompt e system
    if not MEETING_PROMPT_PATH.exists():
        console.print(f"[red]Errore:[/red] Prompt non trovato: {MEETING_PROMPT_PATH}")
        raise typer.Exit(code=1)

    prompt_template = extract_prompt_section(MEETING_PROMPT_PATH.read_text(encoding="utf-8"))

    system_text: str | None = None
    if SYSTEM_PROMPT_PATH.exists():
        system_text = SYSTEM_PROMPT_PATH.read_text(encoding="utf-8")
    else:
        logger.warning(f"System prompt Dike non trovato: {SYSTEM_PROMPT_PATH}")

    # Costruisce input
    kba_input = _build_kba_input(wip_rows)
    prompt = prompt_template.replace("{{kba_text}}", kba_input)

    # Chiama provider
    provider_name = provider.value
    api_key = get_api_key(provider_name)
    provider_cls = PROVIDERS[provider_name]
    provider_instance = provider_cls(api_key=api_key)

    console.print(f"Chiamata API [{provider_name} / {model}] ...", end=" ")
    sys.stdout.flush()

    import time

    t0 = time.monotonic()
    try:
        response = provider_instance.chat(prompt=prompt, model=model, system=system_text)
    except RuntimeError as exc:
        console.print(f"\n[red]Errore API:[/red] {exc}")
        raise typer.Exit(code=1)
    elapsed = time.monotonic() - t0
    console.print(f"ok ({elapsed:.1f}s)")

    # Scrive output
    if output:
        output_path = output
    else:
        ts = datetime.now().strftime("%d%m%y")
        output_path = OWNERS_INBOX_DIR / f"meeting-{ts}.md"

    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(response.text, encoding="utf-8")

    console.print(f"\n[green][OK][/green] Meeting doc -> {output_path.relative_to(PROJECT_ROOT)}")
