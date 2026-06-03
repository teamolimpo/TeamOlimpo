from __future__ import annotations

import json
import sys
from pathlib import Path

import typer
from loguru import logger
from rich.console import Console
from rich.panel import Panel
from rich.table import Table

from tools.hermes_cli.config import HANDOFF_DIR, SCRATCHPAD_PATH, TIPI_HANDOFF
from tools.hermes_cli.generator import (
    create_handoff,
    fix_all_handoffs,
    fix_handoff_file,
    init_scratchpad,
)
from tools.hermes_cli.id_manager import (
    check_duplicate_ids,
    find_next_decision_id,
    find_next_task_id,
)
from tools.hermes_cli.report import generate_diff, generate_report, generate_stats
from tools.hermes_cli.scanner import read_scratchpad, scan_handoff_files
from tools.hermes_cli.validator import validate_handoff_file, validate_scratchpad

console = Console(stderr=True)
out_console = Console()


def _emit_json(data: dict) -> None:
    """Output JSON senza wrapping (evita rich word-wrap)."""
    sys.stdout.write(json.dumps(data, indent=2, ensure_ascii=False) + "\n")


app = typer.Typer(
    name="hermes_cli",
    help="Hermes CLI \u2014 Validazione e gestione ID del Team Olimpo.",
    no_args_is_help=True,
)

validate_app = typer.Typer(help="Comandi di validazione.")
id_app = typer.Typer(help="Comandi di gestione ID.")

app.add_typer(validate_app, name="validate")
app.add_typer(id_app, name="id")

_verbose_state: dict[str, bool] = {"verbose": False}
_json_state: dict[str, bool] = {"json": False}


def _setup_logging(verbose: bool) -> None:
    logger.remove()
    level = "DEBUG" if verbose else "WARNING"
    logger.add(sys.stderr, level=level, format="<level>{level}</level>: {message}")


@app.callback()
def common(
    verbose: bool = typer.Option(False, "--verbose", "-v", help="Output debug su stderr."),
    json_output: bool = typer.Option(False, "--json", help="Output in formato JSON."),
) -> None:
    _verbose_state["verbose"] = verbose
    _json_state["json"] = json_output
    _setup_logging(verbose)
    logger.debug("Hermes CLI avviato")


def _output_json_scratchpad(sp) -> None:
    _emit_json(
        {
            "target": sp.rel_path,
            "valid": len(sp.errors) == 0,
            "parsed": sp.parsed,
            "errors": sp.errors,
            "warnings": sp.warnings,
            "stats": {"tasks": len(sp.tasks), "decisions": len(sp.decisions)},
        }
    )


def _output_text_scratchpad(sp, title_prefix: str = "") -> None:
    lines: list[str] = []
    title = f"hermes-cli validate scratchpad{(' ' + title_prefix) if title_prefix else ''}"

    lines.append(f"  Scratchpad: {sp.rel_path}")
    lines.append("")

    if not sp.parsed and not sp.errors:
        lines.append("  [yellow]\u26a0[/yellow] YAML: frontmatter assente")
    elif sp.parsed:
        lines.append("  [green]\u2713[/green] YAML: frontmatter valido")
    else:
        lines.append("  [red]\u2717[/red] YAML: frontmatter NON valido")

    for w in sp.warnings:
        lines.append(f"  [yellow]\u26a0[/yellow] {w['description']}")

    for e in sp.errors:
        lines.append(f"  [red]\u2717[/red] {e['description']}")

    lines.append("")
    lines.append(
        f"  Risultato: {len(sp.errors)} errori, {len(sp.warnings)} warning ({len(sp.tasks)} task, {len(sp.decisions)} decisioni)"
    )

    panel = Panel(
        "\n".join(lines),
        title=title,
        border_style="blue" if not sp.errors else "red",
    )
    out_console.print(panel)


def _output_json_handoff(hv) -> None:
    _emit_json(
        {
            "path": str(hv.path),
            "valid": hv.valid,
            "has_frontmatter": hv.has_frontmatter,
            "naming_valid": hv.naming_valid,
            "naming_errors": hv.naming_errors,
            "errors": hv.errors,
            "warnings": hv.warnings,
        }
    )


def _output_text_handoff(hv) -> None:
    lines: list[str] = []
    lines.append(f"  File: {hv.path.name}")
    lines.append(
        f"  Frontmatter: {'[green]\u2713 presente[/green]' if hv.has_frontmatter else '[yellow]\u2b1c assente[/yellow]'}"
    )
    lines.append(
        f"  Naming: {'[green]\u2713 valido[/green]' if hv.naming_valid else '[red]\u2717 non valido[/red]'}"
    )

    if hv.naming_errors:
        for ne in hv.naming_errors:
            lines.append(f"    [red]\u2717[/red] {ne}")

    for e in hv.errors:
        lines.append(f"  [red]\u2717[/red] {e['description']}")

    for w in hv.warnings:
        lines.append(f"  [yellow]\u26a0[/yellow] {w['description']}")

    if hv.errors:
        esito = "[red]\u2717 ERRORE[/red]"
    elif hv.warnings or not hv.naming_valid:
        esito = "[yellow]\u26a0 WARN[/yellow]"
    else:
        esito = "[green]\u2713 OK[/green]"
    lines.append("")
    lines.append(f"  Esito: {esito}")

    panel = Panel(
        "\n".join(lines),
        title=f"hermes-cli validate handoff",
        border_style="green" if hv.valid else "red",
    )
    out_console.print(panel)


# --- validate commands ---


@validate_app.command("scratchpad")
def validate_scratchpad_cmd(
    fix: bool = typer.Option(False, "--fix", help="Tenta di correggere errori (Fase 1: limitato)."),
) -> None:
    sp = read_scratchpad(SCRATCHPAD_PATH)
    sp = validate_scratchpad(sp)

    if _json_state["json"]:
        _output_json_scratchpad(sp)
    else:
        _output_text_scratchpad(sp)

    if fix:
        console.print("[yellow]\u26a0 --fix non implementato in Fase 1 (sola lettura).[/yellow]")

    raise typer.Exit(code=0)


@validate_app.command("handoff")
def validate_handoff_cmd(
    file_path: Path = typer.Argument(
        ..., help="Path del file handoff da validare.", exists=True, readable=True
    ),
    fix: bool = typer.Option(False, "--fix", help="Corregge naming e frontmatter se non conformi."),
) -> None:
    hv = validate_handoff_file(file_path)

    if fix:
        fix_result = fix_handoff_file(file_path)
        if _json_state["json"]:
            # Output combinato
            _emit_json(
                {
                    "validation": {
                        "path": str(hv.path),
                        "valid": hv.valid,
                        "has_frontmatter": hv.has_frontmatter,
                        "naming_valid": hv.naming_valid,
                        "errors": hv.errors,
                        "warnings": hv.warnings,
                    },
                    "fix": fix_result,
                }
            )
            return
        if fix_result.get("renamed"):
            out_console.print(f"[green]File rinominato:[/green] {fix_result['new_path']}")
        if fix_result.get("frontmatter_fixed"):
            out_console.print(f"[green]Frontmatter aggiunto.[/green]")
        if fix_result.get("backup"):
            console.print(f"[dim]Backup: {fix_result['backup']}[/dim]")
        if fix_result.get("warnings"):
            for w in fix_result["warnings"]:
                console.print(f"[yellow]{w}[/yellow]")
        if fix_result.get("errors"):
            for e in fix_result["errors"]:
                console.print(f"[bold red]{e}[/bold red]")

    if _json_state["json"] and not fix:
        _output_json_handoff(hv)
    elif not fix:
        _output_text_handoff(hv)

    if hv.errors and not fix:
        raise typer.Exit(code=1)
    raise typer.Exit(code=0)


@validate_app.command("handoffs")
def validate_handoffs_cmd(
    summary: bool = typer.Option(False, "--summary", help="Solo conteggi riassuntivi."),
    fix: bool = typer.Option(
        False, "--fix", help="Corregge naming e frontmatter dei file non conformi."
    ),
) -> None:
    paths = scan_handoff_files(HANDOFF_DIR)
    results = []
    conformi = warning = errori = 0
    for p in paths:
        hv = validate_handoff_file(p)
        results.append(hv)
        if hv.errors:
            errori += 1
        elif hv.warnings:
            warning += 1
        else:
            conformi += 1

    logger.debug(
        f"Validate handoffs: {len(paths)} file, {conformi} conformi, {warning} warning, {errori} errori"
    )

    if fix:
        fix_result = fix_all_handoffs(fix_name=True, fix_frontmatter=True)
        if _json_state["json"]:
            _emit_json(
                {
                    "validation": {
                        "total": len(paths),
                        "conformi": conformi,
                        "warning": warning,
                        "errori": errori,
                    },
                    "fix": fix_result,
                }
            )
            return
        console.print(
            f"[bold]Fix applicato a {fix_result['fixed']}/{fix_result['total']} file.[/bold]"
        )
        if fix_result.get("errors", 0) > 0:
            console.print(f"[red]{fix_result['errors']} errori durante il fix.[/red]")

    if _json_state["json"]:
        _emit_json(
            {
                "target": str(HANDOFF_DIR),
                "total": len(paths),
                "conformi": conformi,
                "warning": warning,
                "errori": errori,
            }
        )
        return

    if summary:
        out_console.print(f"Totale: {len(paths)} file")
        out_console.print(f"  Conformi: {conformi}")
        out_console.print(f"  Warning:  {warning}")
        out_console.print(f"  Errori:   {errori}")
    else:
        table = Table(title=f"Validazione Handoff ({len(paths)} file)")
        table.add_column("File", style="cyan", min_width=30, max_width=50)
        table.add_column("FM", style="yellow", width=2)
        table.add_column("Nome", style="yellow", width=2)
        table.add_column("", style="green", width=2)
        table.add_column("Dettaglio", style="white", max_width=60)

        for hv in results:
            esito = "\u2713" if hv.valid else "\u2717"
            fm_status = "\u2713" if hv.has_frontmatter else "\u00b7"
            naming_status = "\u2713" if hv.naming_valid else "\u2717"
            dettagli = []
            for w in hv.warnings:
                dettagli.append(w["description"])
            for e in hv.errors:
                dettagli.append(e["description"])
            dettaglio_str = "; ".join(dettagli)[:80] if dettagli else ""
            table.add_row(hv.path.name, fm_status, naming_status, esito, dettaglio_str)

        out_console.print(table)
        out_console.print(
            f"\nConformi: {conformi} | Warning: {warning} | Errori: {errori} | Totale: {len(paths)}"
        )

    if errori > 0:
        raise typer.Exit(code=1)
    raise typer.Exit(code=0)


@validate_app.command("all")
def validate_all_cmd() -> None:
    sp = read_scratchpad(SCRATCHPAD_PATH)
    sp = validate_scratchpad(sp)

    paths = scan_handoff_files(HANDOFF_DIR)
    h_conformi = h_warning = h_errori = 0
    for p in paths:
        hv = validate_handoff_file(p)
        if hv.errors:
            h_errori += 1
        elif hv.warnings:
            h_warning += 1
        else:
            h_conformi += 1

    if _json_state["json"]:
        _emit_json(
            {
                "scratchpad": {
                    "path": sp.rel_path,
                    "valid": len(sp.errors) == 0,
                    "parsed": sp.parsed,
                    "errors": sp.errors,
                    "warnings": sp.warnings,
                    "stats": {"tasks": len(sp.tasks), "decisions": len(sp.decisions)},
                },
                "handoffs": {
                    "target": str(HANDOFF_DIR),
                    "total": len(paths),
                    "conformi": h_conformi,
                    "warning": h_warning,
                    "errori": h_errori,
                },
            }
        )
    else:
        _output_text_scratchpad(sp, title_prefix="(parte di all)")
        out_console.print(
            f"\n[bold]Handoff:[/bold] {len(paths)} file \u2014 {h_conformi} conformi, {h_warning} warning, {h_errori} errori"
        )

    if sp.errors or h_errori > 0:
        raise typer.Exit(code=1)
    raise typer.Exit(code=0)


# --- id commands ---


@id_app.command("next")
def id_next(
    kind: str = typer.Argument(..., help="Tipo ID: 'task' o 'decision'"),
) -> None:
    sp = read_scratchpad(SCRATCHPAD_PATH)
    handoff_paths = scan_handoff_files(HANDOFF_DIR)

    if kind == "task":
        next_id = find_next_task_id(sp, handoff_paths)
    elif kind == "decision":
        next_id = find_next_decision_id(sp, handoff_paths)
    else:
        console.print(
            f"[bold red]ERRORE:[/bold red] Tipo non valido: '{kind}'. Usa 'task' o 'decision'."
        )
        raise typer.Exit(code=2)

    if _json_state["json"]:
        _emit_json({"next": next_id, "type": kind})
    else:
        out_console.print(next_id)


@id_app.command("check")
def id_check_cmd() -> None:
    sp = read_scratchpad(SCRATCHPAD_PATH)
    handoff_paths = scan_handoff_files(HANDOFF_DIR)

    conflicts = check_duplicate_ids(sp, handoff_paths)

    if _json_state["json"]:
        _emit_json({"duplicates": conflicts, "total": len(conflicts)})
        raise typer.Exit(code=1 if conflicts else 0)

    if not conflicts:
        out_console.print("[green]Nessun duplicato trovato.[/green]")
    else:
        out_console.print(f"[red]Trovati {len(conflicts)} ID duplicati:[/red]")
        for c in conflicts:
            out_console.print(f"  [bold]{c['id']}[/bold]:")
            for occ in c["occurrences"]:
                out_console.print(f"    - {occ['source']}: {occ['path']}")

    raise typer.Exit(code=1 if conflicts else 0)


# --- scratchpad commands ---

scratchpad_app = typer.Typer(help="Comandi di gestione scratchpad.")
app.add_typer(scratchpad_app, name="scratchpad")


@scratchpad_app.command("init")
def scratchpad_init(
    agent: str = typer.Option(..., "--agent", help="Nome del nuovo agente."),
    role: str = typer.Option(
        "Membro del Team Olimpo",
        "--role",
        help="Ruolo descrittivo dell'agente.",
    ),
    force: bool = typer.Option(False, "--force", help="Sovrascrive se esiste."),
    dry_run: bool = typer.Option(False, "--dry-run", help="Mostra senza creare."),
) -> None:
    """Inizializza uno scratchpad per un nuovo agente."""
    result = init_scratchpad(agent, role=role, force=force, dry_run=dry_run)

    if _json_state["json"]:
        _emit_json(result)
    elif result["success"]:
        out_console.print(f"[green]Creato:[/green] {result['path']}")
        if result.get("warnings"):
            for w in result["warnings"]:
                console.print(f"[yellow]{w}[/yellow]")
    else:
        for e in result["errors"]:
            console.print(f"[bold red]ERRORE:[/bold red] {e}")
        raise typer.Exit(code=1)


# --- handoff commands ---

handoff_app = typer.Typer(help="Comandi di gestione handoff.")
app.add_typer(handoff_app, name="handoff")


@handoff_app.command("create")
def handoff_create(
    tipo: str = typer.Option(..., "--type", help=f"Tipo handoff: {', '.join(TIPI_HANDOFF)}"),
    dest: str = typer.Option(..., "--dest", help="Destinatario (nome mitologico o 'team')."),
    title: str = typer.Option(..., "--title", help="Titolo (max 60 caratteri)."),
    mittente: str = typer.Option("hermes", "--from", help="Mittente (default: hermes)."),
    priorita: str = typer.Option("media", "--priorita", help="Priorita: alta, media, bassa."),
    data: str | None = typer.Option(None, "--date", help="Data YYYY-MM-DD (default: oggi)."),
    force: bool = typer.Option(False, "--force", help="Sovrascrive se esiste."),
    dry_run: bool = typer.Option(False, "--dry-run", help="Mostra senza creare."),
) -> None:
    """Crea un file handoff con naming e frontmatter corretti."""
    result = create_handoff(
        tipo=tipo,
        destinatario=dest,
        titolo=title,
        mittente=mittente,
        priorita=priorita,
        data_str=data,
        force=force,
        dry_run=dry_run,
    )

    if _json_state["json"]:
        _emit_json(result)
    elif result["success"]:
        out_console.print(f"[green]Creato:[/green] {result['path']}")
        if result.get("warnings"):
            for w in result["warnings"]:
                console.print(f"[yellow]{w}[/yellow]")
        if dry_run and result.get("_content"):
            out_console.print("\n[bold]Contenuto (dry-run):[/bold]")
            out_console.print(result["_content"])
    else:
        for e in result["errors"]:
            console.print(f"[bold red]ERRORE:[/bold red] {e}")
        raise typer.Exit(code=1)


# --- report / diff / stats commands ---


@app.command()
def report(
    short: bool = typer.Option(False, "--short", help="Output ridotto a 3-4 righe."),
    json_output: bool = typer.Option(False, "--json", help="Output in formato JSON."),
) -> None:
    if json_output:
        _json_state["json"] = True
    sp = read_scratchpad(SCRATCHPAD_PATH)
    handoff_paths = scan_handoff_files(HANDOFF_DIR)

    result = generate_report(sp, handoff_paths, short=short)

    if _json_state["json"]:
        _emit_json(result)
        return

    if short:
        task_info = (
            f"Task: {result['tasks']['open']} aperti, "
            f"{result['tasks']['completed']} completati, "
            f"{result['tasks']['blocked']} bloccati"
        )
        hf = result["handoffs"]
        dp = hf.get("da-processare", 0)
        hf_info = f"Handoff: {hf['total']} totali, {dp} da-processare"
        sc_ok = result["conformity"]["scratchpad"]["errors"] == 0
        hc = result["conformity"]["handoffs"]
        conf_info = (
            f"Conformit\u00e0: scratchpad {'OK' if sc_ok else 'ERR'}, "
            f"handoff {hc['conformi']}/{hc['conformi'] + hc['warning'] + hc['errori']}"
        )
        panel = Panel(
            f"  {task_info}\n  {hf_info}\n  {conf_info}",
            title="hermes-cli report (breve)",
            border_style="blue",
        )
        out_console.print(panel)
        return

    lines: list[str] = []
    lines.append("  [bold]Hermes CLI \u2014 Report stato[/bold]")
    lines.append("")

    t = result["tasks"]
    open_ids = [
        f"{x['id']}"
        for x in t["by_agent"].get("hermes", [])
        if x["status"] not in ("completed", "blocked", "cancelled")
    ]
    lines.append("  [bold]Task:[/bold]")
    lines.append(
        f"    Aperti:      {t['open']}" + (f" ({', '.join(open_ids)})" if open_ids else "")
    )
    lines.append(f"    Completati:  {t['completed']}")
    lines.append(f"    Bloccati:    {t['blocked']}")
    lines.append(f"    Cancellati:  {t['cancelled']}")
    lines.append("")

    lines.append("  [bold]Agenti coinvolti:[/bold]")
    for agent, tasks in sorted(t["by_agent"].items()):
        tags = ", ".join(f"{x['id']} ({x['status']})" for x in tasks[:5])
        if len(tasks) > 5:
            tags += f" ... (+{len(tasks) - 5})"
        lines.append(f"    {agent.capitalize()}: {tags}")
    lines.append("")

    hf = result["handoffs"]
    lines.append("  [bold]Handoff attivi:[/bold]")
    for stato in ("da-processare", "in-corso", "bloccato", "completato", "senza_stato"):
        lines.append(f"    {stato}: {hf[stato]}")
    lines.append("")

    cf = result["conformity"]
    sc = cf["scratchpad"]
    sc_icon = "[green]\u2713[/green]" if sc["errors"] == 0 else "[red]\u2717[/red]"
    sc_label = f"{sc_icon} {sc['errors']} errori, {sc['warnings']} warning"
    if sc["errors"]:
        sc_label += " (YAML malformato)"
    hc = cf["handoffs"]
    hf_icon = "[green]\u2713[/green]" if hc["errori"] == 0 else "[yellow]\u26a0[/yellow]"
    hf_label = f"{hf_icon} {hc['conformi']}/{hc['conformi'] + hc['warning'] + hc['errori']} conformi, {hc['warning']} warning, {hc['errori']} errori"
    ids = cf["ids"]
    ids_icon = "[green]\u2713[/green]" if ids["duplicates"] == 0 else "[yellow]\u26a0[/yellow]"
    ids_label = f"{ids_icon} {ids['duplicates']} duplicati"
    if ids["duplicate_ids"]:
        ids_label += f" ({', '.join(ids['duplicate_ids'][:5])})"

    lines.append("  [bold]Conformit\u00e0:[/bold]")
    lines.append(f"    Scratchpad:  {sc_label}")
    lines.append(f"    Handoff:     {hf_label}")
    lines.append(f"    ID:          {ids_label}")

    panel = Panel(
        "\n".join(lines),
        title="hermes-cli report",
        border_style="blue",
    )
    out_console.print(panel)


@app.command()
def diff(
    target: str = typer.Argument(
        "scratchpad",
        help="Target da analizzare (default: scratchpad).",
    ),
    json_output: bool = typer.Option(False, "--json", help="Output in formato JSON."),
) -> None:
    if json_output:
        _json_state["json"] = True
    if target != "scratchpad":
        console.print(
            f"[bold red]ERRORE:[/bold red] Target '{target}' non supportato. Usa 'scratchpad'."
        )
        raise typer.Exit(code=2)

    text = SCRATCHPAD_PATH.read_text(encoding="utf-8")
    sp = read_scratchpad(SCRATCHPAD_PATH)
    result = generate_diff(sp, text)

    if _json_state["json"]:
        _emit_json(result)
    else:
        lines: list[str] = []
        lines.append("  Confronto frontmatter vs body")
        lines.append("")

        if result["only_in_frontmatter"]:
            lines.append("  [bold]Task in frontmatter ma non nel body:[/bold]")
            for tid, status in result["only_in_frontmatter"].items():
                lines.append(f"    - {tid} ({status})")
            lines.append("")

        if result["only_in_body"]:
            lines.append("  [bold]Task nel body ma non in frontmatter:[/bold]")
            for tid, status in result["only_in_body"].items():
                lines.append(f"    - {tid} ({status})")
            lines.append("")

        if result["status_mismatch"]:
            lines.append("  [bold]Task con stato diverso:[/bold]")
            for tid, info in result["status_mismatch"].items():
                match_icon = (
                    "[green]\u2713[/green]" if info["fm"] == info["body"] else "[red]\u2717[/red]"
                )
                lines.append(
                    f"    - {tid}: frontmatter={info['fm']}, body={info['body']} {match_icon}"
                )
            lines.append("")

        if result["aligned"]:
            lines.append("  [green]\u2713 Allineato: nessuna discrepanza trovata[/green]")
        else:
            lines.append(
                f"  [yellow]\u26a0 Esito: {result['total_discrepancies']} discrepanze trovate[/yellow]"
            )

        panel = Panel(
            "\n".join(lines),
            title="hermes-cli diff scratchpad",
            border_style="green" if result["aligned"] else "yellow",
        )
        out_console.print(panel)

    if not result["aligned"]:
        raise typer.Exit(code=1)
    raise typer.Exit(code=0)


@app.command()
def stats(
    month: str | None = typer.Option(
        None,
        "--month",
        help="Filtra per mese (formato YYYY-MM).",
    ),
    agent: str | None = typer.Option(
        None,
        "--agente",
        help="Filtra per agente mittente.",
    ),
    json_output: bool = typer.Option(False, "--json", help="Output in formato JSON."),
) -> None:
    if json_output:
        _json_state["json"] = True
    handoff_paths = scan_handoff_files(HANDOFF_DIR)
    result = generate_stats(handoff_paths, month=month, agent=agent)

    if _json_state["json"]:
        _emit_json(result)
        return

    lines: list[str] = []
    prefix = ""
    if result.get("filtered"):
        parts = []
        if result.get("filter_month"):
            parts.append(f"mese={result['filter_month']}")
        if result.get("filter_agent"):
            parts.append(f"agente={result['filter_agent']}")
        prefix = f" ({', '.join(parts)})"

    lines.append("  [bold]Statistiche Team Olimpo[/bold]")
    lines.append("")

    lines.append("  [bold]Task per agente:[/bold]")
    for aname, info in result["tasks_by_agent"].items():
        lines.append(
            f"    {aname.capitalize():12s}: "
            f"{info['total']} (completati: {info['completed']}, "
            f"in corso: {info['in_progress']})"
        )
    lines.append("")

    lines.append("  [bold]Handoff per tipo:[/bold]")
    for tipo, count in result["handoffs_by_type"].items():
        lines.append(f"    {tipo:15s}: {count}")
    lines.append("")

    lines.append("  [bold]Volume per mese:[/bold]")
    for mese, count in result["handoffs_by_month"].items():
        lines.append(f"    {mese}: {count} handoff")

    panel = Panel(
        "\n".join(lines),
        title=f"hermes-cli stats{prefix}",
        border_style="blue",
    )
    out_console.print(panel)
