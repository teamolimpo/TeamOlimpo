"""Task data model, state machine, and validation for Task Manager MCP server.

Exports:
    Task, TaskEvent — dataclasses for task representation
    StateMachine — validates status transitions
    extract_area_from_description / extract_area_from_task_id — ID helpers
    now_iso — ISO 8601 timestamp helper
    VALID_STATUSES, VALID_PRIORITIES, VALID_EVENT_TYPES — constants
"""

from __future__ import annotations

import re
from dataclasses import asdict, dataclass, field
from datetime import UTC, datetime
from typing import Any

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

VALID_STATUSES = [
    "pending",
    "in_progress",
    "completed",
    "cancelled",
    "blocked",
    "standby",
]
VALID_PRIORITIES = ["low", "medium", "high", "critical"]
VALID_EVENT_TYPES = ["handoff_ref", "note", "decision", "deviation"]
INITIAL_STATUSES = ["pending", "standby"]

# Regex for task IDs: T-<AREA>-<NNN>
# AREA: 2-15 chars, uppercase, with hyphens allowed (supports existing
#       IDs like T-MCP-ROADMAP-001)
# NNN: 3 digits
TASK_ID_REGEX = re.compile(r"^T-[A-Z][A-Z0-9-]{1,14}-\d{3}$")

# Regex for body task notation: [T-ID] Description STATUS_MARKER
# TASK_NOTATION_REGEX = re.compile(r"\[([^\]]+)\]\s*(.+?)(?:\s+(✅|❌|⏸|\[IN CORSO\]))?$")
TASK_NOTATION_REGEX = re.compile(
    r"\[([A-Z][A-Z0-9-]+)\]\s*(.+?)(?:\s+(✅.*|❌.*|⏸.*|\[IN CORSO\]))?$",
    re.MULTILINE,
)

# Status mapping for Scratchpad body notation
STATUS_FROM_MARKER: dict[str, str] = {
    "✅": "completed",
    "❌": "cancelled",
    "⏸": "standby",
    "[IN CORSO]": "in_progress",
}

# Status mapping for Scratchpad frontmatter values (Italian → English)
FRONTMATTER_STATUS_MAP: dict[str, str] = {
    "completed": "completed",
    "in corso": "in_progress",
    "in_progress": "in_progress",
    "standby": "standby",
    "cancelled": "cancelled",
    "cancellato": "cancelled",
    "pending": "pending",
}

# ---------------------------------------------------------------------------
# Dataclasses
# ---------------------------------------------------------------------------


@dataclass
class TaskEvent:
    """A single event in a task's audit log (hot level)."""

    timestamp: str
    type: str
    details: str
    handoff_path: str | None = None


@dataclass
class CompressedEvent:
    """A warm-compressed event (max ~200 char details, preserved fields)."""

    timestamp: str
    type: str
    details: str  # compressed to max ~200 chars
    handoff_path: str | None = None
    compressed_level: int = 1  # 1 = warm


@dataclass
class SummaryEvent:
    """A cold-compressed period summary replacing multiple events."""

    period: str  # e.g. "W21-2026" (ISO week)
    original_count: int  # how many events were merged
    type_summary: str  # e.g. "3 completed, 1 handoff_ref"
    key_handoffs: list[str]  # only handoff paths, nothing else
    compressed_level: int = 2  # 2 = cold


# Union type for all event kinds
Event = TaskEvent | CompressedEvent | SummaryEvent


@dataclass
class Task:
    """A task in the Team Olimpo workflow."""

    id: str
    description: str
    status: str
    priority: str
    owner: str
    created_at: str
    updated_at: str
    tags: list[str] = field(default_factory=list)
    parent: str | None = None
    handoff_refs: list[str] = field(default_factory=list)
    events: list[Event] = field(default_factory=list)
    compression_level: int = 0  # 0=hot, 1=warm, 2=cold

    def to_dict(self, include_events: bool = False) -> dict[str, Any]:
        """Serialize to dict for JSON/YAML output.

        Args:
            include_events: If True, include full events list.
                           If False, include only event_count.
        """
        result: dict[str, Any] = {
            "id": self.id,
            "description": self.description,
            "status": self.status,
            "priority": self.priority,
            "owner": self.owner,
            "created_at": self.created_at,
            "updated_at": self.updated_at,
            "tags": self.tags,
            "parent": self.parent,
            "handoff_refs": self.handoff_refs,
            "compression_level": self.compression_level,
        }
        if include_events:
            result["events"] = [asdict(e) for e in self.events]
            result["event_count"] = len(self.events)
        else:
            result["event_count"] = len(self.events)
        return result

    def to_storage_dict(self) -> dict[str, Any]:
        """Serialize to full dict for YAML storage (always includes events)."""
        result: dict[str, Any] = {
            "id": self.id,
            "description": self.description,
            "status": self.status,
            "priority": self.priority,
            "owner": self.owner,
            "created_at": self.created_at,
            "updated_at": self.updated_at,
            "tags": self.tags,
            "parent": self.parent,
            "handoff_refs": self.handoff_refs,
            "events": [asdict(e) for e in self.events],
        }
        if self.compression_level > 0:
            result["compression_level"] = self.compression_level
        return result

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> Task:
        """Deserialize from a storage dict."""
        events_raw = data.get("events", [])
        events: list[Event] = []
        for e in events_raw:
            if "period" in e:
                # SummaryEvent (cold)
                events.append(
                    SummaryEvent(
                        period=e["period"],
                        original_count=e.get("original_count", 0),
                        type_summary=e.get("type_summary", ""),
                        key_handoffs=e.get("key_handoffs", []),
                        compressed_level=e.get("compressed_level", 2),
                    )
                )
            else:
                # TaskEvent (hot) or CompressedEvent (warm)
                events.append(
                    TaskEvent(
                        timestamp=e["timestamp"],
                        type=e["type"],
                        details=e["details"],
                        handoff_path=e.get("handoff_path"),
                    )
                )
        return cls(
            id=data["id"],
            description=data["description"],
            status=data["status"],
            priority=data.get("priority", "medium"),
            owner=data.get("owner", "Hermes"),
            created_at=data.get("created_at", now_iso()),
            updated_at=data.get("updated_at", now_iso()),
            tags=data.get("tags", []),
            parent=data.get("parent"),
            handoff_refs=data.get("handoff_refs", []),
            events=events,
            compression_level=data.get("compression_level", 0),
        )


# ---------------------------------------------------------------------------
# State Machine
# ---------------------------------------------------------------------------


class StateMachine:
    """Validates task status transitions.

    Transition matrix (from -> to)::

        | From - To    | pending | in_progress | completed | cancelled | blocked | standby |
        |--------------|---------|-------------|-----------|-----------|---------|---------|
        | pending      | -       | X           | X         | X         | X       | X       |
        | in_progress  | -       | -           | X         | X         | X       | -       |
        | completed    | -       | -           | -         | -         | -       | -       |
        | cancelled    | -       | -           | -         | -         | -       | -       |
        | blocked      | -       | X           | X         | X         | -       | -       |
        | standby      | X       | X           | X         | X         | X       | -       |

    where ``X`` = valid transition and ``-`` = invalid (or no-op).
    ``completed`` and ``cancelled`` are **terminal** states.

    ``completed`` and ``cancelled`` are **terminal** states — no outgoing transitions.
    """

    _TRANSITIONS: dict[str, set[str]] = {
        "pending": {"in_progress", "completed", "cancelled", "blocked", "standby"},
        "in_progress": {"completed", "cancelled", "blocked"},
        "completed": set(),  # terminal
        "cancelled": set(),  # terminal
        "blocked": {"in_progress", "completed", "cancelled"},
        "standby": {"pending", "in_progress", "completed", "cancelled", "blocked"},
    }

    @classmethod
    def is_valid_transition(cls, from_status: str, to_status: str) -> bool:
        """Check if a status transition is allowed."""
        if from_status not in cls._TRANSITIONS:
            return False
        return to_status in cls._TRANSITIONS[from_status]

    @classmethod
    def valid_transitions(cls, from_status: str) -> list[str]:
        """Return list of valid target statuses from a given status."""
        return sorted(cls._TRANSITIONS.get(from_status, []))

    @classmethod
    def validate_transition(cls, from_status: str, to_status: str) -> None:
        """Validate a transition. Raises ``ValueError`` if invalid.

        Args:
            from_status: Current status.
            to_status: Desired new status.

        Raises:
            ValueError: With a descriptive message if the transition is invalid.
        """
        if from_status == to_status:
            return  # no-op, allowed silently
        if not cls.is_valid_transition(from_status, to_status):
            valid = cls.valid_transitions(from_status)
            if not valid:
                raise ValueError(
                    f"Transizione '{from_status}' → '{to_status}' non valida. "
                    f"'{from_status}' è uno stato terminale. "
                    f"Transizioni consentite: (nessuna)."
                )
            raise ValueError(
                f"Transizione '{from_status}' → '{to_status}' non valida. "
                f"Transizioni consentite da '{from_status}': "
                f"{', '.join(valid)}."
            )


# ---------------------------------------------------------------------------
# ID Helpers
# ---------------------------------------------------------------------------


def extract_area_from_description(description: str) -> str:
    """Extract an area code from a task description for ID generation.

    Strategy:
    1. Look for acronyms in ALL CAPS (e.g. ``MCP``, ``API``, ``CLI``).
    2. If none, take the first alphabetic word and uppercase it.
    3. Fall back to ``TASK``.

    Returns:
        Area string (max 10 characters, uppercase).
    """
    words = description.split()
    # 1. Look for acronyms in ALL CAPS (2+ chars)
    for w in words:
        w_clean = w.strip("()[]{}:;,.")
        if w_clean.isupper() and len(w_clean) >= 2 and w_clean.isalpha():
            return w_clean[:10]
    # 2. First meaningful word
    for w in words:
        w_clean = w.strip("()[]{}:;,.")
        if len(w_clean) >= 2 and w_clean.isalpha():
            return w_clean[:10].upper()
    return "TASK"


def extract_area_from_task_id(task_id: str) -> str:
    """Extract the area portion from a task ID.

    Example: ``T-MCP-ROADMAP-001`` → ``MCP-ROADMAP``.
    """
    m = re.match(r"^T-(.+)-(\d{3})$", task_id)
    if m:
        return m.group(1)
    return "TASK"


def validate_task_id(task_id: str) -> bool:
    """Check if a task ID matches the ``T-<AREA>-<NNN>`` format."""
    return bool(TASK_ID_REGEX.match(task_id))


def now_iso() -> str:
    """Return current UTC timestamp in ISO 8601 format."""
    return datetime.now(UTC).strftime("%Y-%m-%dT%H:%M:%S")


def truncate_description(description: str, max_len: int = 150) -> tuple[str, bool]:
    """Truncate description to max_len characters.

    Returns:
        Tuple of (truncated_description, was_truncated).
    """
    if len(description) <= max_len:
        return description, False
    return description[:max_len], True


# ---------------------------------------------------------------------------
# Validation helpers
# ---------------------------------------------------------------------------


def validate_priority(priority: str) -> None:
    """Raise ``ValueError`` if priority is not valid."""
    if priority not in VALID_PRIORITIES:
        raise ValueError(
            f"priority deve essere uno di: {', '.join(VALID_PRIORITIES)}. Ricevuto: '{priority}'."
        )


def validate_status(status: str) -> None:
    """Raise ``ValueError`` if status is not valid."""
    if status not in VALID_STATUSES:
        raise ValueError(
            f"status deve essere uno di: {', '.join(VALID_STATUSES)}. Ricevuto: '{status}'."
        )


def validate_event_type(event_type: str) -> None:
    """Raise ``ValueError`` if event_type is not valid."""
    if event_type not in VALID_EVENT_TYPES:
        raise ValueError(
            f"event_type deve essere uno di: {', '.join(VALID_EVENT_TYPES)}. "
            f"Ricevuto: '{event_type}'."
        )
