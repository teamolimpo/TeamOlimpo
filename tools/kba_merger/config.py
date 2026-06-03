"""
Configurazione centralizzata per il tool kba_merger.

Tutti i path sono relativi alla root del progetto PKM.
La root viene determinata automaticamente risalendo dal file corrente.
"""

from __future__ import annotations

from pathlib import Path

from tools.common.paths import project_root

# ---------------------------------------------------------------------------
# Root del progetto
# ---------------------------------------------------------------------------
PROJECT_ROOT: Path = project_root()

# ---------------------------------------------------------------------------
# Path catalogo KBA
# ---------------------------------------------------------------------------
CATALOG_DIR: Path = PROJECT_ROOT / "lib" / "data" / "kba_catalog"
RECORDS_DIR: Path = CATALOG_DIR / "records"
INDEX_FILE: Path = CATALOG_DIR / "index.yaml"

# ---------------------------------------------------------------------------
# Path documenti convertiti
# ---------------------------------------------------------------------------
DOCUMENTS_DIR: Path = PROJECT_ROOT / "lib" / "documents"

# ---------------------------------------------------------------------------
# Inbox / Output
# ---------------------------------------------------------------------------
INBOX_DIR: Path = PROJECT_ROOT / "Team" / "Inbox"
OUTPUT_DIR: Path = PROJECT_ROOT / "lib" / "deliverables"

# ---------------------------------------------------------------------------
# Log
# ---------------------------------------------------------------------------
LOG_FILE: Path = PROJECT_ROOT / "lib" / "data" / "kba_merger.log"

# ---------------------------------------------------------------------------
# Siti noti — ordine di priorita' nel match case-insensitive
# ---------------------------------------------------------------------------
KNOWN_SITES: list[str] = ["Montecchio", "Lonigo", "Termoli"]

# ---------------------------------------------------------------------------
# Colonne output Excel (ordine A→O)
# ---------------------------------------------------------------------------
OUTPUT_HEADERS: list[str] = [
    "KBA Number",
    "Published",
    "Category",
    "Disposition Status",
    "Title",
    "Site",
    "Node Name / Node Assignment",
    "User Notes",
    "Risk Score",
    "Risk Level",
    "Problem Type",
    "Workaround",
    "Fix Available",
    "Emerson Category",
    "FIS Notes",
    "Suggested Notes",
    "Stefano's Notes",
]

# Larghezze colonne in caratteri (A→Q, senza colonne AI)
COLUMN_WIDTHS: list[int] = [14, 12, 12, 14, 50, 12, 14, 40, 10, 14, 18, 18, 18, 14, 40, 40, 40]

# Colore sfondo colonna Suggested Notes (giallo chiaro)
SUGGESTED_NOTE_BG_COLOR: str = "FFF2CC"

# ---------------------------------------------------------------------------
# Colori header
# ---------------------------------------------------------------------------
HEADER_BG_COLOR: str = "1F4E79"
HEADER_FG_COLOR: str = "FFFFFF"

# ---------------------------------------------------------------------------
# Colori Risk Level (colonna J) — (bg_hex, fg_hex)
# ---------------------------------------------------------------------------
RISK_LEVEL_COLORS: dict[str, tuple[str, str]] = {
    "critical": ("C00000", "FFFFFF"),
    "warning": ("FF0000", "FFFFFF"),
    "advisory": ("FF9900", "000000"),
    "informational": ("FFFF00", "000000"),
    "negligible": ("92D050", "000000"),
}

# ---------------------------------------------------------------------------
# Colori stato gap check (bg_hex)
# ---------------------------------------------------------------------------
GAP_STATUS_COLORS: dict[str, str] = {
    "da_convertire": "FF9900",
    "da_analizzare": "FFFF00",
    "da_rianalizzare": "FFC000",
    "ok": "92D050",
}
