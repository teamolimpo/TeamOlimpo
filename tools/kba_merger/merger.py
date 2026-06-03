"""
Logica di merge delle righe dell'export DeltaV.

Replica fedelmente la logica dello script JS Office:
- chiave di raggruppamento: KBA Number + Category + Disposition Status + Site
- Site: primo match case-insensitive tra i siti noti in System Name (ID)
- Node Names: set distinti, join con newline
- User Notes: split su regex, dedup, sort per timestamp desc
"""

from __future__ import annotations

import re
from calendar import month_abbr
from typing import Any

from loguru import logger

from tools.kba_merger.config import KNOWN_SITES

# Mappa mese abbreviato inglese -> numero (es. "Jan" -> 1)
_MONTH_MAP: dict[str, int] = {m.lower(): i for i, m in enumerate(month_abbr) if m}


def _extract_site(system_name: str) -> str:
    """
    Estrae il sito da System Name (ID) cercando un match case-insensitive
    tra i siti noti. Se nessuno corrisponde, restituisce l'intero valore.

    Args:
        system_name: Valore della colonna 'System Name (ID)'.

    Returns:
        Stringa sito (es. "Montecchio") o system_name originale.
    """
    if not system_name:
        return system_name
    lower = system_name.lower()
    for site in KNOWN_SITES:
        if site.lower() in lower:
            return site
    return system_name


def _parse_note_timestamp(note: str) -> tuple[int, int, int, int, int]:
    """
    Estrae il timestamp da una nota nel formato '[Autore, DD Mon YYYY HH:MM]'.

    Args:
        note: Stringa della singola nota.

    Returns:
        Tupla (anno, mese, giorno, ora, minuto) per confronto, o (0,0,0,0,0) come fallback.
    """
    match = re.search(
        r"\[.*?,\s*(\d{1,2})\s+([A-Za-z]{3})\s+(\d{4})\s+(\d{1,2}):(\d{2})\]",
        note,
    )
    if not match:
        return (0, 0, 0, 0, 0)
    day = int(match.group(1))
    month = _MONTH_MAP.get(match.group(2).lower(), 0)
    year = int(match.group(3))
    hour = int(match.group(4))
    minute = int(match.group(5))
    return (year, month, day, hour, minute)


def _merge_notes(notes_list: list[str]) -> str:
    """
    Dedup + sort discendente per timestamp delle note.

    Ogni stringa in notes_list puo' contenere piu' note separate da newline
    prima di '['. Le split su newline-prima-di-parentesi per separarle.

    Args:
        notes_list: Lista di stringhe User Notes grezze.

    Returns:
        Stringa con le note dedup + sorted, join con '\n'.
    """
    seen: set[str] = set()
    all_notes: list[str] = []

    for raw in notes_list:
        if not raw or not raw.strip():
            continue
        # Split su newline seguito da '[' (inizio di una nuova nota)
        parts = re.split(r"\n(?=\[)", raw.strip())
        for part in parts:
            part = part.strip()
            if part and part not in seen:
                seen.add(part)
                all_notes.append(part)

    # Sort per timestamp desc (piu' recente prima)
    all_notes.sort(key=_parse_note_timestamp, reverse=True)
    return "\n".join(all_notes)


def merge_rows(rows: list[dict[str, Any]], headers: list[str]) -> list[dict[str, Any]]:
    """
    Raggruppa le righe dell'export DeltaV per chiave di merge.

    Chiave: KBA Number + '|||' + Category + '|||' + Disposition Status + '|||' + Site

    Args:
        rows: Lista di dizionari riga (campo -> valore).
        headers: Lista degli header originali del file Excel (usati per validazione).

    Returns:
        Lista di dizionari con i campi merged, uno per chiave unica.
        Ordine: prima apparizione della chiave.
    """
    # Verifica che le colonne attese esistano
    required = [
        "KBA Number",
        "Published",
        "Category",
        "Disposition Status",
        "Title",
        "System Name (ID)",
        "Node Name / Node Assignment",
        "User Notes",
    ]
    missing = [c for c in required if c not in headers]
    if missing:
        raise ValueError(f"Colonne mancanti nel file DeltaV: {missing}")

    merged: dict[str, dict[str, Any]] = {}
    order: list[str] = []

    for row in rows:
        kba = str(row.get("KBA Number") or "").strip()
        category = str(row.get("Category") or "").strip()
        disposition = str(row.get("Disposition Status") or "").strip()
        system_name = str(row.get("System Name (ID)") or "").strip()
        site = _extract_site(system_name)
        node = str(row.get("Node Name / Node Assignment") or "").strip()
        notes_raw = str(row.get("User Notes") or "").strip()

        key = f"{kba}|||{category}|||{disposition}|||{site}"

        if key not in merged:
            merged[key] = {
                "KBA Number": kba,
                "Published": row.get("Published"),
                "Category": category,
                "Disposition Status": disposition,
                "Title": str(row.get("Title") or "").strip(),
                "Site": site,
                "_nodes": set(),
                "_notes_raw": [],
            }
            order.append(key)

        entry = merged[key]

        if node:
            entry["_nodes"].add(node)

        if notes_raw:
            entry["_notes_raw"].append(notes_raw)

    # Assemblaggio finale
    result: list[dict[str, Any]] = []
    for key in order:
        entry = merged[key]
        nodes_sorted = sorted(entry["_nodes"])
        notes_merged = _merge_notes(entry["_notes_raw"])

        result.append(
            {
                "KBA Number": entry["KBA Number"],
                "Published": entry["Published"],
                "Category": entry["Category"],
                "Disposition Status": entry["Disposition Status"],
                "Title": entry["Title"],
                "Site": entry["Site"],
                "Node Name / Node Assignment": "\n".join(nodes_sorted),
                "User Notes": notes_merged,
            }
        )

    logger.debug(f"Merge completato: {len(rows)} righe input -> {len(result)} righe output")
    return result
