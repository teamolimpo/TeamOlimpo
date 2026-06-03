"""
Entry point CLI per il tool kba_pipeline.

Orchestratore della pipeline KBA completa:
  [1/4] Conversione PDF -> Markdown
  [2/4] Analisi AI documenti nuovi/aggiornati
  [3/4] Verifica dipendenze documentali
  [4/4] Merge + enrichment -> Excel finale

Utilizzo:
  python -m tools.kba_pipeline run Inbox/KBA.xlsx
  python -m tools.kba_pipeline run Inbox/KBA.xlsx --dry-run
  python -m tools.kba_pipeline run Inbox/KBA.xlsx --skip-convert --skip-analyze
  python -m tools.kba_pipeline run Inbox/KBA.xlsx --no-ai-merge --provider grok
"""

from __future__ import annotations

import re
import sys
import time
from pathlib import Path

import typer
from loguru import logger
from rich.console import Console
from rich.progress import Progress, SpinnerColumn, TextColumn, BarColumn, TaskProgressColumn

from tools.common.paths import resolve_absolute
from tools.kba_pipeline.config import LOG_FILE, PROJECT_ROOT, RECORDS_DIR
from tools.kba_pipeline import __version__
from tools.consulto.config import KNOWN_PRICES

console = Console(highlight=False)

app = typer.Typer(
    name="kba_pipeline",
    help="Orchestratore della pipeline KBA — dal PDF al file Excel finale.",
    no_args_is_help=True,
)

# Default inbox se non specificata
_DEFAULT_INBOX: Path = PROJECT_ROOT / "Team" / "Inbox"


def _stats_line(response: object) -> str:
    """Riga compatta stats AI: (12.3s · 8.0k tokens · $0.0016 · modello)."""
    parts: list[str] = []
    elapsed = getattr(response, "elapsed_seconds", None)
    if elapsed is not None:
        if elapsed >= 60:
            m, s = int(elapsed // 60), int(elapsed % 60)
            parts.append(f"{m}m {s:02d}s")
        else:
            parts.append(f"{elapsed:.1f}s")

    inp_tok = getattr(response, "input_tokens", None)
    out_tok = getattr(response, "output_tokens", None)
    if inp_tok or out_tok:

        def _fmt(n: int | None) -> str:
            if n is None:
                return "?"
            return f"{n / 1000:.1f}k" if n >= 1000 else str(n)

        parts.append(f"↑{_fmt(inp_tok)} ↓{_fmt(out_tok)} tok")

    model_id = getattr(response, "model_used", "") or ""
    inp_tok = getattr(response, "input_tokens", None)
    out_tok = getattr(response, "output_tokens", None)
    if model_id in KNOWN_PRICES and inp_tok and out_tok:
        ip, op = KNOWN_PRICES[model_id]
        cost = (inp_tok * ip + out_tok * op) / 1_000_000
        parts.append(f"${cost:.4f}")

    if model_id:
        parts.append(f"[dim]{model_id}[/dim]")

    return "(" + " · ".join(parts) + ")" if parts else ""


# ---------------------------------------------------------------------------
# Advisor modelli
# ---------------------------------------------------------------------------


def _show_model_advisor(records_dir: Path, current_model: str, excel_path: Path) -> None:
    """
    Confronta il modello salvato in ogni record con current_model.
    Se ci sono record stale, mostra un report e il comando per aggiornarli.
    """
    import yaml as _yaml

    _FRONTMATTER_RE = re.compile(r"\A---\s*\n([\s\S]*?)\n---\s*\n", re.MULTILINE)

    stale: dict[str, int] = {}  # old_model -> count

    if not records_dir.exists():
        return

    for rec in records_dir.glob("*.md"):
        try:
            text = rec.read_text(encoding="utf-8")
            fm_match = _FRONTMATTER_RE.match(text)
            if not fm_match:
                continue
            fm = _yaml.safe_load(fm_match.group(1)) or {}
            rec_model = str(fm.get("analyzed_by_model", "unknown"))
            if rec_model != current_model:
                stale[rec_model] = stale.get(rec_model, 0) + 1
        except Exception:
            continue

    if not stale:
        return

    total_stale = sum(stale.values())
    console.print(
        f"\n[yellow]⚠  Advisor modelli:[/yellow] [bold]{total_stale}[/bold] record analizzati "
        f"con modello diverso da [cyan]{current_model}[/cyan]"
    )
    for old_model, count in sorted(stale.items(), key=lambda x: -x[1]):
        console.print(f"   [dim]{old_model}[/dim]  →  {count} record")
    rel_excel = excel_path.name
    console.print(f"\n   Per aggiornare:")
    console.print(
        f"   [dim]python -m tools.kba_pipeline run {rel_excel} "
        f"--skip-convert --force-analyze --model-analyze {current_model}[/dim]"
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
    """Orchestratore della pipeline KBA per il Team Olimpo."""
    _setup_logging(verbose)


# ---------------------------------------------------------------------------
# Comando principale: run
# ---------------------------------------------------------------------------


@app.command()
def run(
    excel: Path = typer.Argument(
        ...,
        help="File Excel DeltaV (.xlsx) — path relativo a PROJECT_ROOT o assoluto.",
        exists=False,  # gestione manuale per path relativi a PROJECT_ROOT
    ),
    inbox: Path = typer.Option(
        None,
        "--inbox",
        "-i",
        help=f"Cartella sorgente PDF (default: Inbox/).",
    ),
    provider: str = typer.Option(
        "grok",
        "--provider",
        help="Provider LLM da usare per l'analisi AI (step 2 e step 4).",
    ),
    model: str = typer.Option(
        "grok-4-1-fast-reasoning",
        "--model",
        help="Modello LLM per l'enrichment Suggested Notes (step 4).",
    ),
    model_analyze: str = typer.Option(
        "grok-4.20-0309-reasoning",
        "--model-analyze",
        help="Modello LLM per l'analisi KBA (step 2). Default: modello potente.",
    ),
    force_analyze: bool = typer.Option(
        False,
        "--force-analyze",
        help="Forza la ri-analisi di tutti i record esistenti (utile dopo cambio modello).",
    ),
    skip_convert: bool = typer.Option(
        False,
        "--skip-convert",
        help="Salta lo step 1 (conversione PDF).",
    ),
    skip_analyze: bool = typer.Option(
        False,
        "--skip-analyze",
        help="Salta lo step 2 (analisi AI documenti).",
    ),
    no_ai_merge: bool = typer.Option(
        False,
        "--no-ai-merge",
        help="Esegui il merge senza AI enrichment (step 4 piu' veloce).",
    ),
    dry_run: bool = typer.Option(
        False,
        "--dry-run",
        help="Mostra il piano di esecuzione senza apportare modifiche.",
    ),
    force: bool = typer.Option(
        False,
        "--force",
        "-f",
        help="Forza la riconversione dei PDF gia' presenti nel database (step 1).",
    ),
) -> None:
    """
    Esegue la pipeline KBA completa: PDF -> Markdown -> catalogo -> merge Excel.

    Il file Excel DeltaV puo' essere specificato come path assoluto o relativo
    alla root del progetto (es. 'Inbox/KBA.xlsx').

    Exit code 0 = completato con successo.
    Exit code 1 = dipendenze documentali mancanti (step 3) o errore critico.
    """
    from tools.kba_pipeline.steps import (
        step1_convert,
        step2_analyze,
        step3_resolve,
        step4_merge,
    )

    t0 = time.monotonic()

    console.print(f"[bold]kba_pipeline[/bold] v{__version__} — avvio flusso")
    if dry_run:
        console.print("[dim](modalita' dry-run: nessuna modifica verra' apportata)[/dim]")

    # --- Risolvi path Excel ---
    excel_path = resolve_absolute(excel)

    if not excel_path.exists():
        console.print(
            f"[bold red]Errore:[/bold red] file Excel non trovato: {excel_path}", stderr=True
        )
        raise typer.Exit(1)

    if excel_path.suffix.lower() != ".xlsx":
        console.print(
            f"[bold red]Errore:[/bold red] il file deve essere .xlsx, ricevuto: {excel_path.suffix}",
            stderr=True,
        )
        raise typer.Exit(1)

    # --- Risolvi inbox ---
    if inbox is not None:
        inbox_path = resolve_absolute(inbox)
    else:
        inbox_path = _DEFAULT_INBOX

    logger.debug(f"Excel: {excel_path}")
    logger.debug(f"Inbox: {inbox_path}")
    logger.debug(f"Provider: {provider}, model: {model}")

    # ==========================================================================
    # Step 1 — Conversione PDF
    # ==========================================================================
    if not skip_convert:
        console.print("\n[bold][1/4][/bold] Conversione PDF...")

        try:
            r1 = step1_convert(inbox_path, force=force, dry_run=dry_run)
            err_color = "red" if r1["errors"] else "dim"
            console.print(
                f"      [bold]{r1['converted']}[/bold] convertiti, "
                f"[dim]{r1['skipped']} saltati[/dim], "
                f"[{err_color}]{r1['errors']} errori[/{err_color}]"
            )
        except Exception as exc:
            logger.error(f"Step 1 fallito: {exc}")
            console.print(
                f"      [bold red]ERRORE critico nello step 1:[/bold red] {exc}", stderr=True
            )
            raise typer.Exit(1)
    else:
        console.print("\n[bold][1/4][/bold] Conversione PDF... [dim](saltato)[/dim]")

    # ==========================================================================
    # Step 2 — Analisi AI
    # ==========================================================================
    _step2_responses: list = []

    if not skip_analyze:
        console.print("\n[bold][2/4][/bold] Analisi AI documenti nuovi...")

        def _on_kba_progress(
            i: int, total: int, slug: str, status: str, response, error: str | None
        ) -> None:
            if status == "start":
                pass  # il timer live in step2_analyze gestisce il display
            elif status == "ok":
                if response:
                    _step2_responses.append(response)
                stats = _stats_line(response) if response else ""
                console.print(
                    f"      [[dim]{i}/{total}[/dim]] [cyan]{slug}[/cyan]  [green]ok[/green]  [dim]{stats}[/dim]"
                )
            elif status == "error":
                console.print(
                    f"      [[dim]{i}/{total}[/dim]] [cyan]{slug}[/cyan]  [red]ERRORE[/red]: {error}"
                )

        try:
            r2 = step2_analyze(
                provider,
                model_analyze,
                dry_run=dry_run,
                on_progress=_on_kba_progress,
                force_analyze=force_analyze,
            )
            console.print(
                f"      [bold]{r2['analyzed']}[/bold] analizzati, "
                f"[dim]{r2['skipped']} saltati[/dim], "
                f"[{'red' if r2['errors'] else 'dim'}]{r2['errors']} errori[/{'red' if r2['errors'] else 'dim'}], "
                f"[bold]{r2['total_catalog']}[/bold] nel catalogo"
            )
        except Exception as exc:
            logger.error(f"Step 2 fallito: {exc}")
            console.print(
                f"      [bold red]ERRORE critico nello step 2:[/bold red] {exc}", stderr=True
            )
            raise typer.Exit(1)
    else:
        console.print("\n[bold][2/4][/bold] Analisi AI... [dim](saltato)[/dim]")

    # ==========================================================================
    # Step 3 — Verifica dipendenze
    # ==========================================================================
    console.print("\n[bold][3/4][/bold] Verifica dipendenze...")
    try:
        r3 = step3_resolve(excel_path)
    except (ValueError, OSError) as exc:
        logger.error(f"Step 3 fallito: {exc}")
        console.print(f"      [bold red]ERRORE lettura Excel:[/bold red] {exc}", stderr=True)
        raise typer.Exit(1)
    except Exception as exc:
        logger.error(f"Step 3 errore inatteso: {exc}")
        console.print(f"      [bold red]ERRORE critico nello step 3:[/bold red] {exc}", stderr=True)
        raise typer.Exit(1)

    if not r3["ok"]:
        console.print(
            f"      [bold red]STOP[/bold red] — [bold]{len(r3['missing'])}[/bold] documenti mancanti:"
        )
        for m in r3["missing"]:
            console.print(f"        [cyan]- {m}[/cyan]")
        console.print("\n      Aggiungi i PDF mancanti e rilancia.")
        raise typer.Exit(1)

    console.print("      [green]OK[/green] — tutte le dipendenze presenti")

    # ==========================================================================
    # Step 4 — Merge + Enrichment
    # ==========================================================================
    console.print("\n[bold][4/4][/bold] Merge + enrichment...")

    # Accumulatore token per step 4 (e globale)
    _s4_responses: list = []

    def _on_enrich_progress(i: int, total: int, kba: str, status: str, response, error) -> None:
        if status == "python":
            console.print(f"      [[dim]{i}/{total}[/dim]] [cyan]{kba}[/cyan]  [dim]python[/dim]")
        elif status == "ai":
            stats = _stats_line(response) if response else ""
            _s4_responses.append(response)
            console.print(
                f"      [[dim]{i}/{total}[/dim]] [cyan]{kba}[/cyan]  [green]AI[/green]  [dim]{stats}[/dim]"
            )
        elif status == "ai_error":
            console.print(
                f"      [[dim]{i}/{total}[/dim]] [cyan]{kba}[/cyan]  [red]AI ERRORE[/red]: {error}"
            )
        elif status == "fallback":
            console.print(f"      [[dim]{i}/{total}[/dim]] [cyan]{kba}[/cyan]  [dim]fallback[/dim]")

    try:
        r4 = step4_merge(
            excel_path=excel_path,
            use_ai=not no_ai_merge,
            provider_name=provider,
            model=model,
            dry_run=dry_run,
            on_progress=_on_enrich_progress,
        )
        console.print(
            f"      [bold]{r4['input_rows']}[/bold] righe input -> "
            f"[bold]{r4['merged_rows']}[/bold] righe merged, "
            f"[bold]{r4.get('in_catalog', '?')}[/bold]/[bold]{r4.get('total_unique', '?')}[/bold] KBA in catalogo"
        )
        if not dry_run:
            console.print(f"      Output: [cyan]{r4['output_path']}[/cyan]")
    except (ValueError, OSError) as exc:
        logger.error(f"Step 4 fallito: {exc}")
        console.print(f"      [bold red]ERRORE nel merge:[/bold red] {exc}", stderr=True)
        raise typer.Exit(1)
    except Exception as exc:
        logger.error(f"Step 4 errore inatteso: {exc}")
        console.print(f"      [bold red]ERRORE critico nello step 4:[/bold red] {exc}", stderr=True)
        raise typer.Exit(1)

    # Advisor: segnala record con modello diverso da quello corrente
    _show_model_advisor(RECORDS_DIR, model_analyze, excel_path)

    # Riassunto token totali
    all_responses = _step2_responses + _s4_responses  # type: ignore[name-defined]
    if any(r is not None for r in all_responses):
        total_inp = sum(getattr(r, "input_tokens", 0) or 0 for r in all_responses if r)
        total_out = sum(getattr(r, "output_tokens", 0) or 0 for r in all_responses if r)
        total_cost = 0.0
        for r in all_responses:
            if not r:
                continue
            mid = getattr(r, "model_used", "") or ""
            inp = getattr(r, "input_tokens", None)
            out = getattr(r, "output_tokens", None)
            if mid in KNOWN_PRICES and inp and out:
                ip, op = KNOWN_PRICES[mid]
                total_cost += (inp * ip + out * op) / 1_000_000

        def _fmt(n: int) -> str:
            return f"{n / 1000:.1f}k" if n >= 1000 else str(n)

        cost_str = f" · [bold]${total_cost:.4f}[/bold] totali" if total_cost else ""
        console.print(
            f"\n[dim]Token sessione:[/dim] ↑{_fmt(total_inp)} ↓{_fmt(total_out)}{cost_str}"
        )

    elapsed = time.monotonic() - t0
    console.print(f"[green]Completato[/green] in [bold]{elapsed:.0f}s[/bold]")
