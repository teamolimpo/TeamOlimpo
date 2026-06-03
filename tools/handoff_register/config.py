"""
Configurazione centralizzata per il tool handoff_register.

Tutti i path sono derivati dalla root del progetto PKM.
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
# Path di lavoro
# ---------------------------------------------------------------------------

# Cartella handoff
HANDOFF_DIR: Path = PROJECT_ROOT / "lib" / "Fucina" / "Handoff"

# Cartelle/sottocartelle da ignorare nello scan ricorsivo
SKIP_DIRS: frozenset[str] = frozenset(
    {"templates", "kba_batch", "kba_batch2", "tucson", "Legacy", "scripts"}
)

# File di registro autogenerato
REGISTRO_PATH: Path = HANDOFF_DIR / "Registro.md"

# File di log del tool
LOG_FILE: Path = PROJECT_ROOT / "lib" / "data" / "handoff_register.log"

# ---------------------------------------------------------------------------
# Valori ammessi nei frontmatter
# ---------------------------------------------------------------------------

STATI_ATTIVI: frozenset[str] = frozenset({"da-processare", "in-corso", "bloccato"})
STATI_VALIDI: frozenset[str] = frozenset({"da-processare", "in-corso", "bloccato", "completato"})

PRIORITA_VALIDE: frozenset[str] = frozenset({"alta", "media", "bassa"})

TIPI_VALIDI: frozenset[str] = frozenset(
    {"profilo", "specifica", "feedback", "bug", "report", "test", "nota"}
)
