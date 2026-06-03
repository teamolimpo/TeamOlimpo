"""
Writer per il catalogo KBA del Team Olimpo.

Scrive record MD nel formato usato da Dike in lib/data/kba_catalog/records/
e riscrive index.yaml da zero leggendo tutti i record presenti.
"""

from __future__ import annotations

from datetime import date
from pathlib import Path
from typing import Any

import yaml
from loguru import logger

from tools.kba_indexer.config import INDEX_FILE, RECORDS_DIR


# ---------------------------------------------------------------------------
# Costruzione del body Markdown
# ---------------------------------------------------------------------------


def _build_body(body_data: dict[str, Any]) -> str:
    """
    Costruisce il body Markdown del record a partire dai dati estratti dal JSON.

    Args:
        body_data: Dizionario con i campi del body (campo '_body' del record parsato).

    Returns:
        Stringa Markdown del body.
    """
    lines: list[str] = []

    # Sezione Sintesi
    lines.append("## Sintesi")
    lines.append("")
    summary = body_data.get("kba_problem_summary", "")
    lines.append(summary if summary else "_Nessuna sintesi disponibile._")
    lines.append("")

    # Sezione Analisi del rischio
    lines.append("## Analisi del rischio")
    lines.append("")

    sev_just = body_data.get("severity_justification", "")
    occ_just = body_data.get("occurrence_justification", "")
    det_just = body_data.get("detectability_justification", "")

    if sev_just:
        lines.append("### Severita'")
        lines.append("")
        lines.append(sev_just)
        lines.append("")

    if occ_just:
        lines.append("### Occorrenza")
        lines.append("")
        lines.append(occ_just)
        lines.append("")

    if det_just:
        lines.append("### Rilevabilita'")
        lines.append("")
        lines.append(det_just)
        lines.append("")

    calc = body_data.get("risk_score_calculation", "")
    if calc:
        lines.append("### Score composito")
        lines.append("")
        lines.append("```")
        lines.append(calc)
        lines.append("```")
        lines.append("")

    modifiers: list[dict[str, Any]] = body_data.get("modifiers_applied", [])
    if modifiers:
        lines.append("### Modificatori applicati")
        lines.append("")
        for mod in modifiers:
            name = mod.get("modifier", "")
            adj = mod.get("adjustment", 0)
            reason = mod.get("reason", "")
            sign = "+" if isinstance(adj, (int, float)) and adj >= 0 else ""
            lines.append(f"- **{name}** ({sign}{adj}): {reason}")
        lines.append("")

    # Sezione Workaround
    workaround = body_data.get("workaround_description", "")
    lines.append("## Workaround")
    lines.append("")
    lines.append(workaround if workaround else "_Nessun workaround disponibile._")
    lines.append("")

    # Sezione Raccomandazione
    rec = body_data.get("operational_recommendation", "")
    lines.append("## Raccomandazione")
    lines.append("")
    lines.append(rec if rec else "_Nessuna raccomandazione disponibile._")
    lines.append("")

    # Sezione Note
    notes = body_data.get("notes", "")
    divergence = body_data.get("divergence_from_emerson", False)
    divergence_exp = body_data.get("divergence_explanation", "")

    lines.append("## Note")
    lines.append("")
    if notes:
        lines.append(notes)
        lines.append("")
    if divergence and divergence_exp:
        lines.append("**Divergenza dalla classificazione Emerson:**")
        lines.append("")
        lines.append(divergence_exp)
        lines.append("")

    if not notes and not (divergence and divergence_exp):
        lines.append("_Nessuna nota aggiuntiva._")
        lines.append("")

    return "\n".join(lines)


# ---------------------------------------------------------------------------
# Costruzione del frontmatter YAML
# ---------------------------------------------------------------------------


def _build_frontmatter(record: dict[str, Any]) -> str:
    """
    Costruisce il frontmatter YAML del record nel formato di Dike.

    Usa yaml.dump per serializzazione corretta; costruisce la struttura a mano
    con commenti di sezione per mantenere la leggibilita'.

    Args:
        record: Dizionario con tutti i campi del record (senza '_body').

    Returns:
        Stringa con il frontmatter YAML completo, delimitatori inclusi.
    """
    sections: list[str] = ["---"]

    def _dump_field(key: str, value: Any) -> str:
        """Serializza un singolo campo YAML."""
        return yaml.dump(
            {key: value},
            default_flow_style=False,
            allow_unicode=True,
            sort_keys=False,
        ).rstrip()

    # Identificazione
    sections.append("# Identificazione")
    sections.append(_dump_field("kba_id", record["kba_id"]))
    sections.append(_dump_field("title", record["title"]))
    sections.append(_dump_field("source_file", record["source_file"]))
    sections.append(_dump_field("analyzed_at", record["analyzed_at"]))

    # Classificazione
    sections.append("")
    sections.append("# Classificazione")
    sections.append(_dump_field("emerson_category", record["emerson_category"]))
    sections.append(_dump_field("risk_score", record["risk_score"]))
    sections.append(_dump_field("risk_level", record["risk_level"]))

    # Scoring dettagliato
    sections.append("")
    sections.append("# Scoring dettagliato")
    sections.append(_dump_field("severity", record["severity"]))
    sections.append(_dump_field("occurrence", record["occurrence"]))
    sections.append(_dump_field("detectability", record["detectability"]))

    # Classificazione del problema
    sections.append("")
    sections.append("# Classificazione del problema")
    sections.append(_dump_field("problem_type", record["problem_type"]))
    sections.append(_dump_field("architecture_level", record["architecture_level"]))
    sections.append(_dump_field("impact_domains", record["impact_domains"]))

    # Componenti
    sections.append("")
    sections.append("# Componenti")
    sections.append(_dump_field("affected_products", record["affected_products"]))
    sections.append(_dump_field("affected_versions", record["affected_versions"]))

    # Mitigazioni
    sections.append("")
    sections.append("# Mitigazioni")
    sections.append(_dump_field("workaround_available", record["workaround_available"]))
    sections.append(_dump_field("workaround_complexity", record["workaround_complexity"]))
    sections.append(_dump_field("fix_available", record["fix_available"]))
    sections.append(_dump_field("fix_reference", record["fix_reference"]))
    sections.append(_dump_field("fix_versions", record.get("fix_versions", [])))

    # Metadati
    sections.append("")
    sections.append("# Metadati")
    sections.append(_dump_field("date_published", record["date_published"]))
    sections.append(_dump_field("author", record["author"]))
    sections.append(_dump_field("tags", record["tags"]))
    sections.append(_dump_field("source", record["source"]))
    sections.append(
        _dump_field("analyzed_by_provider", record.get("analyzed_by_provider", "unknown"))
    )
    sections.append(_dump_field("analyzed_by_model", record.get("analyzed_by_model", "unknown")))

    # Confidence
    sections.append("")
    sections.append("# Confidence")
    sections.append(_dump_field("confidence", record["confidence"]))
    sections.append(_dump_field("confidence_note", record["confidence_note"]))

    sections.append("---")
    return "\n".join(sections) + "\n"


# ---------------------------------------------------------------------------
# Scrittura del record
# ---------------------------------------------------------------------------


def write_record(record: dict[str, Any]) -> Path:
    """
    Scrive un record nel catalogo KBA.

    Crea il file MD in RECORDS_DIR/<slug>.md con frontmatter YAML + body Markdown.

    Args:
        record: Dizionario con i campi del record, incluso '_body' per il Markdown.

    Returns:
        Path al file scritto.
    """
    kba_id = record["kba_id"]
    slug = kba_id.lower()
    record_path = RECORDS_DIR / f"{slug}.md"

    RECORDS_DIR.mkdir(parents=True, exist_ok=True)

    body_data = record.get("_body", {})

    # Campi da escludere dal frontmatter
    frontmatter_record = {k: v for k, v in record.items() if not k.startswith("_")}

    frontmatter_str = _build_frontmatter(frontmatter_record)
    body_str = _build_body(body_data)

    content = frontmatter_str + "\n" + body_str

    record_path.write_text(content, encoding="utf-8")
    logger.info(f"Record scritto: {record_path}")
    return record_path


# ---------------------------------------------------------------------------
# Aggiornamento index.yaml
# ---------------------------------------------------------------------------


def _parse_record_for_index(record_path: Path) -> dict[str, Any] | None:
    """
    Legge un record MD e ne estrae i campi necessari per l'indice.

    Args:
        record_path: Path al file record MD.

    Returns:
        Dizionario con i campi indice, o None se il file non e' leggibile.
    """
    try:
        content = record_path.read_text(encoding="utf-8")
    except OSError as exc:
        logger.warning(f"Impossibile leggere record {record_path.name}: {exc}")
        return None

    # Estrae il frontmatter
    import re

    fm_match = re.match(r"\A---\s*\n([\s\S]*?)\n---\s*\n", content, re.MULTILINE)
    if not fm_match:
        logger.warning(f"Frontmatter mancante in {record_path.name}")
        return None

    try:
        fm = yaml.safe_load(fm_match.group(1))
    except yaml.YAMLError as exc:
        logger.warning(f"YAML non valido in {record_path.name}: {exc}")
        return None

    if not isinstance(fm, dict):
        return None

    return {
        "id": fm.get("kba_id", record_path.stem.upper()),
        "score": fm.get("risk_score", 0.0),
        "level": fm.get("risk_level", ""),
        "type": fm.get("problem_type", ""),
        "title": fm.get("title", ""),
    }


def _classify_level(level: str) -> str:
    """
    Mappa il risk_level al bucket della distribuzione.

    Args:
        level: Stringa del livello di rischio (es. "Advisory", "Warning").

    Returns:
        Chiave del bucket (critical, warning, advisory, informational, negligible).
    """
    mapping = {
        "critical": "critical",
        "warning": "warning",
        "advisory": "advisory",
        "informational": "informational",
        "negligible": "negligible",
    }
    return mapping.get(level.lower(), "advisory")


def rebuild_index() -> int:
    """
    Riscrive index.yaml da zero leggendo tutti i record in RECORDS_DIR.

    Non accumula: legge i file presenti e sovrascrive sempre l'indice.
    Questo garantisce coerenza anche dopo eliminazione o sovrascrittura di record.

    Returns:
        Numero totale di record indicizzati.
    """
    if not RECORDS_DIR.exists():
        logger.warning(f"Directory records non trovata: {RECORDS_DIR}")
        _write_empty_index()
        return 0

    record_files = sorted(RECORDS_DIR.glob("*.md"))
    entries: list[dict[str, Any]] = []
    distribution: dict[str, int] = {
        "critical": 0,
        "warning": 0,
        "advisory": 0,
        "informational": 0,
        "negligible": 0,
    }

    for record_path in record_files:
        entry = _parse_record_for_index(record_path)
        if entry is None:
            continue
        entries.append(entry)
        bucket = _classify_level(str(entry.get("level", "")))
        distribution[bucket] = distribution.get(bucket, 0) + 1

    index_data = {
        "catalog_updated": date.today().isoformat(),
        "total_entries": len(entries),
        "risk_distribution": distribution,
        "entries": entries,
    }

    INDEX_FILE.parent.mkdir(parents=True, exist_ok=True)
    INDEX_FILE.write_text(
        yaml.dump(
            index_data,
            default_flow_style=False,
            allow_unicode=True,
            sort_keys=False,
        ),
        encoding="utf-8",
    )
    logger.info(f"index.yaml riscritto: {len(entries)} record totali")
    return len(entries)


def _write_empty_index() -> None:
    """Scrive un index.yaml vuoto se non ci sono record."""
    empty = {
        "catalog_updated": date.today().isoformat(),
        "total_entries": 0,
        "risk_distribution": {
            "critical": 0,
            "warning": 0,
            "advisory": 0,
            "informational": 0,
            "negligible": 0,
        },
        "entries": [],
    }
    INDEX_FILE.parent.mkdir(parents=True, exist_ok=True)
    INDEX_FILE.write_text(
        yaml.dump(empty, default_flow_style=False, allow_unicode=True, sort_keys=False),
        encoding="utf-8",
    )
