"""Costanti di configurazione per kba_resolver."""

from pathlib import Path

from tools.common.paths import project_root

PROJECT_ROOT: Path = project_root()

RECORDS_DIR: Path = PROJECT_ROOT / "lib" / "data" / "kba_catalog" / "records"
DOCUMENTS_DIR: Path = PROJECT_ROOT / "lib" / "documents"
LOG_FILE: Path = PROJECT_ROOT / "lib" / "data" / "kba_resolver.log"
