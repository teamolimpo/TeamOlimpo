from __future__ import annotations

import re
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any

from loguru import logger

from tools.hermes_cli.config import SCRATCHPAD_PATH, STATI_HANDOFF
from tools.hermes_cli.models import Scratchpad
from tools.hermes_cli.scanner import read_frontmatter, read_scratchpad
from tools.hermes_cli.validator import validate_handoff_file

TASK_ID_BODY_RE = re.compile(r"\[(T-[A-Z0-9-]+)\]")

BODY_STATUS_MAP: dict[str, str] = {
    "\u2705": "completed",
    "COMPLETATO": "completed",
    "\u23f3": "in_progress",
    "IN CORSO": "in_progress",
    "\u274c": "cancelled",
    "CANCELLED": "cancelled",
    "\u23f8": "blocked",
    "IN ATTESA": "blocked",
    "ARCHIVIATO": "archived",
    "PENDING": "pending",
}


def _infer_body_status(line: str) -> str:
    upper = line.upper()
    for marker, status in BODY_STATUS_MAP.items():
        if marker in upper or marker in line:
            return status
    return "unknown"


def _extract_body_tasks(body_text: str) -> list[dict[str, Any]]:
    tasks: list[dict[str, Any]] = []
    in_task_section = False

    for line in body_text.split("\n"):
        stripped = line.strip()
        if stripped.startswith("## "):
            in_task_section = "task in corso" in stripped.lower()
            continue
        if not in_task_section:
            continue
        for match in TASK_ID_BODY_RE.finditer(line):
            tasks.append(
                {
                    "id": match.group(1),
                    "status": _infer_body_status(line),
                    "line": stripped[:80],
                }
            )

    return tasks


def generate_report(
    scratchpad: Scratchpad,
    handoff_paths: list[Path],
    short: bool = False,
) -> dict[str, Any]:
    result: dict[str, Any] = {
        "short": short,
        "tasks": {
            "open": 0,
            "completed": 0,
            "blocked": 0,
            "cancelled": 0,
            "total": 0,
            "by_agent": {},
        },
        "handoffs": {
            "da-processare": 0,
            "in-corso": 0,
            "bloccato": 0,
            "completato": 0,
            "senza_stato": 0,
            "total": len(handoff_paths),
        },
        "conformity": {
            "scratchpad": {
                "errors": len(scratchpad.errors),
                "warnings": len(scratchpad.warnings),
            },
            "handoffs": {"conformi": 0, "warning": 0, "errori": 0},
            "ids": {"duplicates": 0, "duplicate_ids": []},
        },
    }

    for t in scratchpad.tasks:
        result["tasks"]["total"] += 1
        if t.status == "completed":
            result["tasks"]["completed"] += 1
        elif t.status == "blocked":
            result["tasks"]["blocked"] += 1
        elif t.status == "cancelled":
            result["tasks"]["cancelled"] += 1
        else:
            result["tasks"]["open"] += 1

    for t in scratchpad.tasks:
        agent = (t.delegated_to or t.responsible or "unknown").lower()
        result["tasks"]["by_agent"].setdefault(agent, [])
        result["tasks"]["by_agent"][agent].append(
            {
                "id": t.id,
                "status": t.status or "unknown",
            }
        )

    for hp in handoff_paths:
        hv = validate_handoff_file(hp)
        stato = str(hv.frontmatter.get("stato", "")).lower() if hv.frontmatter else ""
        if stato in STATI_HANDOFF:
            result["handoffs"][stato] += 1
        else:
            result["handoffs"]["senza_stato"] += 1
        if hv.errors:
            result["conformity"]["handoffs"]["errori"] += 1
        elif hv.warnings:
            result["conformity"]["handoffs"]["warning"] += 1
        else:
            result["conformity"]["handoffs"]["conformi"] += 1

    from tools.hermes_cli.id_manager import check_duplicate_ids

    conflicts = check_duplicate_ids(scratchpad, handoff_paths)
    result["conformity"]["ids"]["duplicates"] = len(conflicts)
    result["conformity"]["ids"]["duplicate_ids"] = [c["id"] for c in conflicts]

    logger.debug(
        f"Report: {result['tasks']['total']} task, "
        f"{result['handoffs']['total']} handoff, "
        f"{result['conformity']['handoffs']['conformi']} conformi"
    )
    return result


def generate_diff(scratchpad: Scratchpad, scratchpad_text: str) -> dict[str, Any]:
    if scratchpad_text.startswith("---"):
        end_marker = scratchpad_text.find("\n---", 3)
        body_text = scratchpad_text[end_marker + 5 :] if end_marker != -1 else scratchpad_text
    else:
        body_text = scratchpad_text

    fm_tasks: dict[str, str] = {t.id: t.status or "unknown" for t in scratchpad.tasks if t.id}

    body_task_list = _extract_body_tasks(body_text)
    body_tasks: dict[str, str] = {t["id"]: t["status"] for t in body_task_list}

    only_in_fm: dict[str, str] = {tid: s for tid, s in fm_tasks.items() if tid not in body_tasks}
    only_in_body: dict[str, str] = {tid: s for tid, s in body_tasks.items() if tid not in fm_tasks}
    status_mismatch: dict[str, dict[str, str]] = {}
    for tid in fm_tasks:
        if tid in body_tasks and fm_tasks[tid] != body_tasks[tid]:
            status_mismatch[tid] = {"fm": fm_tasks[tid], "body": body_tasks[tid]}

    total = len(only_in_fm) + len(only_in_body) + len(status_mismatch)

    logger.debug(
        f"Diff: {len(only_in_fm)} solo FM, {len(only_in_body)} solo body, {len(status_mismatch)} stato diff"
    )
    return {
        "diff": True,
        "only_in_frontmatter": only_in_fm,
        "only_in_body": only_in_body,
        "status_mismatch": status_mismatch,
        "total_discrepancies": total,
        "aligned": total == 0,
    }


def generate_stats(
    handoff_paths: list[Path],
    month: str | None = None,
    agent: str | None = None,
) -> dict[str, Any]:
    sp = read_scratchpad(SCRATCHPAD_PATH)

    tasks_by_agent: dict[str, dict[str, int]] = defaultdict(
        lambda: {"total": 0, "completed": 0, "in_progress": 0, "other": 0},
    )
    for t in sp.tasks:
        aname = (t.delegated_to or t.responsible or "unknown").lower()
        tasks_by_agent[aname]["total"] += 1
        if t.status == "completed":
            tasks_by_agent[aname]["completed"] += 1
        elif t.status == "in_progress":
            tasks_by_agent[aname]["in_progress"] += 1
        else:
            tasks_by_agent[aname]["other"] += 1

    by_tipo: Counter[str] = Counter()
    by_mittente: Counter[str] = Counter()
    by_month: Counter[str] = Counter()

    for hp in handoff_paths:
        fm, _ = read_frontmatter(hp)
        if not fm:
            continue
        data = str(fm.get("data", ""))
        hp_month = data[:7] if len(data) >= 7 else ""
        mittente_val = str(fm.get("mittente", "")).lower()

        if month and hp_month != month:
            continue
        if agent and mittente_val != agent.lower():
            continue

        by_tipo[str(fm.get("tipo", "unknown")).lower()] += 1
        by_mittente[mittente_val] += 1
        if hp_month:
            by_month[hp_month] += 1

    result: dict[str, Any] = {
        "tasks_by_agent": {k: dict(v) for k, v in sorted(tasks_by_agent.items())},
        "handoffs_by_type": dict(by_tipo.most_common()),
        "handoffs_by_sender": dict(by_mittente.most_common()),
        "handoffs_by_month": dict(sorted(by_month.items())),
        "filtered": month is not None or agent is not None,
    }
    if month:
        result["filter_month"] = month
    if agent:
        result["filter_agent"] = agent

    return result
