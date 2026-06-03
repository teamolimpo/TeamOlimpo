"""
Scanner per i file handoff del Team Olimpo.

Legge i frontmatter YAML di tutti i file .md presenti ricorsivamente in
HANDOFF_DIR, saltando le cartelle in SKIP_DIRS e Registro.md.

Lo stato archiviato viene derivato dal frontmatter (stato == "completato"),
non più dalla posizione nel filesystem.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import yaml
from loguru import logger

from tools.handoff_register.config import HANDOFF_DIR, REGISTRO_PATH, SKIP_DIRS


# ---------------------------------------------------------------------------
# Struttura dati di un handoff
# ---------------------------------------------------------------------------


@dataclass
class HandoffRecord:
    """Rappresenta i metadati di un singolo file handoff."""

    path: Path

    # True se stato == "completato"
    is_archived: bool

    data: str | None = None
    mittente: str | None = None
    destinatario: str | None = None
    tipo: str | None = None
    stato: str | None = None
    priorita: str | None = None
    titolo: str | None = None

    processato_da: str | None = None
    processato_il: str | None = None

    has_warnings: bool = False
    warning_messages: list[str] = field(default_factory=list)

    @property
    def display_data(self) -> str:
        return str(self.data) if self.data else ""

    @property
    def sort_key(self) -> str:
        return self.display_data or "0000-00-00"


# ---------------------------------------------------------------------------
# Lettura frontmatter
# ---------------------------------------------------------------------------


def _read_frontmatter(path: Path) -> tuple[dict[str, Any], list[str]]:
    """
    Legge e parsa il frontmatter YAML da un file Markdown.

    Args:
        path: Path al file .md.

    Returns:
        Tupla (frontmatter_dict, lista_warning).
        frontmatter_dict è vuoto se il file non ha frontmatter o in caso di errore.
    """
    warnings: list[str] = []

    try:
        text = path.read_text(encoding="utf-8")
    except OSError as exc:
        warnings.append(f"impossibile leggere il file: {exc}")
        return {}, warnings

    # Il frontmatter deve iniziare esattamente a riga 1
    if not text.startswith("---"):
        warnings.append("frontmatter YAML assente (il file non inizia con '---')")
        return {}, warnings

    # Trova la chiusura del blocco YAML
    end_marker = text.find("\n---", 3)
    if end_marker == -1:
        warnings.append("frontmatter YAML non chiuso (marker '---' di chiusura assente)")
        return {}, warnings

    yaml_block = text[3:end_marker].strip()

    try:
        parsed = yaml.safe_load(yaml_block)
    except yaml.YAMLError as exc:
        warnings.append(f"errore YAML: {exc}")
        return {}, warnings

    if not isinstance(parsed, dict):
        warnings.append("il frontmatter non è un mapping YAML valido")
        return {}, warnings

    return parsed, warnings


def _validate_frontmatter(fm: dict[str, Any], path: Path) -> list[str]:
    """
    Verifica la presenza dei campi obbligatori nel frontmatter.

    Args:
        fm: Dizionario frontmatter già parsato.
        path: Path del file (per messaggi di warning contestuali).

    Returns:
        Lista di messaggi di warning per i campi mancanti o non validi.
    """
    warnings: list[str] = []
    required = ("data", "mittente", "destinatario", "tipo", "stato", "priorita", "titolo")

    for campo in required:
        if campo not in fm or fm[campo] is None:
            warnings.append(f"campo obbligatorio mancante: '{campo}'")

    return warnings


def _build_record(path: Path) -> HandoffRecord:
    fm, read_warnings = _read_frontmatter(path)
    validation_warnings = _validate_frontmatter(fm, path) if fm else []
    all_warnings = read_warnings + validation_warnings

    has_warnings = bool(all_warnings)

    if has_warnings:
        for msg in all_warnings:
            logger.warning(f"[scanner] {path.name}: {msg}")

    raw_data = fm.get("data")
    data_str: str | None = None
    if raw_data is not None:
        data_str = str(raw_data)

    stato = str(fm["stato"]).lower() if fm.get("stato") else None
    is_archived = stato == "completato"

    return HandoffRecord(
        path=path,
        is_archived=is_archived,
        data=data_str,
        mittente=str(fm["mittente"]).lower() if fm.get("mittente") else None,
        destinatario=str(fm["destinatario"]).lower() if fm.get("destinatario") else None,
        tipo=str(fm["tipo"]).lower() if fm.get("tipo") else None,
        stato=stato,
        priorita=str(fm["priorita"]).lower() if fm.get("priorita") else None,
        titolo=str(fm["titolo"]) if fm.get("titolo") else None,
        processato_da=str(fm["processato_da"]).lower() if fm.get("processato_da") else None,
        processato_il=str(fm["processato_il"]) if fm.get("processato_il") else None,
        has_warnings=has_warnings,
        warning_messages=all_warnings,
    )


# ---------------------------------------------------------------------------
# Scan ricorsivo
# ---------------------------------------------------------------------------


def _is_scannable(path: Path) -> bool:
    if path.suffix.lower() != ".md":
        return False
    if path.resolve() == REGISTRO_PATH.resolve():
        return False
    for parent in path.parents:
        if parent.name in SKIP_DIRS:
            return False
    return True


def scan_all(handoff_dir: Path = HANDOFF_DIR) -> tuple[list[HandoffRecord], list[HandoffRecord]]:
    """
    Scansiona ricorsivamente HANDOFF_DIR e divide per stato.

    Salta: templates/, kba_batch/, kba_batch2/, tucson/, Legacy/, scripts/, e Registro.md.

    Args:
        handoff_dir: Cartella radice. Default: HANDOFF_DIR.

    Returns:
        Tupla (attivi, archiviati), ciascuna ordinata per data discendente.
    """
    if not handoff_dir.exists():
        logger.debug(f"[scanner] Cartella non trovata: {handoff_dir}")
        return [], []

    attivi: list[HandoffRecord] = []
    archiviati: list[HandoffRecord] = []

    for path in sorted(handoff_dir.rglob("*.md")):
        if not _is_scannable(path):
            logger.debug(f"[scanner] Saltato: {path}")
            continue

        record = _build_record(path)
        if record.is_archived:
            archiviati.append(record)
            logger.debug(f"[scanner] Letto archiviato: {path.name}")
        else:
            attivi.append(record)
            logger.debug(f"[scanner] Letto attivo: {path.name} (stato={record.stato})")

    attivi.sort(key=lambda r: r.sort_key, reverse=True)
    archiviati.sort(key=lambda r: r.sort_key, reverse=True)
    logger.debug(f"[scanner] Totale: {len(attivi)} attivi, {len(archiviati)} archiviati")
    return attivi, archiviati
