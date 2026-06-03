"""
Configurazione centralizzata per il tool kba.indexer.

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
# Path del catalogo KBA (gestito da Dike)
# ---------------------------------------------------------------------------
CATALOG_DIR: Path = PROJECT_ROOT / "lib" / "data" / "kba_catalog"
RECORDS_DIR: Path = CATALOG_DIR / "records"
INDEX_FILE: Path = CATALOG_DIR / "index.yaml"

# ---------------------------------------------------------------------------
# Path dei file batch prodotti da tools.consulto
# ---------------------------------------------------------------------------
BATCH_DIR: Path = PROJECT_ROOT / "lib" / "Handoff" / "kba_batch"

# ---------------------------------------------------------------------------
# Path dei documenti Markdown convertiti da tools.pdf_converter
# ---------------------------------------------------------------------------
DOCUMENTS_DIR: Path = PROJECT_ROOT / "lib" / "documents"

# ---------------------------------------------------------------------------
# Cartella Inbox dell'utente (output finali)
# ---------------------------------------------------------------------------
INBOX_DIR: Path = PROJECT_ROOT / "lib" / "deliverables"

# ---------------------------------------------------------------------------
# File di log
# ---------------------------------------------------------------------------
LOG_FILE: Path = PROJECT_ROOT / "lib" / "data" / "kba_indexer.log"
