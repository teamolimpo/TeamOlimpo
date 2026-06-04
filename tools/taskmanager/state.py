"""state.yaml backing store with file locking for the Task Manager.

Exports:
    StateStore — thread-safe YAML backing store with fcntl locking
    compress_events — compress task event logs (hot/warm/cold)
    _find_project_root — locate project root from CWD or file location
"""

from __future__ import annotations

import fcntl
import os
import shutil
import tempfile
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import yaml
from loguru import logger

from tools.common.paths import project_root, resolve_absolute

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

DEFAULT_STATE: dict[str, Any] = {
    "version": 1,
    "last_updated": "",
    "counter": {},
    "tasks": {},
}

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _find_project_root() -> Path:
    """Locate the Team Olimpo project root directory.

    Delegates to :func:`tools.common.paths.project_root`. Falls back to
    CWD-based discovery for runtime flexibility (when called outside the
    usual module hierarchy).

    Returns:
        Absolute path to the project root.

    Raises:
        FileNotFoundError: If no project root can be determined.
    """
    try:
        return project_root()
    except Exception:
        pass

    # Fallback: walk up from CWD looking for tools/config.yaml or pyproject.toml
    cwd = Path.cwd().resolve()
    for candidate in [cwd, *cwd.parents]:
        if (candidate / "tools" / "config.yaml").is_file():
            logger.debug(f"Project root found via tools/config.yaml: {candidate}")
            return candidate
    for candidate in [cwd, *cwd.parents]:
        if (candidate / "pyproject.toml").is_file():
            logger.debug(f"Project root found via pyproject.toml: {candidate}")
            return candidate

    raise FileNotFoundError(
        "Could not locate Team Olimpo project root. Run from within the project directory."
    )


# ---------------------------------------------------------------------------
# StateStore
# ---------------------------------------------------------------------------


class StateStore:
    """Thread-safe state.yaml backing store with fcntl file locking.

    Usage::

        store = StateStore()
        data = store.load()
        data["tasks"]["T-MY-001"] = task_dict
        store.save()

    The store caches data in memory; call ``reload()`` to force a disk read.
    File locking with ``fcntl.flock`` prevents concurrent writes from
    external processes.
    """

    def __init__(self, path: Path | None = None) -> None:
        """Initialize the store.

        Args:
            path: Explicit path to state.yaml. If ``None``, auto-detect
                  from ``Library/System/Poros/state.yaml`` relative to project root.
        """
        if path is not None:
            self._path = path.resolve()
        else:
            self._path = resolve_absolute("lib", "System", "Poros", "state.yaml")
        self._lock_path = self._path.with_name(f".{self._path.name}.lock")
        self._data: dict[str, Any] | None = None
        self._lock_fd: int | None = None

    # ------------------------------------------------------------------
    # Properties
    # ------------------------------------------------------------------

    @property
    def path(self) -> Path:
        """Return the path to state.yaml."""
        return self._path

    # ------------------------------------------------------------------
    # File locking
    # ------------------------------------------------------------------

    def _acquire_lock(self) -> None:
        """Acquire an exclusive file lock (fcntl.flock)."""
        self._lock_path.parent.mkdir(parents=True, exist_ok=True)
        if not self._lock_path.exists():
            self._lock_path.touch()
        fd = os.open(str(self._lock_path), os.O_RDONLY)
        fcntl.flock(fd, fcntl.LOCK_EX)
        self._lock_fd = fd
        logger.debug(f"Lock acquired on {self._lock_path}")

    def _release_lock(self) -> None:
        """Release the file lock."""
        if self._lock_fd is not None:
            fcntl.flock(self._lock_fd, fcntl.LOCK_UN)
            os.close(self._lock_fd)
            self._lock_fd = None
            logger.debug("Lock released")

    # ------------------------------------------------------------------
    # Read / Write
    # ------------------------------------------------------------------

    def load(self) -> dict[str, Any]:
        """Load state from disk into memory.

        Returns the in-memory data dict. On first call (or after
        ``reload()``), reads from the YAML file. If the file does not
        exist, creates a default empty state.

        Returns:
            The state dict with keys ``version``, ``last_updated``,
            ``counter``, ``tasks``.

        Raises:
            ValueError: If the YAML file is malformed.
        """
        if self._data is not None:
            return self._data

        if not self._path.exists():
            logger.info(f"state.yaml not found at {self._path}, creating default")
            self._data = dict(DEFAULT_STATE)
            # Write default to disk immediately so the file exists
            self._save_raw()
            return self._data

        try:
            raw = self._path.read_text(encoding="utf-8")
            parsed = yaml.safe_load(raw)
        except yaml.YAMLError as exc:
            raise ValueError(
                f"state.yaml malformed at {self._path}: {exc}. File non modificato."
            ) from exc

        if not isinstance(parsed, dict):
            raise ValueError(
                f"state.yaml at {self._path} must be a YAML dictionary, "
                f"got {type(parsed).__name__}. File non modificato."
            )

        # Ensure all top-level keys exist
        for key, default_val in DEFAULT_STATE.items():
            if key not in parsed:
                parsed[key] = default_val

        self._data = parsed
        logger.debug(f"State loaded from {self._path} ({len(parsed.get('tasks', {}))} tasks)")
        return self._data

    def _save_raw(self) -> None:
        """Atomically write ``self._data`` to the YAML file.

        Uses a temporary file + ``shutil.move`` for atomic write.
        """
        self._path.parent.mkdir(parents=True, exist_ok=True)
        fd, tmp_path = tempfile.mkstemp(
            suffix=".yaml",
            prefix=f".{self._path.name}.",
            dir=self._path.parent,
        )
        try:
            with os.fdopen(fd, "w", encoding="utf-8") as f:
                yaml.dump(
                    self._data,
                    f,
                    default_flow_style=False,
                    allow_unicode=True,
                    sort_keys=False,
                    indent=2,
                )
            shutil.move(tmp_path, str(self._path))
        except Exception:
            # Clean up temp file on failure
            p = Path(tmp_path)
            if p.exists():
                p.unlink()
            raise

    def save(self) -> None:
        """Write the current in-memory state to the YAML file with locking.

        The ``last_updated`` field is automatically set to the current
        UTC timestamp before writing.
        """
        if self._data is None:
            logger.warning("save() called with no data loaded — loading first")
            self.load()
            return

        self._acquire_lock()
        try:
            # Update timestamp
            from tools.taskmanager.models import now_iso

            self._data["last_updated"] = now_iso()
            self._save_raw()
            logger.debug(f"State saved to {self._path}")
        finally:
            self._release_lock()

    def reload(self) -> dict[str, Any]:
        """Force a full reload from disk, discarding the in-memory cache.

        Returns:
            The reloaded state dict.
        """
        self._data = None
        return self.load()

    # ------------------------------------------------------------------
    # Task-specific helpers
    # ------------------------------------------------------------------

    def get_tasks(self) -> dict[str, dict[str, Any]]:
        """Return the ``tasks`` dict (id → task dict)."""
        return self.load().setdefault("tasks", {})

    def get_task(self, task_id: str) -> dict[str, Any] | None:
        """Return a single task dict, or ``None`` if not found."""
        return self.get_tasks().get(task_id)

    def get_counter(self) -> dict[str, int]:
        """Return the area counter dict."""
        return self.load().setdefault("counter", {})

    def _ensure_loaded_for_write(self) -> dict[str, Any]:
        """Ensure data is loaded and return it for modification.

        Caller **must** call ``save()`` after modifications.
        """
        if self._data is None:
            self.load()
        return self._data  # type: ignore[return-value]

    def next_task_id(self, area: str) -> str:
        """Generate the next task ID for an *area* and increment the counter.

        Called before adding a task. Example::

            task_id = store.next_task_id("MCP")
            # Returns "T-MCP-003" if counter was at 2
            # Counter is incremented to 3

        Note:
            The counter increment is persisted when ``save()`` is called.
        """
        data = self._ensure_loaded_for_write()
        counter: dict[str, int] = data.setdefault("counter", {})
        tasks: dict[str, Any] = data.setdefault("tasks", {})
        current = counter.get(area, 0) + 1
        # Increment until we find an ID that doesn't collide with existing tasks
        # (handles explicit IDs that were set manually, e.g. T-PARENT-001)
        while f"T-{area}-{current:03d}" in tasks:
            current += 1
        counter[area] = current
        return f"T-{area}-{current:03d}"


# ---------------------------------------------------------------------------
# Compression helpers
# ---------------------------------------------------------------------------

_WARM_DAYS = 7
_COLD_DAYS = 30


def _iso_week_key(date_str: str) -> str:
    """Convert an ISO timestamp to an ISO week key like ``W21-2026``.

    Args:
        date_str: ISO 8601 timestamp string.

    Returns:
        Week key string.
    """
    dt = datetime.fromisoformat(date_str)
    iso_year, iso_week, _ = dt.isocalendar()
    return f"W{iso_week:02d}-{iso_year}"


def _days_ago(ts: str) -> float:
    """Compute how many days ago a timestamp was.

    Args:
        ts: ISO 8601 timestamp.

    Returns:
        Float days difference.
    """
    now = datetime.now(UTC)
    dt = datetime.fromisoformat(ts).replace(tzinfo=UTC) if "T" in ts else datetime.fromisoformat(ts)
    return (now - dt).total_seconds() / 86400.0


def _compress_details_with_token_juice(details: str, max_chars: int = 200) -> str:
    """Compress event details using Token Juice C2 prose compressor.

    Args:
        details: Original event details text.
        max_chars: Maximum character length for result.

    Returns:
        Compressed detail string.
    """
    try:
        from tools.token_juice.compressor import compress as tj_compress

        compressed = tj_compress(details, intensity="full")
        if len(compressed) > max_chars:
            compressed = compressed[:max_chars]
        # Return compressed only if it actually saved chars
        if len(compressed) < len(details) * 0.8:
            return compressed
        return details[:max_chars]
    except Exception:
        # Fallback: simple truncation
        return details[:max_chars]


def compress_events(
    age_days: int | None = None,
    max_level: int = 2,
    dry_run: bool = True,
    store: StateStore | None = None,
) -> dict[str, Any]:
    """Compress task event logs based on age.

    Applies hot/warm/cold compression to task events:
    - **Hot** (0-7 days, level 0): no compression
    - **Warm** (8-30 days, level 1): compress details to max 200 chars
    - **Cold** (>30 days, level 2): condense multiple events to period summary

    Args:
        age_days: If set, only compress tasks older than this many days.
                  If ``None``, uses default thresholds (7 for warm, 30 for cold).
        max_level: Maximum compression level to apply (1=warm, 2=cold).
                   Default 2.
        dry_run: If ``True``, only report what would be done without saving.
        store: Optional ``StateStore`` instance for testing.
               If ``None``, creates a new default store.

    Returns:
        Dict with keys ``tasks_processed``, ``events_compressed``,
        ``events_summarized``, ``dry_run``, ``details``.
    """
    if store is None:
        store = StateStore()
    data = store.load()
    tasks_dict: dict[str, Any] = data.setdefault("tasks", {})
    now = now_iso()

    results: dict[str, Any] = {
        "tasks_processed": 0,
        "events_compressed": 0,
        "events_summarized": 0,
        "tasks_skipped": 0,
        "dry_run": dry_run,
        "details": [],
    }

    for task_id, task_dict in tasks_dict.items():
        updated_at = task_dict.get("updated_at", "")
        if not updated_at:
            continue

        age = _days_ago(updated_at)
        events: list[dict[str, Any]] = task_dict.get("events", [])
        if not events:
            continue

        # If user explicitly set age_days, use that as the primary threshold
        if age_days is not None:
            if age <= age_days:
                continue  # not old enough
            # Determine target level based on age threshold
            if age > max(_COLD_DAYS, age_days) and max_level >= 2:
                target_level = 2
            else:
                target_level = min(max_level, 1)
        else:
            # Default behaviour: use standard thresholds
            if age <= _WARM_DAYS:
                continue  # hot — skip

            target_level = 1  # warm
            if age > _COLD_DAYS and max_level >= 2:
                target_level = 2  # cold

        current_level = task_dict.get("compression_level", 0)
        if current_level >= target_level:
            continue  # already compressed at or above target

        results["tasks_processed"] += 1

        if target_level == 1:
            # --- Warm compression: compress details per event ---
            new_events: list[dict[str, Any]] = []
            n_compressed = 0
            for ev in events:
                # Check if already a SummaryEvent type
                if "period" in ev:
                    new_events.append(ev)
                    continue
                details = ev.get("details", "")
                if len(details) > 100:
                    compressed = _compress_details_with_token_juice(details, max_chars=200)
                    ev["details"] = compressed
                    n_compressed += 1
                new_events.append(ev)

            task_dict["events"] = new_events
            task_dict["compression_level"] = 1
            results["events_compressed"] += n_compressed
            results["details"].append(
                f"{task_id}: warm-compressed {n_compressed} events (age={age:.0f}d, level=0→1)"
            )

        elif target_level == 2:
            # --- Cold compression: merge events into SummaryEvent ---
            original_count = len(events)
            type_counts: dict[str, int] = {}
            key_handoffs: list[str] = []
            period = _iso_week_key(updated_at)

            for ev in events:
                ev_type = ev.get("type", "unknown")
                type_counts[ev_type] = type_counts.get(ev_type, 0) + 1
                hp = ev.get("handoff_path")
                if hp:
                    key_handoffs.append(hp)

            type_summary_parts = [f"{cnt} {t}" for t, cnt in sorted(type_counts.items())]
            type_summary = ", ".join(type_summary_parts)

            # Replace all events with a single SummaryEvent
            task_dict["events"] = [
                {
                    "period": period,
                    "original_count": original_count,
                    "type_summary": type_summary,
                    "key_handoffs": key_handoffs,
                    "compressed_level": 2,
                }
            ]
            task_dict["compression_level"] = 2
            results["events_summarized"] += original_count
            results["details"].append(
                f"{task_id}: cold-summarized {original_count} events "
                f"into period={period} (age={age:.0f}d)"
            )

    if not dry_run:
        data["last_updated"] = now
        store.save()

    return results


def now_iso() -> str:
    """Return current UTC timestamp in ISO 8601 format."""
    from tools.taskmanager.models import now_iso as _now_iso

    return _now_iso()
