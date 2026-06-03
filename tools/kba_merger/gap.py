"""
Logica del gap check per il tool kba_merger.

Per ogni KBA Number unico nel file DeltaV:
  - stato 'ok'              -> presente in kba_catalog/records/ con analyzed_at >= converted_at
  - stato 'da_rianalizzare' -> record presente ma documento piu' recente
    (converted_at > analyzed_at)
  - stato 'da_analizzare'   -> MD convertito in lib/documents/ ma nessun record
  - stato 'da_convertire'   -> PDF non ancora convertito (nessun MD in lib/documents/)

Il flag recursive=True estende la verifica alle KBA referenziate da fix_reference
nei record del catalogo, in modo transitivo (BFS). Le KBA mancanti vengono
aggiunte al risultato con il campo 'referenced_by' che indica chi le cita.
"""

from __future__ import annotations

import re
from typing import Any

import yaml
from loguru import logger

from tools.kba_merger.config import DOCUMENTS_DIR, RECORDS_DIR

# Pattern per estrarre ID KBA da stringhe libere (es. fix_reference)
_KBA_ID_RE = re.compile(r"\b([A-Z]{2}-\d{4}-\d{4})\b")

# Pattern per estrarre data ISO dal frontmatter (YYYY-MM-DD, anche con timestamp dopo)
_DATE_RE = re.compile(r"(\d{4}-\d{2}-\d{2})")


def _extract_frontmatter_date(text: str, field: str) -> str:
    """
    Estrae un campo data dal frontmatter YAML di un file Markdown.

    Supporta sia date semplici ('YYYY-MM-DD') che timestamp
    ('YYYY-MM-DD HH:MM:SS...'). Restituisce solo la parte YYYY-MM-DD.

    Args:
        text: Contenuto del file Markdown.
        field: Nome del campo da estrarre (es. 'converted_at', 'analyzed_at').

    Returns:
        Stringa data in formato ISO 'YYYY-MM-DD', o '' se non trovata.
    """
    pattern = re.compile(
        rf"^{re.escape(field)}:\s*(['\"]?)(\d{{4}}-\d{{2}}-\d{{2}})",
        re.MULTILINE,
    )
    match = pattern.search(text)
    if match:
        return match.group(2)
    return ""


def _get_status(slug: str) -> str:
    """
    Determina lo stato di copertura di una singola KBA.

    Args:
        slug: Identificatore KBA in lowercase (es. 'nk-1000-0109').

    Returns:
        Una delle quattro stringhe: 'ok', 'da_rianalizzare', 'da_analizzare', 'da_convertire'.
    """
    record_path = RECORDS_DIR / f"{slug}.md"
    doc_path = DOCUMENTS_DIR / f"{slug}.md"

    if not record_path.exists():
        if doc_path.exists():
            return "da_analizzare"
        return "da_convertire"

    # Record esiste — confronta converted_at (doc) vs analyzed_at (record)
    if not doc_path.exists():
        # Caso strano: record presente ma documento assente — ok per compatibilita'
        return "ok"

    try:
        doc_text = doc_path.read_text(encoding="utf-8")
        rec_text = record_path.read_text(encoding="utf-8")
    except OSError:
        return "ok"

    converted_str = _extract_frontmatter_date(doc_text, "converted_at")
    analyzed_str = _extract_frontmatter_date(rec_text, "analyzed_at")

    if not converted_str or not analyzed_str:
        # Non possiamo confrontare — consideralo ok
        return "ok"

    if converted_str > analyzed_str:  # confronto ISO lessicografico
        return "da_rianalizzare"

    return "ok"


def _read_fix_references(slug: str) -> list[str]:
    """
    Legge il campo fix_reference dal frontmatter YAML del record catalogo.
    Estrae tutti gli ID KBA presenti nel valore (formato XX-NNNN-NNNN).

    Args:
        slug: Slug KBA in lowercase.

    Returns:
        Lista di ID KBA referenziati (uppercase, deduplicati).
    """
    record_path = RECORDS_DIR / f"{slug}.md"
    if not record_path.exists():
        return []
    try:
        text = record_path.read_text(encoding="utf-8")
        if not text.startswith("---"):
            return []
        parts = text.split("---", 2)
        if len(parts) < 3:
            return []
        meta = yaml.safe_load(parts[1]) or {}
        fix_ref = str(meta.get("fix_reference") or "")
        return list(dict.fromkeys(m.upper() for m in _KBA_ID_RE.findall(fix_ref)))
    except Exception as exc:
        logger.warning(f"Errore lettura fix_reference per {slug}: {exc}")
        return []


def _expand_recursive(
    initial_kbas: set[str],
) -> dict[str, list[str]]:
    """
    BFS sui fix_reference del catalogo.

    Parte dalle KBA iniziali (già nel file DeltaV), espande ricorsivamente
    le KBA referenziate finché non ci sono nuovi ID da visitare.

    Args:
        initial_kbas: Set di KBA Number già presenti nel file DeltaV (uppercase).

    Returns:
        Dizionario {kba_id: [referenziata_da, ...]} per le KBA referenziate
        che non erano nel set iniziale. Le KBA del set iniziale non compaiono
        nel dizionario, anche se sono referenziate.
    """
    visited: set[str] = set(initial_kbas)
    # Queue: KBA di cui leggere i fix_reference (quelle con record nel catalogo)
    queue: list[str] = [
        k for k in initial_kbas if _get_status(k.lower()) in ("ok", "da_rianalizzare")
    ]
    referenced_by: dict[str, list[str]] = {}

    while queue:
        current = queue.pop(0)
        refs = _read_fix_references(current.lower())
        for ref in refs:
            if ref not in visited:
                visited.add(ref)
                referenced_by[ref] = [current]
                # Se anche il referenziato ha un record, espandiamo da lui
                if _get_status(ref.lower()) in ("ok", "da_rianalizzare"):
                    queue.append(ref)
            elif ref in referenced_by and current not in referenced_by[ref]:
                referenced_by[ref].append(current)

    return referenced_by


def compute_gap(
    rows: list[dict[str, Any]],
    recursive: bool = False,
) -> list[dict[str, Any]]:
    """
    Calcola lo stato di copertura per tutte le KBA uniche nel file DeltaV.

    Args:
        rows: Lista di dizionari riga (output grezzo lettura Excel, prima del merge).
        recursive: Se True, espande il check alle KBA referenziate da fix_reference
                   nei record del catalogo (BFS transitivo). Le KBA aggiuntive
                   compaiono nel risultato con occurrences=0 e referenced_by valorizzato.

    Returns:
        Lista di dizionari con chiavi:
          kba_number, published, category, disposition_status, title,
          occurrences, stato, referenced_by (lista, vuota se non ricorsivo)
        Ordinata: prima per occurrences decrescenti, poi le referenziate (occ=0).
    """
    # Raccoglie metadati e conta occorrenze per KBA Number
    kba_meta: dict[str, dict[str, Any]] = {}
    kba_count: dict[str, int] = {}

    for row in rows:
        kba = str(row.get("KBA Number") or "").strip()
        if not kba:
            continue
        kba_count[kba] = kba_count.get(kba, 0) + 1
        if kba not in kba_meta:
            kba_meta[kba] = {
                "published": row.get("Published"),
                "category": str(row.get("Category") or "").strip(),
                "disposition_status": str(row.get("Disposition Status") or "").strip(),
                "title": str(row.get("Title") or "").strip(),
            }

    result: list[dict[str, Any]] = []
    for kba, meta in kba_meta.items():
        slug = kba.lower()
        stato = _get_status(slug)
        logger.debug(f"Gap check {kba}: {stato}")
        result.append(
            {
                "kba_number": kba,
                "published": meta["published"],
                "category": meta["category"],
                "disposition_status": meta["disposition_status"],
                "title": meta["title"],
                "occurrences": kba_count[kba],
                "stato": stato,
                "referenced_by": [],
            }
        )

    # ── Espansione ricorsiva ──────────────────────────────────────────────────
    if recursive:
        referenced_by = _expand_recursive(set(kba_meta.keys()))
        existing = {r["kba_number"] for r in result}

        for ref_kba, parents in referenced_by.items():
            if ref_kba in existing:
                continue  # già nel file DeltaV, non duplichiamo
            slug = ref_kba.lower()
            stato = _get_status(slug)
            if stato == "ok":
                continue  # referenziata e presente — nessun problema
            logger.debug(f"Gap ricorsivo {ref_kba}: {stato} (da {parents})")
            result.append(
                {
                    "kba_number": ref_kba,
                    "published": None,
                    "category": "",
                    "disposition_status": "",
                    "title": f"[referenziata da: {', '.join(parents)}]",
                    "occurrences": 0,
                    "stato": stato,
                    "referenced_by": parents,
                }
            )
    # ─────────────────────────────────────────────────────────────────────────

    # Ordinamento: prima per occorrenze desc, poi le referenziate (occ=0)
    result.sort(key=lambda r: (-r["occurrences"], r["kba_number"]))
    return result
