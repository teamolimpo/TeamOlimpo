from __future__ import annotations

from pathlib import Path

from tools.common.paths import project_root

PROJECT_ROOT: Path = project_root()

HANDOFF_DIR: Path = PROJECT_ROOT / "Library" / "Handoff"
SCRATCHPAD_PATH: Path = PROJECT_ROOT / "lib" / "Fucina" / "Hermes" / "Scratchpad.md"

MEMBRI: frozenset[str] = frozenset(
    {
        "hermes",
        "proteo",
        "atena",
        "efesto",
        "clio",
        "dike",
        "metis",
        "calliope",
        "pythagoras",
        "hermione",
        "euterpe",
        "demetra",
        "eunomia",
    }
)

SKIP_DIRS: frozenset[str] = frozenset(
    {
        "templates",
        "kba_batch",
        "kba_batch2",
        "tucson",
        "Legacy",
        "scripts",
    }
)

STATI_HANDOFF: frozenset[str] = frozenset(
    {
        "da-processare",
        "in-corso",
        "bloccato",
        "completato",
    }
)

PRIORITA_VALIDE: frozenset[str] = frozenset({"alta", "media", "bassa"})

TIPI_HANDOFF: frozenset[str] = frozenset(
    {
        "profilo",
        "specifica",
        "feedback",
        "bug",
        "report",
        "test",
        "nota",
    }
)

STATI_TASK: frozenset[str] = frozenset(
    {
        "in_progress",
        "blocked",
        "awaiting_review",
        "completed",
    }
)

REGISTRO_PATH: Path = HANDOFF_DIR / "Registro.md"
