"""Migrate existing tasks from ``Team/Poros/Scratchpad.md`` to ``state.yaml``.

Giorno 0 migration: reads the Scratchpad Markdown file (YAML frontmatter +
body task notation) and produces a ``state.yaml`` snapshot that preserves
all historical task IDs, statuses, and relationships.

The Scratchpad's YAML frontmatter has inconsistent indentation (items in the
same list use different indent levels). Therefore, this module uses a custom
line-by-line parser instead of ``yaml.safe_load`` for the frontmatter.
"""

from __future__ import annotations

import re
from pathlib import Path
from typing import Any

from loguru import logger

from tools.taskmanager.models import (
    FRONTMATTER_STATUS_MAP,
    STATUS_FROM_MARKER,
    TASK_NOTATION_REGEX,
    now_iso,
)
from tools.taskmanager.state import DEFAULT_STATE, StateStore

# ---------------------------------------------------------------------------
# Scratchpad path
# ---------------------------------------------------------------------------


def _find_scratchpad(project_root: Path) -> Path | None:
    """Locate ``Team/Poros/Scratchpad.md`` relative to project root.

    Returns the path, or ``None`` if the file does not exist.
    """
    path = project_root / "lib" / "Fucina" / "Poros" / "Scratchpad.md"
    if path.is_file():
        return path
    return None


# ---------------------------------------------------------------------------
# Custom YAML-like frontmatter parser for loose indentation
# ---------------------------------------------------------------------------

# Regex for lines inside active_tasks
_ID_LINE_RE = re.compile(r"^(\s*)(?:- )?id:\s*\"(.+?)\"\s*$")
_KEY_VALUE_RE = re.compile(r"^(\s*)(\w[\w_]*):\s*\"?(.+?)\"?\s*$")
_SUBTASKS_KEY_RE = re.compile(r"^(\s*)subtasks:\s*$")


def _parse_active_tasks(fm_text: str) -> list[dict[str, Any]]:
    """Parse the ``active_tasks`` list from raw YAML frontmatter text.

    Uses a line-by-line parser that is tolerant of inconsistent indentation
    (which the Scratchpad has). Each task and its subtasks are extracted
    as structured dicts.

    Args:
        fm_text: The raw YAML frontmatter string (between ``---`` delimiters).

    Returns:
        List of task dicts with keys: ``id``, ``description``, ``status``,
        ``responsible``, and optionally ``subtasks``.
    """
    lines = fm_text.split("\n")

    # Locate the active_tasks section
    active_start = -1
    for i, line in enumerate(lines):
        if line.rstrip() == "active_tasks:":
            active_start = i
            break

    if active_start == -1:
        return []

    active_lines = lines[active_start + 1 :]

    # Track the base indent of the first list item under active_tasks
    # Items belong to the same list if their indent matches the base level
    # (or is within 1-2 spaces of it, due to Scratchpad's quirks)
    first_indent: int | None = None

    tasks: list[dict[str, Any]] = []
    current_task: dict[str, Any] | None = None
    current_subs: list[dict[str, Any]] = []
    in_subtasks = False
    subtask_indent: int | None = None

    for raw_line in active_lines:
        if not raw_line.strip():
            continue

        orig_indent = len(raw_line) - len(raw_line.lstrip())

        # --- Detect list item start (line with `- id:`) ---
        id_match = _ID_LINE_RE.match(raw_line)
        if id_match:
            id_indent = len(id_match.group(1))

            # Determine if this is a parent-level task or a subtask
            # Heuristic: if indent is deeper than subtask_indent, it's a subtask
            if in_subtasks and subtask_indent is not None:
                # Check if this subtask has similar indent to other subtasks
                if abs(id_indent - subtask_indent) <= 2:
                    # This is another subtask in the current list
                    sub_id = id_match.group(2)
                    current_subs.append(
                        {
                            "id": sub_id,
                            "_line": raw_line,
                            "_indent": id_indent,
                        }
                    )
                    current_task["subtasks"] = current_subs  # type: ignore[union-attr]
                    continue

            # This is a parent-level task
            # Save previous task if any
            if current_task is not None:
                tasks.append(current_task)

            if first_indent is None:
                first_indent = id_indent

            task_id = id_match.group(2)
            current_task = {
                "id": task_id,
                "_line": raw_line,
                "_indent": id_indent,
                "subtasks": [],
            }
            current_subs = []
            in_subtasks = False
            subtask_indent = None
            continue

        # --- Detect `subtasks:` key ---
        sub_key_match = _SUBTASKS_KEY_RE.match(raw_line)
        if sub_key_match and current_task is not None:
            in_subtasks = True
            subtask_indent = (orig_indent // 2) * 2 + 2  # expected subtask indent
            continue

        # --- Detect key-value pairs (`description:`, `status:`, etc.) ---
        kv_match = _KEY_VALUE_RE.match(raw_line)
        if not kv_match or current_task is None:
            continue

        key = kv_match.group(2)
        value = kv_match.group(3).strip().strip('"').strip("'")

        if in_subtasks and current_subs:
            # Add to current subtask
            current_subs[-1][key] = value
        elif current_task is not None:
            current_task[key] = value

    # Don't forget the last task
    if current_task is not None:
        tasks.append(current_task)

    # Clean up internal fields
    result: list[dict[str, Any]] = []
    for t in tasks:
        clean = {k: v for k, v in t.items() if not k.startswith("_")}
        # Clean up subtasks
        subs = clean.get("subtasks", [])
        if subs:
            clean_subs = []
            for s in subs:
                sc = {k: v for k, v in s.items() if not k.startswith("_")}
                clean_subs.append(sc)
            clean["subtasks"] = clean_subs
        result.append(clean)

    return result


def _parse_frontmatter(content: str) -> list[dict[str, Any]]:
    """Extract and parse the ``active_tasks`` list from Scratchpad frontmatter.

    Uses a custom line-by-line parser tolerant of indentation quirks.

    Returns:
        List of task dicts as they appear in the frontmatter YAML.
    """
    if not content.startswith("---"):
        return []

    parts = content.split("---", 2)
    if len(parts) < 3:
        return []

    return _parse_active_tasks(parts[1])


# ---------------------------------------------------------------------------
# Status mapping
# ---------------------------------------------------------------------------


def _normalize_status(raw: Any) -> str:
    """Map a status string (English, Italian, or marker) to canonical form.

    Examples::

        _normalize_status("completed")  -> "completed"
        _normalize_status("in corso")   -> "in_progress"
        _normalize_status("standby")    -> "standby"
    """
    if not isinstance(raw, str):
        return "pending"
    normalized = raw.strip().lower()
    return FRONTMATTER_STATUS_MAP.get(normalized, normalized)


# ---------------------------------------------------------------------------
# Body task notation parser
# ---------------------------------------------------------------------------


def _parse_body_tasks(body: str, known_ids: set[str]) -> list[dict[str, Any]]:
    """Parse body Markdown for task notation ``[T-ID] Description [STATUS]``.

    Returns a list of task dicts (with id, description, status).
    Tasks whose IDs are already in *known_ids* are skipped to avoid
    duplicates (frontmatter takes precedence).
    """
    results: list[dict[str, Any]] = []
    for match in TASK_NOTATION_REGEX.finditer(body):
        task_id = match.group(1).strip()
        description = match.group(2).strip()
        status_marker = match.group(3) or ""

        if task_id in known_ids:
            logger.debug(f"Body task {task_id} already in frontmatter, skipping")
            continue

        # Determine status from marker
        status = "pending"  # default
        for marker, mapped_status in STATUS_FROM_MARKER.items():
            if marker in status_marker:
                status = mapped_status
                break

        results.append(
            {
                "id": task_id,
                "description": description,
                "status": status,
                "priority": "medium",
                "owner": "Poros",
            }
        )
    return results


# ---------------------------------------------------------------------------
# Counter computation
# ---------------------------------------------------------------------------


def _compute_counters(tasks_dict: dict[str, Any]) -> dict[str, int]:
    """Compute max counter per area from all task IDs.

    Handles both standard IDs (T-AREA-NNN) and non-standard ones.
    """
    area_re = re.compile(r"^T-(.+)-(\d{3})$")
    counters: dict[str, int] = {}

    for tid in tasks_dict:
        m = area_re.match(tid)
        if m:
            area = m.group(1)
            num = int(m.group(2))
            current = counters.get(area, 0)
            if num > current:
                counters[area] = num
        else:
            # Non-standard ID — try to extract prefix
            m2 = re.match(r"^(.+)-(\d+)$", tid)
            if m2:
                area = m2.group(1)
                num = int(m2.group(2))
                current = counters.get(area, 0)
                if num > current:
                    counters[area] = num
    return counters


# ---------------------------------------------------------------------------
# Main migration
# ---------------------------------------------------------------------------


def migrate_from_scratchpad(store: StateStore) -> dict[str, Any]:
    """Run the Giorno 0 migration: Scratchpad -> state.yaml.

    Reads ``Team/Poros/Scratchpad.md``, extracts all tasks, and writes
    them into the provided ``StateStore``.

    Steps:
    1. Parse frontmatter for ``active_tasks[]`` using a custom line parser.
    2. Extract ``subtasks[]`` from each task.
    3. Parse body Markdown for ``[T-ID]`` notation with status markers.
    4. Merge both sources (frontmatter takes precedence for duplicate IDs).
    5. Compute area counters from the max numbered ID in each area.
    6. Write everything into ``state.yaml``.

    Args:
        store: An initialized ``StateStore`` (writes directly).

    Returns:
        The final state dict as written to ``state.yaml``.

    Raises:
        FileNotFoundError: If Scratchpad.md cannot be found.
    """
    from tools.taskmanager.state import _find_project_root

    project_root = _find_project_root()
    scratchpad_path = _find_scratchpad(project_root)

    if scratchpad_path is None:
        raise FileNotFoundError(
            f"Scratchpad.md not found in {project_root / 'Team' / 'Poros'}. Cannot run migration."
        )

    logger.info(f"Starting migration from {scratchpad_path}")
    content = scratchpad_path.read_text(encoding="utf-8")

    # --- Separate frontmatter from body ---
    body = content
    if content.startswith("---"):
        parts = content.split("---", 2)
        if len(parts) >= 3:
            body = parts[2]

    # --- Parse frontmatter active_tasks ---
    active_tasks = _parse_frontmatter(content)
    logger.info(f"Found {len(active_tasks)} tasks in frontmatter")

    # --- Build tasks dict from frontmatter ---
    tasks_dict: dict[str, dict[str, Any]] = {}
    known_ids: set[str] = set()

    for entry in active_tasks:
        if "id" not in entry:
            continue
        task_id = entry["id"]
        known_ids.add(task_id)

        # Handle subtasks for frontmatter
        raw_subs = entry.get("subtasks", [])
        if isinstance(raw_subs, list) and len(raw_subs) > 0 and isinstance(raw_subs[0], dict):
            # Some entries have subtasks with 'subtasks:' key pointing to a list
            # already processed by our parser
            subtasks_list = raw_subs
        else:
            subtasks_list = []

        # Collect subtask IDs for status check
        sub_ids_in_entry = [s["id"] for s in subtasks_list if isinstance(s, dict) and "id" in s]

        # Determine status: if all subtasks are "completed", task can be "completed"
        # unless explicitly set otherwise
        entry_status = entry.get("status", "pending")
        if isinstance(entry_status, str):
            status = _normalize_status(entry_status)
        else:
            status = "pending"

        tasks_dict[task_id] = {
            "id": task_id,
            "description": entry.get("description", ""),
            "status": status,
            "priority": "medium",
            "owner": entry.get("responsible", "Poros"),
            "tags": [],
            "parent": None,
            "handoff_refs": [],
            "events": [],
            "created_at": now_iso(),
            "updated_at": now_iso(),
        }

        # Process subtasks
        for sub_entry in subtasks_list:
            if not isinstance(sub_entry, dict) or "id" not in sub_entry:
                continue
            sub_id = sub_entry["id"]
            known_ids.add(sub_id)
            sub_status_raw = sub_entry.get("status", "pending")
            sub_status = (
                _normalize_status(sub_status_raw) if isinstance(sub_status_raw, str) else "pending"
            )

            tasks_dict[sub_id] = {
                "id": sub_id,
                "description": sub_entry.get("description", ""),
                "status": sub_status,
                "priority": "medium",
                "owner": entry.get("responsible", "Poros"),
                "tags": [],
                "parent": task_id,
                "handoff_refs": [],
                "events": [],
                "created_at": now_iso(),
                "updated_at": now_iso(),
            }

    # --- Parse body tasks ---
    body_tasks = _parse_body_tasks(body, known_ids)
    for bt in body_tasks:
        bt["created_at"] = now_iso()
        bt["updated_at"] = now_iso()
        bt["tags"] = []
        bt["handoff_refs"] = []
        bt["events"] = []
        bt["parent"] = None
        tasks_dict[bt["id"]] = bt

    if not tasks_dict:
        logger.warning("No tasks found in Scratchpad. Creating empty state.")
        return DEFAULT_STATE

    # --- Compute area counters ---
    counters = _compute_counters(tasks_dict)

    # --- Create events ---
    ts = now_iso()
    for task_id, task_dict in tasks_dict.items():
        if task_dict.get("parent"):
            event_details = "Subtask importato da Scratchpad (migrazione Giorno 0)"
        else:
            event_details = "Task importato da Scratchpad (migrazione Giorno 0)"
        task_dict["events"] = [
            {
                "timestamp": ts,
                "type": "created",
                "details": event_details,
            }
        ]

    # --- Build final state ---
    state: dict[str, Any] = {
        "version": 1,
        "last_updated": ts,
        "counter": counters,
        "tasks": tasks_dict,
    }

    # --- Write to store ---
    store._data = state  # type: ignore[attr-defined]
    store.save()

    with_parent = sum(1 for t in tasks_dict.values() if t.get("parent"))

    logger.info(
        f"Migration complete: {len(tasks_dict)} tasks imported "
        f"({with_parent} with parent), "
        f"{len(counters)} areas tracked"
    )
    return state


def migrate_dry_run(store: StateStore) -> dict[str, Any]:
    """Run migration in dry-run mode (no writes).

    Returns the state dict that *would* be written, without modifying
    the backing file. Useful for previewing the migration result.
    """
    original_data = store._data  # type: ignore[attr-defined]

    try:
        from tools.taskmanager.state import _find_project_root

        project_root = _find_project_root()
        scratchpad_path = _find_scratchpad(project_root)

        if scratchpad_path is None:
            raise FileNotFoundError("Scratchpad.md not found")

        content = scratchpad_path.read_text(encoding="utf-8")

        body = content
        if content.startswith("---"):
            parts = content.split("---", 2)
            if len(parts) >= 3:
                body = parts[2]

        active_tasks = _parse_frontmatter(content)
        tasks_dict: dict[str, Any] = {}
        known_ids: set[str] = set()

        for entry in active_tasks:
            if "id" not in entry:
                continue
            task_id = entry["id"]
            known_ids.add(task_id)
            task_entry: dict[str, Any] = {
                "id": task_id,
                "description": entry.get("description", ""),
                "status": _normalize_status(entry.get("status", "pending")),
                "owner": entry.get("responsible", "Poros"),
                "subtask_count": 0,
            }
            subs = entry.get("subtasks", [])
            if isinstance(subs, list):
                for s in subs:
                    if isinstance(s, dict) and "id" in s:
                        known_ids.add(s["id"])
                        task_entry["subtask_count"] += 1
            tasks_dict[task_id] = task_entry

        body_tasks = _parse_body_tasks(body, known_ids)
        for bt in body_tasks:
            tasks_dict[bt["id"]] = bt

        return {
            "version": 1,
            "counter": _compute_counters(tasks_dict),
            "tasks": tasks_dict,
            "note": "DRY RUN — no file written",
        }
    finally:
        store._data = original_data
