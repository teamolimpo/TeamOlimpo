from __future__ import annotations

import re
from pathlib import Path
from typing import Any

from loguru import logger

from tools.hermes_cli.config import (
    MEMBRI,
    PRIORITA_VALIDE,
    STATI_HANDOFF,
    STATI_TASK,
    TIPI_HANDOFF,
)
from tools.hermes_cli.models import HandoffValidation, Scratchpad
from tools.hermes_cli.scanner import read_frontmatter

HANDOFF_NAME_RE = re.compile(
    r"^\d{4}-\d{2}-\d{2}_[a-z]+-[a-z]+_(profilo|specifica|feedback|bug|report|test|nota)_[a-z0-9][a-z0-9-]*\.md$"
)


def validate_scratchpad(sp: Scratchpad) -> Scratchpad:
    """Validate a scratchpad structure and collect warnings for common issues.

    Checks active_tasks, members_status, decisions, and last_updated fields.
    Returns the scratchpad with warnings appended.
    """
    if not sp.parsed:
        return sp

    raw_tasks = sp.raw.get("active_tasks", [])
    if not isinstance(raw_tasks, list):
        sp.warnings.append(
            {
                "type": "wrong_type",
                "field": "active_tasks",
                "description": "active_tasks non è una lista",
            }
        )
    elif len(raw_tasks) == 0:
        sp.warnings.append(
            {"type": "empty_list", "field": "active_tasks", "description": "active_tasks è vuoto"}
        )

    for i, t in enumerate(sp.tasks):
        if not t.id:
            sp.warnings.append(
                {
                    "type": "missing_field",
                    "field": f"active_tasks[{i}].id",
                    "description": f"Task {i} senza id",
                }
            )
        if t.description and not t.title:
            sp.warnings.append(
                {
                    "type": "wrong_field",
                    "field": f"active_tasks[{i}]",
                    "expected": "title",
                    "actual": "description",
                    "description": f"active_tasks[{i}] usa 'description' invece di 'title' (convenzione: usare 'title')",
                }
            )
        if t.responsible and not t.delegated_to:
            sp.warnings.append(
                {
                    "type": "wrong_field",
                    "field": f"active_tasks[{i}]",
                    "expected": "delegated_to",
                    "actual": "responsible",
                    "description": f"active_tasks[{i}] usa 'responsible' invece di 'delegated_to' (convenzione: usare 'delegated_to')",
                }
            )
        if t.status and t.status not in STATI_TASK:
            sp.warnings.append(
                {
                    "type": "invalid_enum",
                    "field": f"active_tasks[{i}].status",
                    "actual": t.status,
                    "expected": sorted(STATI_TASK),
                    "description": f"Stato '{t.status}' non valido. Attesi: {', '.join(sorted(STATI_TASK))}",
                }
            )

    ms = sp.raw.get("members_status")
    if ms is None:
        sp.warnings.append(
            {
                "type": "missing_field",
                "field": "members_status",
                "description": "Campo 'members_status' assente nel frontmatter",
            }
        )
    elif not isinstance(ms, dict):
        sp.warnings.append(
            {
                "type": "wrong_type",
                "field": "members_status",
                "description": "members_status non è un mapping valido",
            }
        )

    raw_decisions = sp.raw.get("decisions", [])
    if not isinstance(raw_decisions, list):
        sp.warnings.append(
            {"type": "wrong_type", "field": "decisions", "description": "decisions non è una lista"}
        )
    elif len(raw_decisions) == 0:
        sp.warnings.append(
            {"type": "empty_list", "field": "decisions", "description": "decisions è vuoto"}
        )

    for i, d in enumerate(sp.decisions):
        if not d.id:
            sp.warnings.append(
                {
                    "type": "missing_field",
                    "field": f"decisions[{i}].id",
                    "description": f"Decisione {i} senza id",
                }
            )
        if not d.date:
            sp.warnings.append(
                {
                    "type": "missing_field",
                    "field": f"decisions[{i}].date",
                    "description": f"Decisione {d.id} senza date",
                }
            )
        if not d.description:
            sp.warnings.append(
                {
                    "type": "missing_field",
                    "field": f"decisions[{i}].description",
                    "description": f"Decisione {d.id} senza description",
                }
            )

    if "last_updated" not in sp.raw:
        sp.warnings.append(
            {
                "type": "missing_field",
                "field": "last_updated",
                "severity": "minor",
                "description": "Campo 'last_updated' mancante (opzionale)",
            }
        )

    logger.debug(f"Validazione scratchpad: {len(sp.errors)} errori, {len(sp.warnings)} warning")
    return sp


def validate_handoff_name(path: Path) -> list[str]:
    """Validate a handoff file name against the project naming convention.

    Returns a list of error messages, empty if the name is valid.
    """
    name = path.name
    if not HANDOFF_NAME_RE.match(name):
        return [f"nome file non segue convenzione: {name}"]
    return []


def validate_handoff_fields(
    """Validate handoff frontmatter fields for required values and known enums.

    Returns a tuple of (errors, warnings).
    """
    
    fm: dict[str, Any],
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    errors: list[dict[str, Any]] = []
    warnings: list[dict[str, Any]] = []

    required = ("data", "mittente", "destinatario", "tipo", "stato", "priorita", "titolo")
    for campo in required:
        if campo not in fm or fm[campo] is None:
            errors.append(
                {
                    "type": "missing_field",
                    "field": campo,
                    "description": f"Campo obbligatorio mancante: '{campo}'",
                }
            )

    if "mittente" in fm and fm["mittente"]:
        val = str(fm["mittente"]).lower()
        if val not in MEMBRI:
            warnings.append(
                {
                    "type": "invalid_value",
                    "field": "mittente",
                    "actual": val,
                    "description": f"Mittente '{val}' non è un membro valido",
                }
            )

    if "destinatario" in fm and fm["destinatario"]:
        val = str(fm["destinatario"]).lower()
        if val not in MEMBRI and val != "team":
            warnings.append(
                {
                    "type": "invalid_value",
                    "field": "destinatario",
                    "actual": val,
                    "description": f"Destinatario '{val}' non è un membro valido o 'team'",
                }
            )

    if "tipo" in fm and fm["tipo"]:
        val = str(fm["tipo"]).lower()
        if val not in TIPI_HANDOFF:
            warnings.append(
                {
                    "type": "invalid_enum",
                    "field": "tipo",
                    "actual": val,
                    "expected": sorted(TIPI_HANDOFF),
                    "description": f"Tipo '{val}' non valido. Valori attesi: {', '.join(sorted(TIPI_HANDOFF))}",
                }
            )

    if "stato" in fm and fm["stato"]:
        val = str(fm["stato"]).lower()
        if val not in STATI_HANDOFF:
            warnings.append(
                {
                    "type": "invalid_enum",
                    "field": "stato",
                    "actual": val,
                    "expected": sorted(STATI_HANDOFF),
                    "description": f"Stato '{val}' non valido. Valori attesi: {', '.join(sorted(STATI_HANDOFF))}",
                }
            )

    if "priorita" in fm and fm["priorita"]:
        val = str(fm["priorita"]).lower()
        if val not in PRIORITA_VALIDE:
            warnings.append(
                {
                    "type": "invalid_enum",
                    "field": "priorita",
                    "actual": val,
                    "expected": sorted(PRIORITA_VALIDE),
                    "description": f"Priorità '{val}' non valida. Valori attesi: {', '.join(sorted(PRIORITA_VALIDE))}",
                }
            )

    return errors, warnings


def validate_handoff_file(path: Path) -> HandoffValidation:
    """Run all validation checks on a single handoff file.

    Validates the file name and frontmatter fields, then returns a
    HandoffValidation object with errors and warnings.
    """
    hv = HandoffValidation(path=path)

    fm, read_warnings = read_frontmatter(path)
    hv.frontmatter = fm
    hv.has_frontmatter = bool(fm)

    for w in read_warnings:
        hv.warnings.append({"type": "read", "description": w})

    naming_errors = validate_handoff_name(path)
    hv.naming_errors = naming_errors
    hv.naming_valid = len(naming_errors) == 0

    if hv.has_frontmatter:
        field_errors, field_warnings = validate_handoff_fields(fm)
        hv.errors.extend(field_errors)
        hv.warnings.extend(field_warnings)

    logger.debug(
        f"Validato handoff: {path.name} — naming_valid={hv.naming_valid}, errors={len(hv.errors)}, warnings={len(hv.warnings)}"
    )
    return hv
