"""
Writer per il file Registro.md del sistema handoff del Team Olimpo.

Genera REGISTRO_PATH a partire dalle liste di HandoffRecord.
Il file è sempre riscritto completamente — non viene mai modificato a mano.

Formato prodotto:
  - Frontmatter YAML con titolo, timestamp e tags
  - Sezione "File attivi" con tabella ordinata per data discendente
  - Sezione "File archiviati" con tabella ordinata per data discendente
"""

from __future__ import annotations

from datetime import datetime
from pathlib import Path
from typing import Sequence

from loguru import logger

from tools.handoff_register.config import REGISTRO_PATH
from tools.handoff_register.scanner import HandoffRecord


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _cell(value: str | None, fallback: str = "—") -> str:
    """Restituisce il valore o un placeholder se assente/vuoto."""
    v = str(value).strip() if value else ""
    return v if v else fallback


def _render_active_table(records: Sequence[HandoffRecord]) -> str:
    """
    Genera la tabella Markdown degli handoff attivi.

    Args:
        records: Lista di HandoffRecord con is_archived=False.

    Returns:
        Stringa Markdown della tabella (senza newline finale extra).
    """
    header = (
        "| Data | Da | A | Tipo | Titolo | Stato | Priorità |\n"
        "|------|----|---|------|--------|-------|---------|"
    )

    if not records:
        return f"{header}\n| — | — | — | — | — | — | — |"

    rows = []
    for r in records:
        row = (
            f"| {_cell(r.data)} "
            f"| {_cell(r.mittente)} "
            f"| {_cell(r.destinatario)} "
            f"| {_cell(r.tipo)} "
            f"| {_cell(r.titolo)} "
            f"| {_cell(r.stato)} "
            f"| {_cell(r.priorita)} |"
        )
        rows.append(row)

    return header + "\n" + "\n".join(rows)


def _render_archived_table(records: Sequence[HandoffRecord]) -> str:
    """
    Genera la tabella Markdown degli handoff archiviati.

    Args:
        records: Lista di HandoffRecord con is_archived=True.

    Returns:
        Stringa Markdown della tabella (senza newline finale extra).
    """
    header = (
        "| Data | Da | A | Tipo | Titolo | Completato il | Processato da |\n"
        "|------|----|---|------|--------|--------------|--------------|"
    )

    if not records:
        return f"{header}\n| — | — | — | — | — | — | — |"

    rows = []
    for r in records:
        row = (
            f"| {_cell(r.data)} "
            f"| {_cell(r.mittente)} "
            f"| {_cell(r.destinatario)} "
            f"| {_cell(r.tipo)} "
            f"| {_cell(r.titolo)} "
            f"| {_cell(r.processato_il)} "
            f"| {_cell(r.processato_da)} |"
        )
        rows.append(row)

    return header + "\n" + "\n".join(rows)


# ---------------------------------------------------------------------------
# Funzione principale
# ---------------------------------------------------------------------------


def write_registro(
    active_records: Sequence[HandoffRecord],
    archived_records: Sequence[HandoffRecord],
    registro_path: Path = REGISTRO_PATH,
    now: datetime | None = None,
) -> None:
    """
    Genera e scrive il file Registro.md.

    Sovrascrive il file esistente se presente. Crea le directory intermedie
    se necessario.

    Args:
        active_records:   Handoff attivi (da-processare, in-corso, bloccato).
        archived_records: Handoff archiviati (completato).
        registro_path:    Path di destinazione. Default: REGISTRO_PATH.
        now:              Timestamp da usare nell'header. Default: datetime.now().

    Raises:
        OSError: Se la scrittura del file fallisce.
    """
    if now is None:
        now = datetime.now()

    ts_iso = now.strftime("%Y-%m-%dT%H:%M:%S")
    ts_readable = now.strftime("%Y-%m-%d %H:%M")

    active_table = _render_active_table(active_records)
    archived_table = _render_archived_table(archived_records)

    content = f"""---
title: Registro Handoff — Team Olimpo
generato_il: {ts_iso}
tags: [handoff, registro]
---

# Registro Handoff

> Generato automaticamente da `tools/handoff_register`. Non modificare a mano.
> Ultimo aggiornamento: {ts_readable}

## File attivi

{active_table}

## File archiviati

{archived_table}
"""

    registro_path.parent.mkdir(parents=True, exist_ok=True)
    registro_path.write_text(content, encoding="utf-8")

    logger.info(
        f"[writer] Registro scritto: {registro_path} "
        f"({len(active_records)} attivi, {len(archived_records)} archiviati)"
    )
