"""Data models for Session Memory MCP server.

Provides enums for status/type classification, dataclasses for serialization,
and helper functions for ID generation and timestamps.

Exports:
    SessionStatus, ObservationType, EntityType — enum classifiers
    SessionData, ObservationData, EntityData, SummaryData — dataclasses
    generate_session_id, now_iso — helper functions
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from datetime import UTC, datetime
from enum import StrEnum
from typing import Any

# ---------------------------------------------------------------------------
# Enums
# ---------------------------------------------------------------------------


class SessionStatus(StrEnum):
    """Lifecycle status of a Hermes session."""

    ACTIVE = "active"
    INTERRUPTED = "interrupted"
    COMPLETED = "completed"


class ObservationType(StrEnum):
    """Classification of a single observation in the timeline."""

    DECISION = "decision"
    DELEGATION = "delegation"
    RESULT = "result"
    NOTE = "note"
    HANDOFF = "handoff"
    USER_MESSAGE = "user_message"
    SYSTEM = "system"


class EntityType(StrEnum):
    """Classification of a named entity."""

    PROJECT = "project"
    AGENT = "agent"
    CONCEPT = "concept"
    PERSON = "person"
    TECHNOLOGY = "technology"
    TASK = "task"


# ---------------------------------------------------------------------------
# Dataclasses
# ---------------------------------------------------------------------------


@dataclass
class SessionData:
    """A Hermes session — one row in the ``sessions`` table."""

    id: str
    status: str = SessionStatus.ACTIVE.value
    topic: str = ""
    summary: str = ""
    agent: str = "Hermes"
    task_ids: list[str] = field(default_factory=list)
    token_budget: int = 2000
    token_discovery: int = 0
    token_read: int = 0
    started_at: str = ""
    ended_at: str | None = None
    updated_at: str = ""
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        """Serialize to a storage-ready dict (JSON fields as strings)."""
        return {
            "id": self.id,
            "status": self.status,
            "topic": self.topic,
            "summary": self.summary,
            "agent": self.agent,
            "task_ids": json.dumps(self.task_ids),
            "token_budget": self.token_budget,
            "token_discovery": self.token_discovery,
            "token_read": self.token_read,
            "started_at": self.started_at,
            "ended_at": self.ended_at,
            "updated_at": self.updated_at,
            "metadata": json.dumps(self.metadata),
        }

    def to_json_dict(self) -> dict[str, Any]:
        """Serialize to a JSON-friendly dict (lists/dicts, not strings)."""
        return {
            "id": self.id,
            "status": self.status,
            "topic": self.topic,
            "summary": self.summary,
            "agent": self.agent,
            "task_ids": self.task_ids,
            "token_budget": self.token_budget,
            "token_discovery": self.token_discovery,
            "token_read": self.token_read,
            "started_at": self.started_at,
            "ended_at": self.ended_at,
            "updated_at": self.updated_at,
            "metadata": self.metadata,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> SessionData:
        """Deserialize from a storage dict (JSON fields as strings)."""
        task_ids_raw = data.get("task_ids", "[]")
        if isinstance(task_ids_raw, str):
            task_ids = json.loads(task_ids_raw)
        else:
            task_ids = task_ids_raw or []

        metadata_raw = data.get("metadata", "{}")
        if isinstance(metadata_raw, str):
            metadata = json.loads(metadata_raw)
        else:
            metadata = metadata_raw or {}

        return cls(
            id=data["id"],
            status=data.get("status", SessionStatus.ACTIVE.value),
            topic=data.get("topic", ""),
            summary=data.get("summary", ""),
            agent=data.get("agent", "Hermes"),
            task_ids=task_ids,
            token_budget=data.get("token_budget", 2000),
            token_discovery=data.get("token_discovery", 0),
            token_read=data.get("token_read", 0),
            started_at=data.get("started_at", ""),
            ended_at=data.get("ended_at"),
            updated_at=data.get("updated_at", ""),
            metadata=metadata,
        )


@dataclass
class ObservationData:
    """A single observation — one row in the ``observations`` table."""

    id: int | None = None
    session_id: str = ""
    parent_id: int | None = None
    type: str = ObservationType.NOTE.value
    agent: str = "Hermes"
    content: str = ""
    tokens_discovery: int = 0
    tokens_read: int = 0
    token_savings: float = 0.0
    entities: list[str] = field(default_factory=list)
    handoff_path: str | None = None
    task_ref: str | None = None
    created_at: str = ""

    def to_dict(self) -> dict[str, Any]:
        """Serialize to a storage-ready dict (JSON fields as strings)."""
        d: dict[str, Any] = {
            "session_id": self.session_id,
            "parent_id": self.parent_id,
            "type": self.type,
            "agent": self.agent,
            "content": self.content,
            "tokens_discovery": self.tokens_discovery,
            "tokens_read": self.tokens_read,
            "entities": json.dumps(self.entities),
            "created_at": self.created_at,
        }
        if self.handoff_path is not None:
            d["handoff_path"] = self.handoff_path
        if self.task_ref is not None:
            d["task_ref"] = self.task_ref
        return d

    def to_json_dict(self, include_token_savings: bool = False) -> dict[str, Any]:
        """Serialize to a JSON-friendly dict."""
        d: dict[str, Any] = {
            "id": self.id,
            "session_id": self.session_id,
            "parent_id": self.parent_id,
            "type": self.type,
            "agent": self.agent,
            "content": self.content,
            "tokens_discovery": self.tokens_discovery,
            "tokens_read": self.tokens_read,
            "entities": self.entities,
            "handoff_path": self.handoff_path,
            "task_ref": self.task_ref,
            "created_at": self.created_at,
        }
        if include_token_savings:
            d["token_savings"] = self.token_savings
        return d

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> ObservationData:
        """Deserialize from a storage dict."""
        entities_raw = data.get("entities", "[]")
        if isinstance(entities_raw, str):
            entities = json.loads(entities_raw)
        else:
            entities = entities_raw or []

        return cls(
            id=data.get("id"),
            session_id=data.get("session_id", ""),
            parent_id=data.get("parent_id"),
            type=data.get("type", ObservationType.NOTE.value),
            agent=data.get("agent", "Hermes"),
            content=data.get("content", ""),
            tokens_discovery=data.get("tokens_discovery", 0),
            tokens_read=data.get("tokens_read", 0),
            token_savings=data.get("token_savings", 0.0),
            entities=entities,
            handoff_path=data.get("handoff_path"),
            task_ref=data.get("task_ref"),
            created_at=data.get("created_at", ""),
        )


@dataclass
class EntityData:
    """A named entity — one row in the ``entities`` table."""

    id: int | None = None
    name: str = ""
    entity_type: str = EntityType.CONCEPT.value
    metadata: dict[str, Any] = field(default_factory=dict)
    created_at: str = ""
    updated_at: str = ""

    def to_dict(self) -> dict[str, Any]:
        """Serialize to a storage-ready dict."""
        return {
            "name": self.name,
            "entity_type": self.entity_type,
            "metadata": json.dumps(self.metadata),
            "created_at": self.created_at,
            "updated_at": self.updated_at,
        }

    def to_json_dict(self) -> dict[str, Any]:
        """Serialize to a JSON-friendly dict."""
        return {
            "id": self.id,
            "name": self.name,
            "entity_type": self.entity_type,
            "metadata": self.metadata,
            "created_at": self.created_at,
            "updated_at": self.updated_at,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> EntityData:
        """Deserialize from a storage dict."""
        metadata_raw = data.get("metadata", "{}")
        if isinstance(metadata_raw, str):
            metadata = json.loads(metadata_raw)
        else:
            metadata = metadata_raw or {}

        return cls(
            id=data.get("id"),
            name=data.get("name", ""),
            entity_type=data.get("entity_type", EntityType.CONCEPT.value),
            metadata=metadata,
            created_at=data.get("created_at", ""),
            updated_at=data.get("updated_at", ""),
        )


@dataclass
class SummaryData:
    """A compressed summary — one row in the ``summaries`` table."""

    id: int | None = None
    session_id: str = ""
    level: int = 1
    parent_id: int | None = None
    content: str = ""
    token_count: int = 0
    created_at: str = ""

    def to_dict(self) -> dict[str, Any]:
        """Serialize to a storage-ready dict."""
        return {
            "session_id": self.session_id,
            "level": self.level,
            "parent_id": self.parent_id,
            "content": self.content,
            "token_count": self.token_count,
            "created_at": self.created_at,
        }

    def to_json_dict(self) -> dict[str, Any]:
        """Serialize to a JSON-friendly dict."""
        return {
            "id": self.id,
            "session_id": self.session_id,
            "level": self.level,
            "parent_id": self.parent_id,
            "content": self.content,
            "token_count": self.token_count,
            "created_at": self.created_at,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> SummaryData:
        """Deserialize from a storage dict."""
        return cls(
            id=data.get("id"),
            session_id=data.get("session_id", ""),
            level=data.get("level", 1),
            parent_id=data.get("parent_id"),
            content=data.get("content", ""),
            token_count=data.get("token_count", 0),
            created_at=data.get("created_at", ""),
        )


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def generate_session_id() -> str:
    """Generate a unique session ID in format ``ses_YYYYMMDD_HHMMSS_ffffff``.

    Includes microseconds to guarantee uniqueness within the same second.

    Returns:
        Session ID string (e.g. ``ses_20260523_143000_123456``).
    """
    return datetime.now(UTC).strftime("ses_%Y%m%d_%H%M%S_%f")


def now_iso() -> str:
    """Return current UTC timestamp in ISO 8601 format with microseconds.

    Returns:
        ISO 8601 timestamp string (e.g. ``2026-05-23T14:30:00.123456``).
    """
    return datetime.now(UTC).strftime("%Y-%m-%dT%H:%M:%S.%f")


def compute_token_savings(tokens_discovery: int, tokens_read: int) -> float:
    """Compute the token savings ratio.

    Args:
        tokens_discovery: Token count for generating the observation.
        tokens_read: Token count for reading the observation.

    Returns:
        Savings ratio (0.0–1.0), or 0.0 if tokens_discovery is 0.
    """
    if tokens_discovery > 0:
        return (tokens_discovery - tokens_read) * 1.0 / tokens_discovery
    return 0.0
