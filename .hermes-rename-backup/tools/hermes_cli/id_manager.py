from __future__ import annotations

import re
from pathlib import Path
from typing import Any

from loguru import logger

from tools.hermes_cli.models import Scratchpad
from tools.hermes_cli.scanner import read_handoff_body, scan_handoff_files

TASK_ID_RE = re.compile(r"T-(?:[A-Z]+-)?(\d{3})")
DECISION_ID_RE = re.compile(r"D-(?:[A-Z]+-)?(\d{3})")

TASK_ID_STRICT_RE = re.compile(r"T-(\d{3})(?:\b|[^A-Za-z]|$)")
DECISION_ID_STRICT_RE = re.compile(r"D-(\d{3})(?:\b|[^A-Za-z]|$)")


def _extract_nums(regex: re.Pattern[str], texts: list[str]) -> set[int]:
    nums: set[int] = set()
    for text in texts:
        for match in regex.finditer(text):
            nums.add(int(match.group(1)))
    return nums


def find_next_id(existing_ids: set[int], prefix: str) -> str:
    if not existing_ids:
        return f"{prefix}-001"
    max_id = max(existing_ids)
    return f"{prefix}-{max_id + 1:03d}"


def _get_id_texts(sp: Scratchpad, handoff_paths: list[Path]) -> tuple[list[str], list[str]]:
    task_texts: list[str] = []
    decision_texts: list[str] = []

    for t in sp.tasks:
        task_texts.append(t.id)

    for d in sp.decisions:
        decision_texts.append(d.id)

    try:
        body = sp.path.read_text(encoding="utf-8")
        task_texts.append(body)
        decision_texts.append(body)
    except OSError:
        pass

    for hp in handoff_paths:
        try:
            body = read_handoff_body(hp)
            task_texts.append(hp.name + "\n" + body)
            decision_texts.append(hp.name + "\n" + body)
        except OSError:
            pass

    return task_texts, decision_texts


def find_next_task_id(sp: Scratchpad, handoff_paths: list[Path] | None = None) -> str:
    if handoff_paths is None:
        handoff_paths = scan_handoff_files()

    task_texts, _ = _get_id_texts(sp, handoff_paths)

    nums = _extract_nums(TASK_ID_STRICT_RE, task_texts)
    if not nums:
        nums = _extract_nums(TASK_ID_RE, task_texts)

    logger.debug(
        f"find_next_task_id: found {len(nums)} existing T-NNN IDs, max={max(nums) if nums else 'none'}"
    )
    return find_next_id(nums, "T")


def find_next_decision_id(sp: Scratchpad, handoff_paths: list[Path] | None = None) -> str:
    if handoff_paths is None:
        handoff_paths = scan_handoff_files()

    _, decision_texts = _get_id_texts(sp, handoff_paths)

    nums = _extract_nums(DECISION_ID_STRICT_RE, decision_texts)
    if not nums:
        nums = _extract_nums(DECISION_ID_RE, decision_texts)

    logger.debug(
        f"find_next_decision_id: found {len(nums)} existing D-NNN IDs, max={max(nums) if nums else 'none'}"
    )
    return find_next_id(nums, "D")


def check_duplicate_ids(
    sp: Scratchpad, handoff_paths: list[Path] | None = None
) -> list[dict[str, Any]]:
    if handoff_paths is None:
        handoff_paths = scan_handoff_files()

    id_map: dict[str, list[dict[str, str]]] = {}

    for t in sp.tasks:
        if t.id:
            id_map.setdefault(t.id, []).append({"source": "scratchpad.tasks", "path": str(sp.path)})

    for d in sp.decisions:
        if d.id:
            id_map.setdefault(d.id, []).append(
                {"source": "scratchpad.decisions", "path": str(sp.path)}
            )

    for hp in handoff_paths:
        try:
            body = read_handoff_body(hp)
            full_text = hp.name + "\n" + body
            for match in TASK_ID_RE.finditer(full_text):
                full_id = match.group(0)
                id_map.setdefault(full_id, []).append({"source": "handoff_body", "path": str(hp)})
            for match in DECISION_ID_RE.finditer(full_text):
                full_id = match.group(0)
                id_map.setdefault(full_id, []).append({"source": "handoff_body", "path": str(hp)})
        except OSError:
            pass

    conflicts: list[dict[str, Any]] = []
    for id_val, occurrences in id_map.items():
        if len(occurrences) > 1:
            conflicts.append({"id": id_val, "occurrences": occurrences})

    logger.debug(f"check_duplicates: {len(conflicts)} conflitti trovati su {len(id_map)} ID unici")
    return conflicts
