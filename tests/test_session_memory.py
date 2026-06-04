"""Tests for Session Memory MCP server.

Covers:
- ``store.py`` — SQLite CRUD, FTS5 search, entity linking
- ``models.py`` — dataclass serialization, enum validation
- ``server.py`` — all 5 tools via CliRunner (smoke tests)
"""

from __future__ import annotations

import tempfile
from pathlib import Path

import pytest

from tools.session_memory.models import (
    EntityData,
    EntityType,
    ObservationData,
    ObservationType,
    SessionData,
    SessionStatus,
    SummaryData,
    compute_token_savings,
    generate_session_id,
    now_iso,
)

# =========================================================================
# Helpers
# =========================================================================


@pytest.fixture
def tmp_db() -> Path:
    """Fixture: create a temporary SQLite database."""
    with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as f:
        db_path = Path(f.name)
    yield db_path
    if db_path.exists():
        db_path.unlink()


@pytest.fixture
def store(tmp_db: Path):
    """Fixture: create a SessionStore with a temporary DB."""
    from tools.session_memory.store import SessionStore

    s = SessionStore(db_path=tmp_db)
    yield s
    s.close()


# =========================================================================
# Test: models.py
# =========================================================================


class TestModels:
    """Dataclass serialization and enum validation."""

    def test_session_status_enum(self):
        assert SessionStatus.ACTIVE.value == "active"
        assert SessionStatus.INTERRUPTED.value == "interrupted"
        assert SessionStatus.COMPLETED.value == "completed"

    def test_observation_type_enum(self):
        assert ObservationType.DECISION.value == "decision"
        assert ObservationType.DELEGATION.value == "delegation"
        assert ObservationType.RESULT.value == "result"
        assert ObservationType.NOTE.value == "note"
        assert ObservationType.HANDOFF.value == "handoff"
        assert ObservationType.USER_MESSAGE.value == "user_message"
        assert ObservationType.SYSTEM.value == "system"

    def test_entity_type_enum(self):
        assert EntityType.PROJECT.value == "project"
        assert EntityType.AGENT.value == "agent"
        assert EntityType.CONCEPT.value == "concept"
        assert EntityType.PERSON.value == "person"
        assert EntityType.TECHNOLOGY.value == "technology"
        assert EntityType.TASK.value == "task"

    def test_session_data_roundtrip(self):
        data = SessionData(
            id="ses_20260523_143000",
            status="active",
            topic="Test topic",
            agent="Poros",
            task_ids=["T-FASE-007"],
            token_budget=2000,
            token_discovery=100,
            token_read=10,
            started_at=now_iso(),
            updated_at=now_iso(),
        )
        d = data.to_dict()
        restored = SessionData.from_dict(d)
        assert restored.id == data.id
        assert restored.topic == data.topic
        assert restored.task_ids == data.task_ids
        assert restored.metadata == {}

    def test_session_data_json_dict(self):
        data = SessionData(
            id="ses_test",
            topic="Test",
            task_ids=["T-001"],
            metadata={"key": "val"},
        )
        jd = data.to_json_dict()
        assert jd["id"] == "ses_test"
        assert jd["task_ids"] == ["T-001"]
        assert jd["metadata"]["key"] == "val"

    def test_observation_data_roundtrip(self):
        data = ObservationData(
            session_id="ses_test",
            type="decision",
            content="Test observation",
            agent="Poros",
            entities=["entity1", "entity2"],
            handoff_path="Library/Handoff/test.md",
            task_ref="T-001",
            tokens_discovery=100,
            tokens_read=20,
            created_at=now_iso(),
        )
        d = data.to_dict()
        restored = ObservationData.from_dict(d)
        assert restored.content == data.content
        assert restored.entities == data.entities
        assert restored.handoff_path == data.handoff_path
        assert restored.task_ref == data.task_ref

    def test_entity_data_roundtrip(self):
        data = EntityData(
            name="test-entity",
            entity_type="technology",
            metadata={"version": "1.0"},
            created_at=now_iso(),
            updated_at=now_iso(),
        )
        d = data.to_dict()
        restored = EntityData.from_dict(d)
        assert restored.name == data.name
        assert restored.entity_type == data.entity_type
        assert restored.metadata["version"] == "1.0"

    def test_summary_data_roundtrip(self):
        data = SummaryData(
            session_id="ses_test",
            level=1,
            content="Summary text",
            token_count=50,
            created_at=now_iso(),
        )
        d = data.to_dict()
        restored = SummaryData.from_dict(d)
        assert restored.content == data.content
        assert restored.token_count == data.token_count

    def test_generate_session_id_format(self):
        sid = generate_session_id()
        assert sid.startswith("ses_")
        # ses_YYYYMMDD_HHMMSS_ffffff = 4+8+1+6+1+6 = 26
        assert len(sid) == 26
        parts = sid.split("_")
        assert len(parts) == 4  # ses, YYYYMMDD, HHMMSS, ffffff
        assert len(parts[1]) == 8  # YYYYMMDD
        assert len(parts[2]) == 6  # HHMMSS
        assert len(parts[3]) == 6  # microseconds (ffffff)

    def test_now_iso_format(self):
        ts = now_iso()
        assert "T" in ts
        assert "." in ts  # microsecond precision
        assert len(ts) >= 26  # 2026-05-23T14:30:00.123456

    def test_compute_token_savings(self):
        assert compute_token_savings(100, 10) == 0.9
        assert compute_token_savings(0, 100) == 0.0
        assert compute_token_savings(100, 100) == 0.0
        assert compute_token_savings(200, 50) == 0.75

    def test_observation_data_from_dict_entities_list(self):
        """Ensure from_dict handles entities as list (already parsed)."""
        data = ObservationData.from_dict(
            {
                "session_id": "ses_test",
                "type": "note",
                "content": "test",
                "entities": ["a", "b"],
            }
        )
        assert data.entities == ["a", "b"]

    def test_session_data_from_dict_parsed_objects(self):
        """Ensure from_dict handles already-parsed task_ids and metadata."""
        data = SessionData.from_dict(
            {
                "id": "ses_test",
                "status": "active",
                "topic": "test",
                "task_ids": ["T-001"],
                "metadata": {"key": "val"},
            }
        )
        assert data.task_ids == ["T-001"]
        assert data.metadata == {"key": "val"}


# =========================================================================
# Test: store.py — Sessions CRUD
# =========================================================================


class TestStoreSessions:
    """Session CRUD operations."""

    def test_create_session(self, store):
        result = store.create_session(topic="Test Session", task_ids=["T-001"])
        assert result["id"].startswith("ses_")
        assert result["status"] == "active"
        assert result["topic"] == "Test Session"
        assert result["task_ids"] == ["T-001"]
        assert result["token_budget"] == 2000

    def test_create_session_custom_budget(self, store):
        result = store.create_session(topic="Budget Test", token_budget=5000)
        assert result["token_budget"] == 5000

    def test_get_session_exists(self, store):
        created = store.create_session(topic="Get Test")
        fetched = store.get_session(created["id"])
        assert fetched is not None
        assert fetched["id"] == created["id"]
        assert fetched["topic"] == "Get Test"

    def test_get_session_not_found(self, store):
        result = store.get_session("ses_nonexistent")
        assert result is None

    def test_update_session(self, store):
        created = store.create_session(topic="Update Test")
        sid = created["id"]

        result = store.update_session(sid, topic="Updated Topic")
        assert result is True

        fetched = store.get_session(sid)
        assert fetched["topic"] == "Updated Topic"

    def test_update_session_not_found(self, store):
        result = store.update_session("ses_nonexistent", topic="Nope")
        assert result is False

    def test_get_active_session(self, store):
        # Create two sessions — most recent active should be returned
        store.create_session(topic="First")
        s2 = store.create_session(topic="Second")

        active = store.get_active_session()
        assert active is not None
        # The most recent active session is returned
        assert active["id"] == s2["id"]

    def test_get_active_session_none(self, store):
        active = store.get_active_session()
        assert active is None

    def test_get_active_session_skips_completed(self, store):
        s1 = store.create_session(topic="Active")
        s2 = store.create_session(topic="To Complete")
        store.update_session(s2["id"], status="completed")

        active = store.get_active_session()
        assert active is not None
        # Should find s1 (active) because s2 is completed
        assert active["id"] == s1["id"]

    def test_get_session_metrics(self, store):
        session = store.create_session(topic="Metrics Test")
        sid = session["id"]

        # No observations yet
        metrics = store.get_session_metrics(sid)
        assert metrics["observations_count"] == 0
        assert metrics["total_tokens_discovery"] == 0
        assert metrics["entity_count"] == 0

        # Add some observations
        store.add_observation(
            sid, type="note", content="Obs 1", tokens_discovery=100, tokens_read=10
        )
        store.add_observation(
            sid, type="decision", content="Obs 2", tokens_discovery=200, tokens_read=20
        )

        metrics = store.get_session_metrics(sid)
        assert metrics["observations_count"] == 2
        assert metrics["total_tokens_discovery"] == 300
        assert metrics["total_tokens_read"] == 30


# =========================================================================
# Test: store.py — Observations CRUD
# =========================================================================


class TestStoreObservations:
    """Observation CRUD operations."""

    def test_add_observation(self, store):
        session = store.create_session(topic="Obs Test")
        sid = session["id"]

        obs_id = store.add_observation(
            session_id=sid,
            type="decision",
            content="Test decision",
            agent="Poros",
            entities=["entity1"],
            handoff_path="Library/test.md",
            task_ref="T-001",
            tokens_discovery=100,
            tokens_read=10,
        )
        assert isinstance(obs_id, int)
        assert obs_id > 0

    def test_get_observation(self, store):
        session = store.create_session(topic="Obs Get")
        sid = session["id"]

        obs_id = store.add_observation(
            session_id=sid,
            type="note",
            content="Test note",
        )
        fetched = store.get_observation(obs_id)
        assert fetched is not None
        assert fetched["id"] == obs_id
        assert fetched["content"] == "Test note"
        assert fetched["session_id"] == sid

    def test_get_observation_not_found(self, store):
        result = store.get_observation(99999)
        assert result is None

    def test_get_observations(self, store):
        session = store.create_session(topic="Obs List")
        sid = session["id"]

        for i in range(3):
            store.add_observation(sid, type="note", content=f"Note {i}")

        obs_list = store.get_observations(sid, limit=10)
        assert len(obs_list) == 3

    def test_get_observations_with_types_filter(self, store):
        session = store.create_session(topic="Filter Obs")
        sid = session["id"]

        store.add_observation(sid, type="note", content="A note")
        store.add_observation(sid, type="decision", content="A decision")

        notes = store.get_observations(sid, types=["note"])
        assert len(notes) == 1
        assert notes[0]["type"] == "note"

    def test_get_latest_observations(self, store):
        session = store.create_session(topic="Latest Obs")
        sid = session["id"]

        for i in range(10):
            store.add_observation(sid, type="note", content=f"Note {i}")

        latest = store.get_latest_observations(sid, limit=3)
        assert len(latest) == 3
        # Should be newest first (Note 9, Note 8, Note 7)
        assert "Note 9" in latest[0]["content"]


# =========================================================================
# Test: store.py — Entities
# =========================================================================


class TestStoreEntities:
    """Entity CRUD and linking."""

    def test_get_or_create_entity_new(self, store):
        eid = store.get_or_create_entity("TestEntity", entity_type="concept")
        assert isinstance(eid, int)
        assert eid > 0

    def test_get_or_create_entity_existing(self, store):
        eid1 = store.get_or_create_entity("UniqueEntity")
        eid2 = store.get_or_create_entity("UniqueEntity")
        assert eid1 == eid2

    def test_get_or_create_entity_normalises(self, store):
        eid1 = store.get_or_create_entity("UpperCase")
        eid2 = store.get_or_create_entity("uppercase")
        assert eid1 == eid2

    def test_link_entity_to_observation(self, store):
        session = store.create_session(topic="Link Test")
        sid = session["id"]

        obs_id = store.add_observation(sid, type="note", content="Linked obs")
        eid = store.get_or_create_entity("LinkedEntity")

        store.link_entity_to_observation(obs_id, eid)
        # Should not raise

    def test_link_entity_duplicate(self, store):
        session = store.create_session(topic="Dup Link")
        sid = session["id"]

        obs_id = store.add_observation(sid, type="note", content="Dup")
        eid = store.get_or_create_entity("DupEntity")

        store.link_entity_to_observation(obs_id, eid)
        store.link_entity_to_observation(obs_id, eid)  # Should be no-op


# =========================================================================
# Test: store.py — FTS5 Search
# =========================================================================


class TestStoreSearch:
    """FTS5 search across observations."""

    def test_search_basic(self, store):
        session = store.create_session(topic="Search Test")
        sid = session["id"]

        store.add_observation(sid, type="note", content="SQLite is a database engine")
        store.add_observation(sid, type="decision", content="We chose SQLite for session storage")
        store.add_observation(sid, type="note", content="Python is a programming language")

        results = store.search_observations("SQLite")
        assert len(results) >= 2

    def test_search_no_results(self, store):
        results = store.search_observations("nonexistentterm12345")
        assert results == []

    def test_search_with_entity_filter(self, store):
        session = store.create_session(topic="Entity Filter")
        sid = session["id"]

        obs_id = store.add_observation(
            sid,
            type="note",
            content="Testing with SQLite",
            entities=["sqlite"],
        )
        eid = store.get_or_create_entity("sqlite", entity_type="technology")
        store.link_entity_to_observation(obs_id, eid)

        store.add_observation(sid, type="note", content="Testing with Python")

        results = store.search_observations("Testing", entity="sqlite")
        assert len(results) == 1
        assert results[0]["id"] == obs_id

    def test_search_with_type_filter(self, store):
        session = store.create_session(topic="Type Filter")
        sid = session["id"]

        store.add_observation(sid, type="decision", content="Decided to use SQLite")
        store.add_observation(sid, type="note", content="SQLite notes")

        results = store.search_observations("SQLite", type="decision")
        assert len(results) == 1
        assert results[0]["type"] == "decision"

    def test_search_with_session_filter(self, store):
        s1 = store.create_session(topic="Session A")
        s2 = store.create_session(topic="Session B")

        store.add_observation(s1["id"], type="note", content="Content in session A")
        store.add_observation(s2["id"], type="note", content="Content in session B")

        results = store.search_observations("Content", session_id=s1["id"])
        assert len(results) == 1
        assert results[0]["session_id"] == s1["id"]

    def test_search_max_results(self, store):
        session = store.create_session(topic="Max Results")
        sid = session["id"]

        for i in range(5):
            store.add_observation(sid, type="note", content=f"Searchable content {i}")

        results = store.search_observations("Searchable", max_results=2)
        assert len(results) == 2


# =========================================================================
# Test: store.py — Summaries
# =========================================================================


class TestStoreSummaries:
    """Summary CRUD operations."""

    def test_add_summary(self, store):
        session = store.create_session(topic="Summary Test")
        sid = session["id"]

        sum_id = store.add_summary(sid, level=1, content="Test summary", token_count=50)
        assert isinstance(sum_id, int)
        assert sum_id > 0

    def test_get_summaries(self, store):
        session = store.create_session(topic="Summary List")
        sid = session["id"]

        store.add_summary(sid, level=1, content="Summary 1")
        store.add_summary(sid, level=2, content="Summary 2")

        summaries = store.get_summaries(sid)
        assert len(summaries) == 2

    def test_get_summaries_by_level(self, store):
        session = store.create_session(topic="Summary Level")
        sid = session["id"]

        store.add_summary(sid, level=1, content="Level 1")
        store.add_summary(sid, level=1, content="Another Level 1")
        store.add_summary(sid, level=2, content="Level 2")

        level1 = store.get_summaries(sid, level=1)
        assert len(level1) == 2

        level2 = store.get_summaries(sid, level=2)
        assert len(level2) == 1

    def test_get_summarization_candidates_none(self, store):
        """Should return all observations when no summary exists."""
        session = store.create_session(topic="Candidates")
        sid = session["id"]

        store.add_observation(sid, type="note", content="Obs 1")
        store.add_observation(sid, type="note", content="Obs 2")

        candidates = store.get_summarization_candidates(sid)
        assert len(candidates) == 2

    def test_get_summarization_candidates_after_summary(self, store):
        """Should return only observations after the latest summary."""
        session = store.create_session(topic="Candidates After")
        sid = session["id"]

        store.add_observation(sid, type="note", content="Before summary")
        store.add_summary(sid, level=1, content="First summary")
        store.add_observation(sid, type="note", content="After summary")

        candidates = store.get_summarization_candidates(sid)
        assert len(candidates) == 1
        assert candidates[0]["content"] == "After summary"


# =========================================================================
# Test: store.py — Edge Cases
# =========================================================================


class TestStoreEdgeCases:
    """Edge cases and error handling."""

    def test_same_session_id_not_allowed(self, store):
        """SQLite primary key constraint prevents duplicate session IDs."""
        import sqlite3

        sql = (
            "INSERT INTO sessions "
            "(id, status, topic, task_ids, token_budget, started_at, updated_at) "
            "VALUES (?, 'active', ?, '[]', 2000, ?, ?)"
        )
        ts = now_iso()
        with pytest.raises(sqlite3.IntegrityError):
            store._conn.execute(sql, ("ses_duplicate", "dup", ts, ts))
            store._conn.execute(sql, ("ses_duplicate", "dup2", ts, ts))
            store._conn.commit()

    def test_database_path_from_env(self, tmp_path: Path, monkeypatch):
        """Test that SESSION_DB_PATH env var overrides default."""
        custom_path = tmp_path / "custom" / "session.db"
        monkeypatch.setenv("SESSION_DB_PATH", str(custom_path))

        from tools.session_memory.store import SessionStore

        store = SessionStore()
        assert store.path == custom_path.resolve()
        store.close()

    def test_update_invalid_field(self, store):
        """Updating with an invalid field should be silently ignored."""
        session = store.create_session(topic="Invalid Field")
        result = store.update_session(session["id"], nonexistent="value")
        assert result is True  # Still succeeds (field ignored)

    def test_add_observation_unknown_session(self, store):
        """Adding observation to non-existent session should fail FK constraint."""
        import sqlite3

        with pytest.raises(sqlite3.IntegrityError):
            store.add_observation("ses_nonexistent", type="note", content="Orphan")


# =========================================================================
# Test: server.py — MCP Tools (smoke tests)
# =========================================================================


class TestServerTools:
    """Smoke tests for all 5 MCP tools using CliRunner.

    Note: FastMCP tools cannot be invoked directly via CliRunner because
    they communicate over stdio. These tests verify that the tools are
    correctly registered and the server starts without errors.
    """

    def test_server_imports(self):
        """Verify the server module can be imported without errors."""
        from tools.session_memory import server as srv

        assert srv.MCP_AVAILABLE is True
        assert hasattr(srv, "mcp")

    def test_server_tools_registered(self):
        """Verify all 5 tools are registered on the MCP instance."""
        from tools.session_memory import server as srv

        # FastMCP exposes tools via ._tool_manager
        tool_names = {tool.name for tool in srv.mcp._tool_manager._tools.values()}
        expected = {
            "session_init",
            "session_observe",
            "session_context",
            "session_recall",
            "session_summarize",
        }
        for name in expected:
            assert name in tool_names, f"Tool '{name}' not registered"

    def test_main_server_function_exists(self):
        """Verify main_server() entry point exists and doesn't crash on import."""
        from tools.session_memory.server import main_server

        assert callable(main_server)


# =========================================================================
# Test: store.py — Token Economics (generated column)
# =========================================================================


class TestStoreTokenEconomics:
    """Test the generated token_savings column."""

    def test_token_savings_generated(self, store):
        session = store.create_session(topic="Token Econ")
        sid = session["id"]

        # 100 discovery, 10 read → 90% savings
        obs_id = store.add_observation(
            sid,
            type="note",
            content="Token test",
            tokens_discovery=100,
            tokens_read=10,
        )
        fetched = store.get_observation(obs_id)
        assert fetched is not None
        assert fetched["token_savings"] == 0.9  # (100-10)/100

    def test_token_savings_zero_discovery(self, store):
        session = store.create_session(topic="Zero Discovery")
        sid = session["id"]

        obs_id = store.add_observation(
            sid,
            type="note",
            content="Zero disc",
            tokens_discovery=0,
            tokens_read=10,
        )
        fetched = store.get_observation(obs_id)
        assert fetched is not None
        assert fetched["token_savings"] == 0.0

    def test_session_token_accumulation(self, store):
        session = store.create_session(topic="Accumulation")
        sid = session["id"]

        store.add_observation(sid, type="note", content="A", tokens_discovery=100, tokens_read=10)
        store.add_observation(sid, type="note", content="B", tokens_discovery=200, tokens_read=20)

        fetched = store.get_session(sid)
        assert fetched is not None
        assert fetched["token_discovery"] == 300
        assert fetched["token_read"] == 30


# =========================================================================
# Test: store.py — Database Lifecycle
# =========================================================================


class TestStoreLifecycle:
    """Database connection lifecycle."""

    def test_close_and_reconnect(self, tmp_db: Path):
        from tools.session_memory.store import SessionStore

        s = SessionStore(db_path=tmp_db)
        session = s.create_session(topic="Lifecycle")
        sid = session["id"]
        s.close()

        # Reconnect
        s2 = SessionStore(db_path=tmp_db)
        fetched = s2.get_session(sid)
        assert fetched is not None
        assert fetched["topic"] == "Lifecycle"
        s2.close()

    def test_wal_mode_enabled(self, tmp_db: Path):
        from tools.session_memory.store import SessionStore

        s = SessionStore(db_path=tmp_db)
        row = s._conn.execute("PRAGMA journal_mode").fetchone()
        assert row[0].lower() == "wal"
        s.close()

    def test_foreign_keys_enabled(self, tmp_db: Path):
        from tools.session_memory.store import SessionStore

        s = SessionStore(db_path=tmp_db)
        row = s._conn.execute("PRAGMA foreign_keys").fetchone()
        assert row[0] == 1
        s.close()
