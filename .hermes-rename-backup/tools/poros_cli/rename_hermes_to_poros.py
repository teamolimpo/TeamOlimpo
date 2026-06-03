#!/usr/bin/env python3
"""Esegue il rename massivo di "Hermes" in "Poros" su tutto il codebase.

Fasi:
  1. Rinomina file/directory (FASE 1)
  2. Sostituzioni testuali nei file rinominati (FASE 2)
  3. Sostituzioni testuali in file non rinominati (FASE 3)
  4. Backup pre-modifica con rollback capability

Modalità:
  --dry-run    Mostra cosa farebbe senza eseguire
  --rollback   Ripristina tutto dai backup in .hermes-rename-backup/
  (default)    Esecuzione reale
"""

from __future__ import annotations

import argparse
import logging
import re
import shutil
import sys
from datetime import datetime
from pathlib import Path
from typing import Any

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
BACKUP_ROOT = PROJECT_ROOT / ".hermes-rename-backup"

LOG_FILE = PROJECT_ROOT / ".hermes-rename-backup" / "rename.log"

# FASE 1: file/directory da rinominare (src → dst relativi a PROJECT_ROOT)
RENAME_MAP: list[tuple[str, str]] = [
    (".opencode/agents/hermes.md",          ".opencode/agents/poros.md"),
    ("Team/Members/hermes.md",              "Team/Members/poros.md"),
    (".claude/agents/hermes.md",            ".claude/agents/poros.md"),
    ("tools/hermes_cli",                    "tools/poros_cli"),          # merge (target already exists)
    ("Team/SOPs/hermes-orchestration-methodology.md",
     "Team/SOPs/poros-orchestration-methodology.md"),
    ("Library/System/Hermes",               "Library/System/Poros"),
]

# FASE 3: file specifici non rinominati da processare
# (path relativi a PROJECT_ROOT)
PHASE3_FILES_REL: list[str] = [
    # Config
    "CLAUDE.md",
    "opencode.json",
    ".mcp.json",
    # Team docs
    "Team/Members/Registro.md",
    "Team/SOPs/handoff-guide.md",
    "Team/SOPs/agent-design-methodology.md",
    "Team/SOPs/agent-review-flow.md",
    "Team/SOPs/log-compression.md",
    "Team/SOPs/archive/agent-creation-flow.md",
    "Team/SOPs/archive/agent-modification-flow.md",
    ".opencode/agents/atena.md",
    # Codice Python
    "tools/synapsis/models.py",
    "tools/synapsis/store.py",
    "tools/taskmanager/models.py",
    "tools/taskmanager/server.py",
    "tools/session_memory/store.py",
    "tools/session_memory/server.py",
    "tools/session_memory/models.py",
    "tools/log_compressor/main.py",
    "tools/kba_reporter/writer.py",
    "tools/kba/reporter/writer.py",
    "tools/email_processor/cli.py",
    "tools/email_processor/discovery.py",
    # Tests
    "tests/test_session_memory.py",
    "tests/test_log_compression.py",
]

# FASE 3 glob patterns: directory da scansionare ricorsivamente per file .md
PHASE3_GLOB_DIRS: list[str] = [
    "Team/Prompts",
    "Team/Meta",
]

# Coppie di sostituzione testuale (old → new)
REPLACE_PAIRS: list[tuple[str, str]] = [
    ("Hermes", "Poros"),
    ("hermes", "Poros"),  # ATTENZIONE: sostituiamo 'hermes' con 'Poros' solo
    # quando la parola esatta è 'hermes' (lowercase).
    # Per non rompere parole come 'Hermione', usiamo
    # word-boundary regex.
]

# Directory/pattern da escludere SEMPRE (case-insensitive match sul path)
EXCLUDE_DIRS: list[str] = [
    ".git",
    ".venv",
    "Legacy",
    ".hermes-rename-backup",
    "__pycache__",
    "node_modules",
    ".eggs",
    "*.pyc",
    "*.pyo",
]

EXCLUDE_PATH_SUBSTRINGS: list[str] = [
    "Team/Fucina/repos",
    ".git/",
]

# Path che contengono riferimenti puri a OpenCode e non vanno toccati
# (ad esempio il nome del tool 'hermes' in contesti di routing)
# Aggiungeremo exclusioni contestuali nelle sostituzioni regex.

# File che non esistono (da ignorare silenziosamente) — non sono errori
# (ad esempio alcuni test potrebbero non esistere ancora)
ALLOW_MISSING: set[str] = set(PHASE3_FILES_REL)

# Mappa speciale per opencode.json e .mcp.json: sostituzioni custom
# (path → [(old, new)])
CUSTOM_REPLACEMENTS: dict[str, list[tuple[str, str]]] = {
    "opencode.json": [
        ('"default_agent": "hermes"', '"default_agent": "poros"'),
        (
            '"SYNAPSIS_DB_PATH": "lib/System/Hermes/synapsis.db"',
            '"SYNAPSIS_DB_PATH": "Library/System/Poros/synapsis.db"',
        ),
    ],
    ".mcp.json": [
        (
            '"SESSION_DB_PATH": "lib/System/Hermes/session.db"',
            '"SESSION_DB_PATH": "Library/System/Poros/session.db"',
        ),
    ],
}

# ---------------------------------------------------------------------------
# Globals
# ---------------------------------------------------------------------------

logger: logging.Logger = logging.getLogger("rename_hermes_to_poros")
_stats: dict[str, int] = {
    "files_renamed": 0,
    "dirs_renamed": 0,
    "files_modified_text": 0,
    "total_replacements": 0,
    "errors": 0,
    "backups_created": 0,
    "whitepaper_files_skipped": 0,
}


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _ensure_backup_dir() -> Path:
    """Ensure the backup root directory exists."""
    BACKUP_ROOT.mkdir(parents=True, exist_ok=True)
    return BACKUP_ROOT


def _backup_path(file_path: Path) -> Path:
    """Return the backup destination path for a given file."""
    rel = file_path.relative_to(PROJECT_ROOT)
    return BACKUP_ROOT / rel


def _should_exclude(path: Path) -> bool:
    """Check if a path should be excluded from processing."""
    rel_str = str(path.relative_to(PROJECT_ROOT)) if path.is_relative_to(PROJECT_ROOT) else str(path)
    lower = rel_str.lower()

    for excl in EXCLUDE_DIRS:
        if excl.startswith("*"):
            if lower.endswith(excl[1:]):
                return True
        elif f"/{excl}/" in lower or lower == excl or lower.startswith(f"{excl}/"):
            return True

    for excl in EXCLUDE_PATH_SUBSTRINGS:
        if excl in rel_str:
            return True

    return False


def _is_whitepaper(path: Path) -> bool:
    """Check if a path is a whitepaper markdown file."""
    rel = str(path.relative_to(PROJECT_ROOT))
    return "paper/whitepaper" in rel and rel.endswith(".md")


def _backup_file(file_path: Path, dry_run: bool) -> bool:
    """Create a backup of a file before modification.

    Returns True if backup was created (or would be created in dry-run).
    """
    if not file_path.exists() or not file_path.is_file():
        return False

    dst = _backup_path(file_path)
    if not dry_run:
        dst.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(str(file_path), str(dst))
        _stats["backups_created"] += 1
        logger.info("Backup: %s → %s", file_path, dst)
    else:
        _stats["backups_created"] += 1
        logger.info("[DRY-RUN] Backup: %s → %s", file_path, dst)

    return True


def _backup_directory(dir_path: Path, dry_run: bool) -> bool:
    """Recursively backup all files in a directory tree.

    Returns True if any backup was created.
    """
    if not dir_path.exists() or not dir_path.is_dir():
        return False

    count = 0
    for f in dir_path.rglob("*"):
        if f.is_file() and not _should_exclude(f):
            dst = _backup_path(f)
            if not dry_run:
                dst.parent.mkdir(parents=True, exist_ok=True)
                shutil.copy2(str(f), str(dst))
                count += 1
            else:
                count += 1

    if count > 0:
        _stats["backups_created"] += count
        logger.info(
            "[%s] Backup directory: %s (%d files)", "[DRY-RUN]" if dry_run else "", dir_path, count
        )
    return count > 0


# ---------------------------------------------------------------------------
# FASE 1: Rinomina file/directory
# ---------------------------------------------------------------------------


def _rename_path(src_rel: str, dst_rel: str, dry_run: bool) -> bool:
    """Rename a single file or directory from src_rel to dst_rel.

    Both paths are relative to PROJECT_ROOT.
    Returns True on success.
    """
    src = PROJECT_ROOT / src_rel
    dst = PROJECT_ROOT / dst_rel

    if not src.exists():
        logger.warning("FASE 1: source non esiste — SKIP: %s", src_rel)
        return False

    if dst.exists():
        logger.warning("FASE 1: destinazione già esistente — SKIP: %s → %s", src_rel, dst_rel)
        return False

    if dry_run:
        if src.is_dir():
            logger.info("[DRY-RUN] FASE 1: rinomina directory %s → %s", src_rel, dst_rel)
        else:
            logger.info("[DRY-RUN] FASE 1: rinomina file %s → %s", src_rel, dst_rel)
        if src.is_dir():
            _stats["dirs_renamed"] += 1
        else:
            _stats["files_renamed"] += 1
        return True

    try:
        src.rename(dst)
        if src.is_dir():
            _stats["dirs_renamed"] += 1
            logger.info("FASE 1: directory rinominata %s → %s", src_rel, dst_rel)
        else:
            _stats["files_renamed"] += 1
            logger.info("FASE 1: file rinominato %s → %s", src_rel, dst_rel)
        return True
    except OSError as exc:
        _stats["errors"] += 1
        logger.error("FASE 1: errore rename %s → %s: %s", src_rel, dst_rel, exc)
        return False


# ---------------------------------------------------------------------------
# FASE 2+3: Sostituzioni testuali
# ---------------------------------------------------------------------------


def _build_regex_patterns() -> list[tuple[re.Pattern, str]]:
    """Build regex patterns for Hermes → Poros replacements.

    Returns list of (compiled_pattern, replacement_string).
    Uses word-boundary matching to avoid partial matches.
    """
    patterns: list[tuple[re.Pattern, str]] = []

    # "Hermes" → "Poros" (word boundary, capitalized)
    patterns.append((re.compile(r"\bHermes\b"), "Poros"))

    # "hermes" → "poros" (word boundary, lowercase) — solo se non è parte di
    # una parola più lunga come "Hermione"
    patterns.append((re.compile(r"\bhermes\b"), "poros"))

    # "HERMES" → "POROS" (word boundary, uppercase)
    patterns.append((re.compile(r"\bHERMES\b"), "POROS"))

    return patterns


def _apply_custom_replacements(
    content: str, file_rel: str, dry_run: bool
) -> tuple[str, int]:
    """Apply custom per-file replacements.

    Returns (modified_content, replacement_count).
    """
    if file_rel not in CUSTOM_REPLACEMENTS:
        return content, 0

    count = 0
    for old, new in CUSTOM_REPLACEMENTS[file_rel]:
        if old in content:
            content = content.replace(old, new)
            count += 1
            logger.info(
                "[%s] Custom replace in %s: %s → %s",
                "[DRY-RUN]" if dry_run else "",
                file_rel,
                old,
                new,
            )

    return content, count


def _apply_text_replacements(
    content: str, file_rel: str, dry_run: bool
) -> tuple[str, int]:
    """Apply all text replacements to content.

    Returns (modified_content, total_replacements).
    """
    patterns = _build_regex_patterns()
    total_count = 0

    for pattern, replacement in patterns:
        new_content, count = pattern.subn(replacement, content)
        if count > 0:
            logger.debug(
                "[%s] Replace in %s: %d match(es) for %s",
                "[DRY-RUN]" if dry_run else "",
                file_rel,
                count,
                pattern.pattern,
            )
            content = new_content
            total_count += count

    return content, total_count


def _process_file_text(
    file_path: Path, dry_run: bool, phase_label: str = "FASE"
) -> bool:
    """Apply text replacements to a single file.

    Steps:
      1. Backup original
      2. Apply custom replacements (if configured for this file)
      3. Apply regex replacements (Hermes/hermes → Poros/poros)
      4. Write modified content

    Returns True if any replacement was applied.
    """
    if not file_path.exists():
        logger.debug("%s: file non trovato — SKIP: %s", phase_label, file_path)
        return False

    if _should_exclude(file_path):
        logger.debug("%s: file escluso — SKIP: %s", phase_label, file_path)
        return False

    rel = str(file_path.relative_to(PROJECT_ROOT))

    # Read original content
    try:
        original = file_path.read_text(encoding="utf-8")
    except (OSError, UnicodeDecodeError) as exc:
        _stats["errors"] += 1
        logger.error("%s: impossibile leggere %s: %s", phase_label, rel, exc)
        return False

    # Apply custom replacements first
    content, custom_count = _apply_custom_replacements(original, rel, dry_run)

    # Apply regex replacements
    content, regex_count = _apply_text_replacements(content, rel, dry_run)

    total_replacements = custom_count + regex_count

    if total_replacements == 0:
        logger.debug("%s: nessuna sostituzione in %s", phase_label, rel)
        return False

    # Backup
    _backup_file(file_path, dry_run)

    _stats["files_modified_text"] += 1
    _stats["total_replacements"] += total_replacements

    # Write modified content (skip in dry-run)
    if not dry_run:
        try:
            file_path.write_text(content, encoding="utf-8")
            logger.info(
                "%s: %s — %d sostituzioni applicate",
                phase_label,
                rel,
                total_replacements,
            )
        except OSError as exc:
            _stats["errors"] += 1
            logger.error("%s: errore scrittura %s: %s", phase_label, rel, exc)
            return False
    else:
        logger.info(
            "%s: [DRY-RUN] %s — %d sostituzioni da applicare",
            phase_label,
            rel,
            total_replacements,
        )

    return True


def _process_directory_tree(dir_path: Path, dry_run: bool) -> int:
    """Process all .md and .py files in a directory tree recursively.

    Returns count of modified files.
    """
    count = 0
    # Solo file .md, .py, .json
    extensions = {".md", ".py", ".json"}

    for f in sorted(dir_path.rglob("*")):
        if not f.is_file():
            continue
        if f.suffix not in extensions:
            continue
        if _should_exclude(f):
            continue
        if _process_file_text(f, dry_run, "FASE 3"):
            count += 1

    return count


# ---------------------------------------------------------------------------
# FASE 4: Whitepaper — gestione speciale
# ---------------------------------------------------------------------------


def _process_whitepaper(file_path: Path, dry_run: bool) -> bool:
    """Process a whitepaper file with special care.

    In whitepapers, "Hermes" may appear as:
    - Orchestrator name (should be replaced)
    - Mythological reference (should NOT be replaced)

    We use context to determine which instances to replace.
    In practice, all references in the Team Olimpo whitepapers
    are to the orchestrator and should be replaced.

    Returns True if any replacement was applied.
    """
    if not file_path.exists():
        return False

    rel = str(file_path.relative_to(PROJECT_ROOT))
    logger.info(
        "[%s] FASE 4: elaborazione whitepaper %s",
        "[DRY-RUN]" if dry_run else "",
        rel,
    )

    return _process_file_text(file_path, dry_run, "FASE 4")


# ---------------------------------------------------------------------------
# FASE 2: Process renamed files
# ---------------------------------------------------------------------------


def _process_renamed_file(src_rel: str, dst_rel: str, dry_run: bool) -> None:
    """Apply text replacements to a file that was renamed.

    Handles both single files and directories.
    """
    src = PROJECT_ROOT / src_rel
    dst = PROJECT_ROOT / dst_rel

    if not dst.exists() and not src.exists():
        logger.debug("FASE 2: nessun target per %s — SKIP", dst_rel)
        return

    target = dst if dst.exists() else src

    if target.is_dir():
        count = _process_directory_tree(target, dry_run)
        if count > 0:
            logger.info(
                "[%s] FASE 2: directory processata %s — %d file modificati",
                "[DRY-RUN]" if dry_run else "",
                dst_rel,
                count,
            )
    elif target.is_file():
        _process_file_text(target, dry_run, "FASE 2")


# ---------------------------------------------------------------------------
# Rollback
# ---------------------------------------------------------------------------


def _rollback(dry_run: bool) -> int:
    """Rollback all changes by restoring from .hermes-rename-backup/.

    Returns count of files restored.
    """
    if not BACKUP_ROOT.exists():
        logger.error("Rollback: directory backup non trovata: %s", BACKUP_ROOT)
        return 0

    restored = 0

    # Walk through backup directory, restore each file to original location
    for backup_file in sorted(BACKUP_ROOT.rglob("*")):
        if not backup_file.is_file() or _should_exclude(backup_file):
            continue

        # Calculate original location
        try:
            rel = backup_file.relative_to(BACKUP_ROOT)
        except ValueError:
            continue

        original = PROJECT_ROOT / rel

        if dry_run:
            logger.info("[DRY-RUN] Rollback: ripristino %s → %s", backup_file, original)
            restored += 1
        else:
            try:
                original.parent.mkdir(parents=True, exist_ok=True)
                shutil.copy2(str(backup_file), str(original))
                restored += 1
                logger.info("Rollback: ripristinato %s → %s", backup_file, original)
            except OSError as exc:
                _stats["errors"] += 1
                logger.error("Rollback: errore ripristino %s: %s", backup_file, exc)

    return restored


# ---------------------------------------------------------------------------
# Report
# ---------------------------------------------------------------------------


def _print_report() -> None:
    """Print final summary report."""
    print()
    print("=" * 60)
    print("  REPORT — Hermes → Poros Rename")
    print("=" * 60)
    print(f"  File rinominati:          {_stats['files_renamed']}")
    print(f"  Directory rinominati:     {_stats['dirs_renamed']}")
    print(f"  File con testo modificato: {_stats['files_modified_text']}")
    print(f"  Sostituzioni totali:       {_stats['total_replacements']}")
    print(f"  Backup creati:             {_stats['backups_created']}")
    print(f"  Errori:                    {_stats['errors']}")
    print(f"  Whitepaper saltati:        {_stats['whitepaper_files_skipped']}")
    print("=" * 60)
    if _stats["errors"] > 0:
        print("  ⚠️  Verificare il log per i dettagli degli errori.")
    print("=" * 60)
    print()


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------


def main() -> None:  # noqa: C901, PLR0912, PLR0915
    """Main entry point."""
    parser = argparse.ArgumentParser(
        description='Esegue il rename massivo "Hermes" → "Poros" su tutto il codebase.',
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Mostra cosa farebbe senza eseguire modifiche.",
    )
    parser.add_argument(
        "--rollback",
        action="store_true",
        help="Ripristina tutto dai backup in .hermes-rename-backup/.",
    )
    parser.add_argument(
        "--whitepaper",
        action="store_true",
        help="Includi anche i whitepaper (paper/whitepaper*.md). Default: esclusi.",
    )
    parser.add_argument(
        "--verbose",
        "-v",
        action="store_true",
        help="Log più dettagliato (debug).",
    )
    parser.add_argument(
        "--phase",
        choices=["1", "2", "3", "4", "all"],
        default="all",
        help="Esegue solo una fase specifica. Default: all.",
    )

    args = parser.parse_args()
    dry_run = args.dry_run
    do_rollback = args.rollback
    do_whitepaper = args.whitepaper
    phase = args.phase

    # ------------------------------------------------------------------
    # Setup logging
    # ------------------------------------------------------------------
    log_level = logging.DEBUG if args.verbose else logging.INFO
    logger.setLevel(log_level)

    # Console handler
    ch = logging.StreamHandler(sys.stdout)
    ch.setLevel(log_level)
    ch.setFormatter(logging.Formatter("%(asctime)s [%(levelname)s] %(message)s"))
    logger.addHandler(ch)

    # File handler (if not rollback, since rollback happens before log dir creation)
    if not do_rollback:
        _ensure_backup_dir()
        fh = logging.FileHandler(str(LOG_FILE), mode="w", encoding="utf-8")
        fh.setLevel(logging.DEBUG)
        fh.setFormatter(logging.Formatter("%(asctime)s [%(levelname)s] %(message)s"))
        logger.addHandler(fh)

    logger.info("=== Hermes → Poros Rename Tool ===")
    logger.info("Project root: %s", PROJECT_ROOT)
    logger.info("Backup root:  %s", BACKUP_ROOT)
    logger.info("Dry-run:      %s", dry_run)
    logger.info("Rollback:     %s", do_rollback)
    logger.info("Whitepaper:   %s", do_whitepaper)
    logger.info("Phase:        %s", phase)
    logger.info("")

    # ==================================================================
    # ROLLBACK MODE
    # ==================================================================
    if do_rollback:
        logger.info("=== Rollback Mode ===")
        restored = _rollback(dry_run)
        logger.info("Rollback completato: %d file ripristinati", restored)
        _print_report()
        return

    # ==================================================================
    # BACKUP PRE-MODIFICA
    # ==================================================================
    logger.info("=== Backup pre-modifica ===")

    # Backup Phase 3 specific files
    for rel_path in PHASE3_FILES_REL:
        fp = PROJECT_ROOT / rel_path
        if fp.exists() and fp.is_file():
            _backup_file(fp, dry_run)

    # Backup glob directories
    for glob_dir in PHASE3_GLOB_DIRS:
        d = PROJECT_ROOT / glob_dir
        if d.exists() and d.is_dir():
            _backup_directory(d, dry_run)

    # Backup Phase 1 rename targets (before rename)
    for src_rel, _dst_rel in RENAME_MAP:
        src = PROJECT_ROOT / src_rel
        if src.exists():
            if src.is_dir():
                _backup_directory(src, dry_run)
            else:
                _backup_file(src, dry_run)

    # Backup whitepapers (before processing)
    for wp_glob in ["paper/whitepaper.md", "paper/whitepaper-it.md"]:
        wp = PROJECT_ROOT / wp_glob
        if wp.exists():
            _backup_file(wp, dry_run)

    logger.info("Backup completato: %d backup creati\n", _stats["backups_created"])

    # ==================================================================
    # FASE 1: Rinomina file/directory
    # ==================================================================
    if phase in ("1", "all"):
        logger.info("=== FASE 1: Rinomina file/directory ===")

        # Handle tools/hermes_cli specially (target already exists as poros_cli)
        hermes_cli = PROJECT_ROOT / "tools/hermes_cli"
        poros_cli = PROJECT_ROOT / "tools/poros_cli"
        if hermes_cli.exists() and hermes_cli.is_dir():
            if hermes_cli.resolve() == poros_cli.resolve():
                logger.info(
                    "FASE 1: tools/hermes_cli e tools/poros_cli sono lo stesso path — SKIP"
                )
            else:
                merged = _merge_hermes_cli_into_poros_cli(hermes_cli, poros_cli, dry_run)
                if merged:
                    _stats["dirs_renamed"] += 1
                    _stats["files_renamed"] += 1  # approx

        # Process all other rename entries
        for src_rel, dst_rel in RENAME_MAP:
            # Skip hermes_cli entry (already handled above)
            if src_rel == "tools/hermes_cli":
                continue
            _rename_path(src_rel, dst_rel, dry_run)

        logger.info("FASE 1 completata\n")

    # ==================================================================
    # FASE 2: Sostituzioni testuali nei file rinominati
    # ==================================================================
    if phase in ("2", "all"):
        logger.info("=== FASE 2: Sostituzioni nei file rinominati ===")

        for src_rel, dst_rel in RENAME_MAP:
            if src_rel == "tools/hermes_cli":
                # Use the already-renamed directory
                _process_renamed_file(src_rel, "tools/poros_cli", dry_run)
            else:
                _process_renamed_file(src_rel, dst_rel, dry_run)

        logger.info("FASE 2 completata\n")

    # ==================================================================
    # FASE 3: Sostituzioni in file non rinominati
    # ==================================================================
    if phase in ("3", "all"):
        logger.info("=== FASE 3: Sostituzioni in file non rinominati ===")

        # Process specific files
        for rel_path in PHASE3_FILES_REL:
            fp = PROJECT_ROOT / rel_path
            if fp.exists():
                _process_file_text(fp, dry_run, "FASE 3")
            else:
                logger.debug("FASE 3: file non trovato — SKIP (allow missing): %s", rel_path)

        # Process glob directories
        for glob_dir in PHASE3_GLOB_DIRS:
            d = PROJECT_ROOT / glob_dir
            if d.exists() and d.is_dir():
                logger.info("FASE 3: elaborazione directory %s ...", glob_dir)
                count = _process_directory_tree(d, dry_run)
                logger.info("FASE 3: directory %s — %d file modificati", glob_dir, count)

        logger.info("FASE 3 completata\n")

    # ==================================================================
    # FASE 4: Casi speciali (whitepaper)
    # ==================================================================
    if phase in ("4", "all"):
        logger.info("=== FASE 4: Casi speciali ===")

        whitepaper_files = [
            PROJECT_ROOT / "paper/whitepaper.md",
            PROJECT_ROOT / "paper/whitepaper-it.md",
        ]

        for wp_file in whitepaper_files:
            if wp_file.exists():
                if do_whitepaper:
                    _process_whitepaper(wp_file, dry_run)
                else:
                    _stats["whitepaper_files_skipped"] += 1
                    logger.info(
                        "FASE 4: whitepaper SKIP (usa --whitepaper per includere): %s",
                        wp_file.relative_to(PROJECT_ROOT),
                    )
            else:
                logger.debug("FASE 4: whitepaper non trovato: %s", wp_file)

        logger.info("FASE 4 completata\n")

    # ==================================================================
    # Report finale
    # ==================================================================
    _print_report()

    # Final log message
    if not dry_run:
        logger.info("Operazione completata. Log salvato in: %s", LOG_FILE)
        logger.info(
            "Per rollback: esegui '%s --rollback'",
            sys.argv[0],
        )


# ---------------------------------------------------------------------------
# Special handling: hermes_cli → poros_cli merge
# ---------------------------------------------------------------------------


def _merge_hermes_cli_into_poros_cli(
    src_dir: Path, dst_dir: Path, dry_run: bool
) -> bool:
    """Merge tools/hermes_cli contents into existing tools/poros_cli.

    Since tools/poros_cli already exists (contains this script),
    we move hermes_cli contents into a subdirectory or merge them.

    Returns True if operation was successful.
    """
    if not src_dir.is_dir():
        return False

    # Strategy: move all from hermes_cli into poros_cli, skip conflicts
    if dry_run:
        logger.info("[DRY-RUN] Merge: %s → %s", src_dir, dst_dir)
        for f in sorted(src_dir.rglob("*")):
            if f.is_file() and not _should_exclude(f):
                rel = f.relative_to(src_dir)
                logger.info("  [DRY-RUN]   Move: %s → %s", rel, dst_dir / rel)
        return True

    try:
        for f in src_dir.rglob("*"):
            if f.is_file() and not _should_exclude(f):
                rel = f.relative_to(src_dir)
                dst = dst_dir / rel
                dst.parent.mkdir(parents=True, exist_ok=True)
                if dst.exists():
                    logger.warning("  Conflict: %s già esiste — SKIP", dst)
                    continue
                shutil.move(str(f), str(dst))
                logger.info("  Move: %s → %s", rel, dst)

        # Remove empty source directory
        remaining = list(src_dir.rglob("*"))
        if not remaining or all(
            p.name == "__pycache__" or (p.is_dir() and not list(p.iterdir()))
            for p in remaining
        ):
            shutil.rmtree(str(src_dir), ignore_errors=True)
            logger.info("  Directory sorgente rimossa: %s", src_dir)
        else:
            logger.warning("File residui in %s — rimozione manuale necessaria", src_dir)

        return True
    except OSError as exc:
        _stats["errors"] += 1
        logger.error("Merge error: %s", exc)
        return False


if __name__ == "__main__":
    main()