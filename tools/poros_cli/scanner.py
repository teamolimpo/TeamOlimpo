from __future__ import annotations

from pathlib import Path
from typing import Any

import yaml
from loguru import logger

from tools.hermes_cli.config import HANDOFF_DIR, REGISTRO_PATH, SCRATCHPAD_PATH, SKIP_DIRS
from tools.hermes_cli.models import Decision, Scratchpad, Task


def read_frontmatter(path: Path) -> tuple[dict[str, Any], list[str]]:
    """Parse YAML frontmatter from a markdown file.

    Returns a tuple of (parsed dict, warnings list). Returns an empty dict
    and a warning if the file has no frontmatter or YAML parsing fails.
    """
    warnings: list[str] = []
    try:
        text = path.read_text(encoding="utf-8")
    except OSError as exc:
        warnings.append(f"impossibile leggere il file: {exc}")
        return {}, warnings

    if not text.startswith("---"):
        warnings.append("frontmatter YAML assente (il file non inizia con '---')")
        return {}, warnings

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


def read_scratchpad(path: Path = SCRATCHPAD_PATH) -> Scratchpad:
    """Read and parse a scratchpad file into a Scratchpad model.

    Handles file-not-found, YAML parse errors, and schema warnings.
    Returns a populated Scratchpad instance.
    """
    sp = Scratchpad(path=path)

    if not path.exists():
        sp.errors.append({"type": "file_not_found", "description": f"File non trovato: {path}"})
        return sp

    try:
        text = path.read_text(encoding="utf-8")
    except OSError as exc:
        sp.errors.append({"type": "read_error", "description": str(exc)})
        return sp

    if not text.startswith("---"):
        sp.warnings.append(
            {
                "type": "no_frontmatter",
                "description": "File non inizia con '---' — frontmatter YAML assente",
            }
        )
        return sp

    end_marker = text.find("\n---", 3)
    if end_marker == -1:
        sp.errors.append(
            {
                "type": "yaml_unclosed",
                "description": "Frontmatter YAML non chiuso (marker '---' di chiusura assente)",
            }
        )
        return sp

    yaml_block = text[3:end_marker].strip()

    try:
        parsed = yaml.safe_load(yaml_block)
    except yaml.YAMLError as exc:
        sp.parsed = False
        mark = getattr(exc, "problem_mark", None)
        if mark is not None:
            sp.yaml_error_line = mark.line + 1
        sp.yaml_error = str(exc)
        problem = getattr(exc, "problem", str(exc))
        sp.errors.append(
            {
                "type": "yaml_parse",
                "line": sp.yaml_error_line or 0,
                "description": f"YAML malformato (riga ~{sp.yaml_error_line}): {problem}",
            }
        )
        logger.debug(f"YAML parse error in scratchpad: {exc}")
        return sp

    if not isinstance(parsed, dict):
        sp.errors.append(
            {"type": "yaml_not_dict", "description": "Il frontmatter non è un mapping YAML valido"}
        )
        return sp

    sp.parsed = True
    sp.raw = parsed

    raw_tasks = parsed.get("active_tasks", [])
    if not isinstance(raw_tasks, list):
        sp.warnings.append(
            {
                "type": "wrong_type",
                "field": "active_tasks",
                "description": "active_tasks non è una lista",
            }
        )
    else:
        for i, t in enumerate(raw_tasks):
            if not isinstance(t, dict):
                sp.warnings.append(
                    {
                        "type": "wrong_type",
                        "field": f"active_tasks[{i}]",
                        "description": f"Elemento {i} non è un oggetto",
                    }
                )
                continue
            task = Task(
                id=str(t.get("id", "")),
                title=t.get("title"),
                description=t.get("description"),
                delegated_to=t.get("delegated_to"),
                responsible=t.get("responsible"),
                status=t.get("status"),
                started_at=str(t.get("started_at", "")) if t.get("started_at") else None,
                subtasks=t.get("subtasks"),
                notes=t.get("notes"),
            )
            sp.tasks.append(task)

    raw_decisions = parsed.get("decisions", [])
    if not isinstance(raw_decisions, list):
        sp.warnings.append(
            {"type": "wrong_type", "field": "decisions", "description": "decisions non è una lista"}
        )
    else:
        for i, d in enumerate(raw_decisions):
            if not isinstance(d, dict):
                sp.warnings.append(
                    {
                        "type": "wrong_type",
                        "field": f"decisions[{i}]",
                        "description": f"Elemento {i} non è un oggetto",
                    }
                )
                continue
            decision = Decision(
                id=str(d.get("id", "")),
                date=str(d.get("date", "")) if d.get("date") else None,
                description=d.get("description"),
                topic=d.get("topic"),
                decision=d.get("decision"),
                rationale=d.get("rationale"),
            )
            sp.decisions.append(decision)

    logger.debug(
        f"Scratchpad letto: {len(sp.tasks)} task, {len(sp.decisions)} decisioni, {len(sp.errors)} errori, {len(sp.warnings)} warning"
    )
    return sp


def _is_scannable(path: Path) -> bool:
    """Check whether a file path should be included in a handoff scan."""
    if path.suffix.lower() != ".md":
        return False
    if path.resolve() == REGISTRO_PATH.resolve():
        return False
    for parent in path.parents:
        if parent.name in SKIP_DIRS:
            return False
    return True


def scan_handoff_files(handoff_dir: Path = HANDOFF_DIR) -> list[Path]:
    """Scan a directory for scannable handoff markdown files.

    Returns a sorted list of file paths that pass the _is_scannable check.
    """
    if not handoff_dir.exists():
        return []
    paths: list[Path] = []
    for path in sorted(handoff_dir.rglob("*.md")):
        if _is_scannable(path):
            paths.append(path)
    logger.debug(f"Scan handoff: {len(paths)} file trovati in {handoff_dir}")
    return paths


def read_handoff_body(path: Path) -> str:
    """Extract the markdown body from a handoff file, skipping its YAML frontmatter."""
    try:
        text = path.read_text(encoding="utf-8")
    except OSError:
        return ""
    if not text.startswith("---"):
        return text
    end_marker = text.find("\n---", 3)
    if end_marker == -1:
        return text
    return text[end_marker + 5 :]
