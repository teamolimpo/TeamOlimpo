"""Scrive i file Markdown di output: lista patch fermata e brief WIP."""

from pathlib import Path
from datetime import date

from tools.kba_reporter.config import GROK_MODEL


def write_patch_list(patch_data: dict, output_path: Path) -> None:
    """Scrive il file Markdown con la lista patch per fermata, organizzata per sito."""
    lines = [f"# Attività in fermata — {date.today().strftime('%B %Y')}\n"]
    for site in sorted(patch_data.keys()):
        data = patch_data[site]
        lines.append(f"\n---\n\n## {site}\n")

        # Patch Microsoft — Workstation DeltaV
        ws_ms = data.get("workstation_ms", {})
        if ws_ms:
            lines.append("### Patch Microsoft — Workstation DeltaV\n")
            for fname in sorted(ws_ms.keys()):
                nodes = ws_ms[fname]
                label = fname
                if "ALL" in fname and "64bit" in fname:
                    label = (
                        fname + "  *(applicare il file per l'OS del nodo: Win10 / S2016 / S2022)*"
                    )
                lines.append(f"**{label}**")
                for n in sorted(nodes):
                    lines.append(f"- {n}")
                lines.append("")

        # Patch Microsoft — Server / Hypervisor
        srv_ms = data.get("server_ms", {})
        if srv_ms:
            lines.append("### Patch Microsoft — Server / Hypervisor\n")
            for fname in sorted(srv_ms.keys()):
                nodes = srv_ms[fname]
                lines.append(f"**{fname}**")
                for n in sorted(nodes):
                    lines.append(f"- {n}")
                lines.append("")

        # Firmware DeltaV
        firmware = data.get("firmware", {})
        if firmware:
            lines.append("### Firmware DeltaV\n")
            for fname in sorted(firmware.keys()):
                info = firmware[fname]
                lines.append(f"**{fname}**")
                label = (
                    "Controller da flashare:"
                    if info["type"] == "controller"
                    else "Schede da flashare:"
                )
                lines.append(label)
                if info["nodes"]:
                    for n in sorted(info["nodes"]):
                        lines.append(f"- {n}")
                else:
                    lines.append("- tutti i nodi I/O del sito")
                lines.append("")

    output_path.write_text("\n".join(lines), encoding="utf-8")


def _risk_label(risk_level: str, risk_score) -> str:
    label = str(risk_level).capitalize() if risk_level else "N/D"
    if risk_score:
        label += f" ({risk_score})"
    return label


def _build_azioni(record: dict) -> list[str]:
    """
    Deriva la lista azioni dal catalog record.
    Usa workaround_text se disponibile, poi fix_reference, poi raccomandazione.
    """
    azioni = []
    reco = (record.get("raccomandazione") or "").strip().lower()
    wk = (record.get("workaround_text") or "").strip()
    fix_ref = (record.get("fix_reference") or "").strip()
    note = (record.get("note") or "").strip()

    if reco in ("nessuna_azione", "monitorare"):
        azioni.append(
            "Nessuna azione urgente — segnalare se il comportamento viene osservato nei siti."
        )
        return azioni

    if wk and reco == "applicare_workaround":
        azioni.append(f"Applicare il workaround: {wk}.")
    elif wk:
        azioni.append(wk)

    if fix_ref and fix_ref.lower() not in ("n/a", "n/a - issue under investigation", ""):
        azioni.append(f"Riferimento fix: {fix_ref}.")

    if note:
        # Includi la nota come contesto aggiuntivo se non è già nelle azioni
        azioni.append(note)

    if not azioni:
        azioni.append("Verificare l'applicabilità nei siti e segnalare a FIS.")

    return azioni


def write_kba_discussion(brief_data: list[dict], output_path: Path) -> None:
    """
    Scrive il file kba-da-discutere con il formato compatto per meeting cliente.
    Una sezione per KBA: Situazione (2 righe) + Azioni (lista numerata).
    """
    today = date.today().isoformat()
    lines = [
        "---",
        f"generato: {today}",
        "source: kba_reporter",
        "---",
        "",
        "# KBA da discutere con il cliente",
        "",
        "---",
        "",
    ]

    for r in brief_data:
        kba = r["kba_number"]
        # Titolo breve: rimuovi prefisso KBA dal titolo se presente
        title_full = r.get("title", "")
        title_short = title_full.replace(f"{kba}: ", "").replace(f"{kba} — ", "")
        # Troncamento a 80 char
        if len(title_short) > 80:
            title_short = title_short[:77] + "..."

        risk = _risk_label(r.get("risk_level", ""), r.get("risk_score", ""))
        sites = ", ".join(r.get("sites", [])) or "da verificare"

        lines.append(f"### {kba} — {title_short}")
        lines.append(f"**Rischio**: {risk}  |  **Siti**: {sites}")
        lines.append("")

        situazione = (r.get("sintesi") or "").strip()
        if situazione:
            lines.append(f"**Situazione**: {situazione}")
        else:
            lines.append(
                "**Situazione**: *(analisi non disponibile — rilancia kba_reporter dopo analisi Grok)*"
            )
        lines.append("")

        azioni = _build_azioni(r)
        lines.append("**Azioni**:")
        for i, a in enumerate(azioni, 1):
            lines.append(f"{i}. {a}")
        lines.append("")
        lines.append("---")
        lines.append("")

    output_path.write_text("\n".join(lines), encoding="utf-8")


def write_wip_brief(brief_data: list[dict], output_path: Path) -> None:
    """Scrive il file Markdown con il brief WIP per Poros / Grok."""
    today = date.today().isoformat()
    da_analizzare = [r for r in brief_data if r["stato"] in ("ANALIZZA", "MANCANTE")]
    skip = [r for r in brief_data if r["stato"] == "SKIP"]

    lines = [
        "---",
        f"generato: {today}",
        "tool: kba_reporter",
        f"modello_grok: {GROK_MODEL}",
        "---",
        "",
        "# Brief WIP — KBA da analizzare",
        "",
        "## Riepilogo",
        f"- Totale KBA WIP: {len(brief_data)}",
        f"- Da analizzare: {len(da_analizzare)}",
        f"- Già fresche (skip): {len(skip)}",
        f"- Modello Grok: {GROK_MODEL}",
        "",
    ]

    if da_analizzare:
        lines += [
            "## KBA da analizzare",
            "",
            "| KBA | Titolo | Siti | Risk Level | Stato | Ultima analisi | Source |",
            "|-----|--------|------|------------|-------|----------------|--------|",
        ]
        for r in da_analizzare:
            siti = ", ".join(r["sites"])
            lines.append(
                f"| {r['kba_number']} | {r['title'][:60]} | {siti} | "
                f"{r['risk_level']} | {r['stato']} | {r['analyzed_at']} | {r['source']} |"
            )
        lines.append("")

    if skip:
        lines += [
            "## KBA già fresche (skip)",
            "",
            "| KBA | Titolo | Ultima analisi | Source |",
            "|-----|--------|----------------|--------|",
        ]
        for r in skip:
            lines.append(
                f"| {r['kba_number']} | {r['title'][:60]} | {r['analyzed_at']} | {r['source']} |"
            )
        lines.append("")

    if da_analizzare:
        lines += [
            "---",
            "",
            "> Passa questo file a Poros per avviare l'analisi Grok + Dike"
            " sulle KBA in stato ANALIZZA o MANCANTE.",
            "",
        ]

    output_path.write_text("\n".join(lines), encoding="utf-8")
