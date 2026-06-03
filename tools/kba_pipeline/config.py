"""
Configurazione centralizzata per il tool kba_pipeline.

Tutti i path sono relativi alla root del progetto PKM.
"""

from __future__ import annotations

from pathlib import Path

from tools.common.paths import project_root

# ---------------------------------------------------------------------------
# Root del progetto
# ---------------------------------------------------------------------------
PROJECT_ROOT: Path = project_root()

# ---------------------------------------------------------------------------
# Path dei documenti Markdown convertiti
# ---------------------------------------------------------------------------
DOCUMENTS_DIR: Path = PROJECT_ROOT / "lib" / "documents"

# ---------------------------------------------------------------------------
# Path dei record del catalogo KBA
# ---------------------------------------------------------------------------
RECORDS_DIR: Path = PROJECT_ROOT / "lib" / "data" / "kba_catalog" / "records"

# ---------------------------------------------------------------------------
# Path della cartella batch (file batch prodotti dallo step 2)
# ---------------------------------------------------------------------------
BATCH_DIR: Path = PROJECT_ROOT / "lib" / "Fucina" / "Handoff" / "kba_batch"

# ---------------------------------------------------------------------------
# Prompt per l'analisi AI dei documenti KBA
# ---------------------------------------------------------------------------
PROMPT_ANALYZE: Path = PROJECT_ROOT / "Team" / "Prompts" / "kba" / "analisi-rischio-kba.md"

# ---------------------------------------------------------------------------
# File di log del pipeline
# ---------------------------------------------------------------------------
LOG_FILE: Path = PROJECT_ROOT / "lib" / "data" / "kba_pipeline.log"
