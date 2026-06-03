"""MCP server: expose 6 ``task_*`` tools for Team Olimpo task management.

Usage::

    uv run python -m tools.taskmanager.server

The server listens on stdio (MCP stdio transport). An MCP client (e.g.
``opencode.json``'s ``mcp`` section) connects to it and calls the
``task_*`` tools.

Tools
-----
- task_create — Create a new task.
- task_update_status — Transition a task's status.
- task_query — Search and filter tasks.
- task_summary — Aggregate task statistics.
- task_log_event — Append an event to a task's log.
- task_export — Dump all state as YAML.
- taskmanager_compress — Compress task event logs (hot/warm/cold).
"""

from __future__ import annotations

import json
from typing import Any

from loguru import logger

from tools.taskmanager.models import (
    INITIAL_STATUSES,
    TASK_ID_REGEX,
    VALID_PRIORITIES,
    VALID_STATUSES,
    StateMachine,
    extract_area_from_description,
    extract_area_from_task_id,
    now_iso,
    truncate_description,
    validate_event_type,
    validate_priority,
    validate_status,
)
from tools.taskmanager.state import StateStore, compress_events

# ---------------------------------------------------------------------------
# MCP SDK — graceful fallback if missing
# ---------------------------------------------------------------------------

try:
    from mcp.server.fastmcp import FastMCP

    mcp = FastMCP("taskmanager")
    MCP_AVAILABLE = True
except ImportError:
    MCP_AVAILABLE = False

# ---------------------------------------------------------------------------
# Backing store (singleton-like, created on first use)
# ---------------------------------------------------------------------------

_store: StateStore | None = None


def _get_store() -> StateStore:
    """Return the global ``StateStore`` instance, creating it if needed."""
    global _store
    if _store is None:
        _store = StateStore()
        _store.load()  # ensure loaded
    return _store


# ---------------------------------------------------------------------------
# Helper: ensure store is loaded and return its data
# ---------------------------------------------------------------------------


def _load_data() -> dict[str, Any]:
    """Load and return the state data dict."""
    return _get_store().load()


def _save_data() -> None:
    """Persist current state to disk."""
    _get_store().save()


def _task_dict_to_json(task_dict: dict[str, Any], include_events: bool = False) -> dict[str, Any]:
    """Convert a raw task dict from storage to a JSON-friendly output dict.

    Args:
        task_dict: Raw task dict from state.yaml (includes ``events`` list).
        include_events: If True, include full events in output.

    Returns:
        A cleaned dict suitable for JSON serialization.
    """
    events = task_dict.get("events", [])
    result: dict[str, Any] = {
        "id": task_dict["id"],
        "description": task_dict.get("description", ""),
        "status": task_dict.get("status", "pending"),
        "priority": task_dict.get("priority", "medium"),
        "owner": task_dict.get("owner", "Hermes"),
        "created_at": task_dict.get("created_at", ""),
        "updated_at": task_dict.get("updated_at", ""),
        "tags": task_dict.get("tags", []),
        "parent": task_dict.get("parent"),
        "handoff_refs": task_dict.get("handoff_refs", []),
        "compression_level": task_dict.get("compression_level", 0),
        "event_count": len(events),
    }
    if include_events:
        result["events"] = events
    return result


# ---------------------------------------------------------------------------
# Tool 1: task_create
# ---------------------------------------------------------------------------


@mcp.tool()
def task_create(
    description: str,
    priority: str = "medium",
    owner: str = "Hermes",
    status: str = "pending",
    task_id: str | None = None,
    parent: str | None = None,
    tags: list[str] | None = None,
) -> str:
    """Create a new task.

    Generates an ID automatically (T-<AREA>-<NNN>) if ``task_id`` is omitted.
    If ``parent`` is specified, the area is derived from the parent's ID.

    Parameters
    ----------
    description : str
        Task description (max 150 characters; auto-truncated with warning).
    priority : str
        One of ``low``, ``medium`` (default), ``high``, ``critical``.
    owner : str
        Agent name or ``"user"`` (default ``"Hermes"``).
    status : str
        Initial status: ``"pending"`` (default) or ``"standby"``.
    task_id : str | None
        Explicit ID (format ``T-<AREA>-<NNN>``). Omit for auto-generation.
    parent : str | None
        ID of the parent task (for hierarchical subtasks).
    tags : list[str] | None
        List of single-word tags.
    """
    logger.info(
        f"task_create called: desc={description[:50]}..., "
        f"priority={priority}, owner={owner}, status={status}, "
        f"task_id={task_id}, parent={parent}"
    )

    # --- Validate required ---
    if not description or not description.strip():
        return json.dumps({"error": "Il parametro 'description' è obbligatorio."})

    # --- Truncate description ---
    description, was_truncated = truncate_description(description.strip(), max_len=150)
    if was_truncated:
        logger.warning(f"Description truncated to 150 characters: {description[:80]}...")

    # --- Validate priority ---
    try:
        validate_priority(priority)
    except ValueError as e:
        return json.dumps({"error": str(e)})

    # --- Validate status ---
    try:
        validate_status(status)
    except ValueError as e:
        return json.dumps({"error": str(e)})

    if status not in INITIAL_STATUSES:
        return json.dumps(
            {
                "error": (
                    f"Status '{status}' non valido per creazione. "
                    f"Usa uno di: {', '.join(INITIAL_STATUSES)}."
                )
            }
        )

    # --- Validate tags ---
    if tags is not None:
        cleaned_tags: list[str] = []
        for tag in tags:
            t = tag.strip()
            if " " in t:
                return json.dumps(
                    {"error": f"Tag '{t}' contiene spazi. I tag devono essere una singola parola."}
                )
            if t:
                cleaned_tags.append(t)
        tags = cleaned_tags

    store = _get_store()

    # --- Resolve task_id ---
    final_id: str | None = task_id
    if final_id is not None:
        # Validate format
        if not TASK_ID_REGEX.match(final_id):
            return json.dumps(
                {
                    "error": (
                        f"ID '{final_id}' non valido. Il formato deve essere "
                        f"T-<AREA>-<NNN> (es. T-MCP-001)."
                    )
                }
            )
        # Check uniqueness
        if store.get_task(final_id) is not None:
            return json.dumps(
                {
                    "error": f"ID '{final_id}' già in uso. Usa un ID diverso o ometti per generazione automatica."
                }
            )
    else:
        # Auto-generate ID
        if parent:
            # Derive area from parent's ID
            parent_task = store.get_task(parent)
            if parent_task is None:
                return json.dumps({"error": f"Parent task '{parent}' non trovato."})
            area = extract_area_from_task_id(parent_task["id"])
        else:
            area = extract_area_from_description(description)

        final_id = store.next_task_id(area)

    # --- Validate parent (if specified) ---
    if parent is not None:
        parent_task = store.get_task(parent)
        if parent_task is None:
            return json.dumps({"error": f"Parent task '{parent}' non trovato."})

    # --- Build task dict ---
    ts = now_iso()
    task_dict: dict[str, Any] = {
        "id": final_id,
        "description": description,
        "status": status,
        "priority": priority,
        "owner": owner,
        "created_at": ts,
        "updated_at": ts,
        "tags": tags or [],
        "parent": parent,
        "handoff_refs": [],
        "events": [
            {
                "timestamp": ts,
                "type": "created",
                "details": f"Task creato da {owner}" if owner else "Task creato",
            }
        ],
    }

    # --- Persist ---
    store._ensure_loaded_for_write()  # type: ignore[attr-defined]
    store.get_tasks()[final_id] = task_dict
    _save_data()

    logger.info(f"Task created: {final_id} (status={status}, owner={owner})")

    return json.dumps(
        {
            "id": final_id,
            "status": status,
            "created_at": ts,
            "description": description,
        }
    )


# ---------------------------------------------------------------------------
# Tool 2: task_update_status
# ---------------------------------------------------------------------------


@mcp.tool()
def task_update_status(
    task_id: str,
    new_status: str,
    note: str | None = None,
) -> str:
    """Transition a task's status with state-machine validation.

    If the task has a parent and none of its siblings remain
    non-completed, the parent is auto-promoted to ``completed``
    (only if the parent is currently ``in_progress`` or ``pending``).

    Parameters
    ----------
    task_id : str
        ID of the task to update.
    new_status : str
        Target status (``pending``, ``in_progress``, ``completed``,
        ``cancelled``, ``blocked``, ``standby``).
    note : str | None
        Optional note about the transition.
    """
    logger.info(f"task_update_status: task={task_id} → {new_status}")

    # --- Validate inputs ---
    if not task_id:
        return json.dumps({"error": "Il parametro 'task_id' è obbligatorio."})
    try:
        validate_status(new_status)
    except ValueError as e:
        return json.dumps({"error": str(e)})

    store = _get_store()
    task_dict = store.get_task(task_id)
    if task_dict is None:
        return json.dumps({"error": f"Task '{task_id}' non trovato."})

    old_status = task_dict.get("status", "pending")

    # --- Validate transition ---
    if old_status == new_status:
        logger.warning(f"Task {task_id} already has status '{new_status}' — no-op")
        return json.dumps(
            {
                "id": task_id,
                "old_status": old_status,
                "new_status": new_status,
                "updated_at": task_dict.get("updated_at"),
                "auto_parent_completed": None,
                "warning": f"Task già in stato '{new_status}'.",
            }
        )

    try:
        StateMachine.validate_transition(old_status, new_status)
    except ValueError as e:
        return json.dumps({"error": str(e)})

    # --- Update task ---
    ts = now_iso()
    task_dict["status"] = new_status
    task_dict["updated_at"] = ts

    # Add event
    event_details = f"{new_status} ← {old_status}"
    if note:
        event_details += f" — {note}"
    task_dict.setdefault("events", []).append(
        {
            "timestamp": ts,
            "type": "status_change",
            "details": event_details,
        }
    )

    auto_parent_completed: str | None = None

    # --- Check parent auto-promotion ---
    parent_id = task_dict.get("parent")
    if parent_id and new_status == "completed":
        parent_task = store.get_task(parent_id)
        if parent_task:
            parent_status = parent_task.get("status", "")
            if parent_status in ("in_progress", "pending"):
                # Check all siblings
                all_tasks = store.get_tasks()
                siblings = [t for t in all_tasks.values() if t.get("parent") == parent_id]
                if siblings and all(s.get("status") == "completed" for s in siblings):
                    # Auto-promote parent
                    parent_task["status"] = "completed"
                    parent_task["updated_at"] = ts
                    parent_task.setdefault("events", []).append(
                        {
                            "timestamp": ts,
                            "type": "status_change",
                            "details": (
                                f"completed ← {parent_status} — "
                                f"auto-promozione: tutti i subtask completati"
                            ),
                        }
                    )
                    auto_parent_completed = parent_id
                    logger.info(
                        f"Parent {parent_id} auto-promoted to completed "
                        f"(all {len(siblings)} subtasks completed)"
                    )

    _save_data()

    logger.info(f"Task {task_id}: {old_status} → {new_status}")

    result: dict[str, Any] = {
        "id": task_id,
        "old_status": old_status,
        "new_status": new_status,
        "updated_at": ts,
        "auto_parent_completed": auto_parent_completed,
    }
    return json.dumps(result)


# ---------------------------------------------------------------------------
# Tool 3: task_query
# ---------------------------------------------------------------------------


@mcp.tool()
def task_query(
    status: str | None = None,
    owner: str | None = None,
    priority: str | None = None,
    task_id: str | None = None,
    parent: str | None = None,
    search: str | None = None,
    tag: str | None = None,
    since: str | None = None,
    limit: int = 20,
    include_events: bool = False,
) -> str:
    """Search and filter tasks.

    All filter parameters are combined with AND logic. If no filter is
    given, returns the last ``limit`` tasks ordered by ``updated_at``.

    Parameters
    ----------
    status : str | None
        Filter by status (``pending``, ``in_progress``, etc.).
    owner : str | None
        Filter by owner name.
    priority : str | None
        Filter by priority (``low``, ``medium``, ``high``, ``critical``).
    task_id : str | None
        Return a single task by ID.
    parent : str | None
        Filter by parent task ID (subtasks of a task).
    search : str | None
        Case-insensitive text search on ``description``.
    tag : str | None
        Filter by tag (must match exactly).
    since : str | None
        ISO 8601 timestamp; only tasks with ``updated_at >= since``.
    limit : int
        Max results (default 20, max 100).
    include_events : bool
        If True, include full event log in each task.
    """
    logger.debug(
        f"task_query: status={status}, owner={owner}, "
        f"priority={priority}, task_id={task_id}, parent={parent}, "
        f"search={search}, tag={tag}, since={since}, limit={limit}"
    )

    # --- Clamp limit ---
    if limit < 1:
        limit = 20
    if limit > 100:
        logger.warning(f"limit {limit} exceeds max 100, clamping to 100")
        limit = 100

    # --- Validate since ---
    if since:
        try:
            from datetime import datetime as dt_cls

            dt_cls.fromisoformat(since)
        except ValueError:
            return json.dumps(
                {
                    "error": f"Formato data 'since' non valido: '{since}'. Usa ISO 8601 (es. 2026-05-20T10:00:00)."
                }
            )

    store = _get_store()
    all_tasks = store.get_tasks()

    # If task_id is specified, return just that one
    if task_id:
        task = all_tasks.get(task_id)
        if task is None:
            return "[]"
        return json.dumps([_task_dict_to_json(task, include_events=include_events)])

    # --- Apply filters ---
    filtered: list[dict[str, Any]] = []
    for tid, t in all_tasks.items():
        if status is not None and t.get("status") != status:
            continue
        if owner is not None and t.get("owner", "").lower() != owner.lower():
            continue
        if priority is not None and t.get("priority") != priority:
            continue
        if parent is not None and t.get("parent") != parent:
            continue
        if tag is not None:
            task_tags = t.get("tags", [])
            if tag not in task_tags:
                continue
        if search is not None:
            desc = t.get("description", "").lower()
            if search.lower() not in desc:
                continue
        if since is not None:
            updated = t.get("updated_at", "")
            if updated < since:
                continue

        filtered.append(t)

    # --- Sort by updated_at descending (newest first) ---
    filtered.sort(key=lambda t: t.get("updated_at", ""), reverse=True)

    # --- Apply limit ---
    if limit > 0:
        filtered = filtered[:limit]

    # --- Convert to output format ---
    results = [_task_dict_to_json(t, include_events=include_events) for t in filtered]

    return json.dumps(results)


# ---------------------------------------------------------------------------
# Tool 4: task_summary
# ---------------------------------------------------------------------------


@mcp.tool()
def task_summary(
    owner: str | None = None,
) -> str:
    """Return aggregate task statistics.

    Parameters
    ----------
    owner : str | None
        If specified, only count tasks owned by this agent.
    """
    logger.debug(f"task_summary: owner={owner}")

    store = _get_store()
    all_tasks = store.get_tasks()

    if owner:
        filtered = [t for t in all_tasks.values() if t.get("owner", "").lower() == owner.lower()]
    else:
        filtered = list(all_tasks.values())

    # --- Counts ---
    total = len(filtered)
    by_status: dict[str, int] = {s: 0 for s in VALID_STATUSES}
    by_priority: dict[str, int] = {p: 0 for p in VALID_PRIORITIES}
    wip_current: list[str] = []
    oldest_pending: str | None = None
    oldest_pending_ts: str | None = None

    for t in filtered:
        s = t.get("status", "pending")
        by_status[s] = by_status.get(s, 0) + 1

        p = t.get("priority", "medium")
        by_priority[p] = by_priority.get(p, 0) + 1

        if s == "in_progress":
            wip_current.append(t["id"])

        if s == "pending":
            created = t.get("created_at", "")
            if oldest_pending_ts is None or created < oldest_pending_ts:
                oldest_pending_ts = created
                oldest_pending = f"{t['id']} ({created})"

    result: dict[str, Any] = {
        "total": total,
        "by_status": by_status,
        "by_priority": by_priority,
        "wip_current": wip_current,
        "oldest_pending": oldest_pending or None,
    }
    return json.dumps(result)


# ---------------------------------------------------------------------------
# Tool 5: task_log_event
# ---------------------------------------------------------------------------


@mcp.tool()
def task_log_event(
    task_id: str,
    event_type: str,
    details: str,
    handoff_path: str | None = None,
) -> str:
    """Append an event to a task's audit log.

    Parameters
    ----------
    task_id : str
        ID of the target task.
    event_type : str
        One of ``handoff_ref``, ``note``, ``decision``, ``deviation``.
    details : str
        Event description.
    handoff_path : str | None
        Relative path to an associated handoff file (required for
        ``handoff_ref`` type; optional otherwise).
    """
    logger.info(
        f"task_log_event: task={task_id}, type={event_type}, "
        f"details={details[:80] if details else ''}"
    )

    # --- Validate ---
    if not task_id:
        return json.dumps({"error": "Il parametro 'task_id' è obbligatorio."})
    if not details or not details.strip():
        return json.dumps({"error": "Il parametro 'details' è obbligatorio."})

    try:
        validate_event_type(event_type)
    except ValueError as e:
        return json.dumps({"error": str(e)})

    store = _get_store()
    task_dict = store.get_task(task_id)
    if task_dict is None:
        return json.dumps({"error": f"Task '{task_id}' non trovato."})

    # --- Warning for handoff_ref without handoff_path ---
    if event_type == "handoff_ref" and not handoff_path:
        logger.warning(f"handoff_ref event on {task_id} without handoff_path")

    # --- Build event ---
    ts = now_iso()
    event: dict[str, Any] = {
        "timestamp": ts,
        "type": event_type,
        "details": details.strip(),
    }
    if handoff_path:
        event["handoff_path"] = handoff_path

    # Append event
    events: list[dict[str, Any]] = task_dict.setdefault("events", [])
    events.append(event)
    event_index = len(events) - 1

    # If handoff_ref, also add to handoff_refs
    if event_type == "handoff_ref" and handoff_path:
        refs: list[str] = task_dict.setdefault("handoff_refs", [])
        if handoff_path not in refs:
            refs.append(handoff_path)

    # Update timestamp
    task_dict["updated_at"] = ts

    _save_data()

    logger.info(f"Event #{event_index} ({event_type}) added to {task_id}")

    result: dict[str, Any] = {
        "id": task_id,
        "event_index": event_index,
        "timestamp": ts,
        "event_type": event_type,
        "details": details.strip(),
    }
    return json.dumps(result)


# ---------------------------------------------------------------------------
# Tool 6: task_export
# ---------------------------------------------------------------------------


@mcp.tool()
def task_export(
    pretty: bool = True,
) -> str:
    """Export all task state as a YAML string.

    This is the only tool that exposes the complete state. Use sparingly
    (token cost).

    Parameters
    ----------
    pretty : bool
        If True, format YAML for human readability (default).
    """
    logger.info("task_export called")

    store = _get_store()
    data = store.load()

    import yaml as yaml_lib

    if pretty:
        yaml_str = yaml_lib.dump(
            data,
            default_flow_style=False,
            allow_unicode=True,
            sort_keys=False,
            indent=2,
        )
    else:
        yaml_str = yaml_lib.dump(data, allow_unicode=True, sort_keys=False)

    return yaml_str


# ---------------------------------------------------------------------------
# Tool 7: taskmanager_compress
# ---------------------------------------------------------------------------


@mcp.tool()
def taskmanager_compress(
    age_days: int | None = None,
    max_level: int = 2,
    dry_run: bool = True,
) -> str:
    """Compress task event logs based on age (hot/warm/cold).

    Applies progressive compression to tasks older than thresholds:
    - **Warm** (level 1, 8-30 days): compresses event details to max 200 chars
      using Token Juice prose compressor, preserving handoff_path, timestamp, type.
    - **Cold** (level 2, >30 days): replaces multiple events with a single period
      summary preserving only type counts and key handoff paths.

    Parameters
    ----------
    age_days : int | None
        If set, only compress tasks older than this many days.
        If None, uses default thresholds (7 for warm, 30 for cold).
    max_level : int
        Maximum compression level: 1 (warm) or 2 (cold). Default 2.
    dry_run : bool
        If True (default), only report what would be done without saving.
    """
    logger.info(
        f"taskmanager_compress: age_days={age_days}, max_level={max_level}, dry_run={dry_run}"
    )

    if max_level not in (1, 2):
        return json.dumps({"error": "max_level deve essere 1 (warm) o 2 (cold)."})

    try:
        results = compress_events(
            age_days=age_days,
            max_level=max_level,
            dry_run=dry_run,
        )
        logger.info(
            f"Compression {'dry-run' if dry_run else 'applied'}: "
            f"{results['tasks_processed']} tasks, "
            f"{results['events_compressed']} events compressed, "
            f"{results['events_summarized']} events summarized"
        )
        return json.dumps(results)
    except Exception as e:
        logger.error(f"Compression failed: {e}")
        return json.dumps({"error": f"Compressione fallita: {e}"})


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------


def main_server() -> None:
    """Start the taskmanager MCP server on stdio transport."""
    if not MCP_AVAILABLE:
        logger.error("MCP SDK not installed. Run: uv add mcp")
        import sys

        sys.exit(1)

    logger.info("Starting taskmanager MCP server on stdio...")

    # Validate that state.yaml is loadable on startup
    try:
        store = _get_store()
        store.load()
        task_count = len(store.get_tasks())
        logger.info(f"state.yaml loaded: {task_count} tasks found at {store.path}")
    except Exception as e:
        logger.error(f"Failed to load state.yaml: {e}")
        import sys

        sys.exit(1)

    mcp.run()


if __name__ == "__main__":
    main_server()
