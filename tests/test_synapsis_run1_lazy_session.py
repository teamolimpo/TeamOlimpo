"""Test RUN 1 — Lazy Session Creation (Synapsis V2).

Tests:
1. observation su sessione inesistente → sessione auto-creata, observation scritta
2. idempotenza: due `session_observe` con stessa session_id inesistente
3. nessun cambiamento API pubblica: session_init funziona come prima
"""

from __future__ import annotations

import tempfile
from pathlib import Path

from loguru import logger

from tools.synapsis.store import SynapsisStore

# Disable loguru for clean test output
logger.remove()


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


def _make_store() -> SynapsisStore:
    """Create a SynapsisStore backed by a temporary file."""
    tmp = tempfile.NamedTemporaryFile(suffix=".db", delete=False)
    tmp.close()
    store = SynapsisStore(db_path=Path(tmp.name))
    return store


# ---------------------------------------------------------------------------
# Test 1: Observation on non-existent session → auto-created
# ---------------------------------------------------------------------------


def test_observe_auto_creates_session():
    """session_observe on a missing session should auto-create it."""
    store = _make_store()
    session_id = "ses_test_lazy_001"

    # Verify session does NOT exist yet
    assert store.get_session(session_id) is None, "Session should not exist before test"

    # Call ensure_session directly (as server.py would)
    session = store.ensure_session(session_id)
    assert session is not None, "ensure_session should return a session dict"
    assert session["id"] == session_id
    assert session["status"] == "active"
    assert session["topic"] == "auto-recovered"

    # Now add an observation — should succeed
    obs_id = store.add_observation(
        session_id=session_id,
        type="note",
        content="Test observation on auto-created session",
        agent="Efesto",
    )
    assert obs_id is not None and obs_id > 0, "Observation should be created"

    # Verify session still exists
    session_after = store.get_session(session_id)
    assert session_after is not None
    assert session_after["status"] == "active"

    logger.info("✓ Test 1 passed: observation on auto-created session works")


# ---------------------------------------------------------------------------
# Test 2: Idempotence — calling ensure_session twice
# ---------------------------------------------------------------------------


def test_ensure_session_idempotent():
    """Calling ensure_session twice should be safe."""
    store = _make_store()
    session_id = "ses_test_lazy_002"

    # First call — creates
    session1 = store.ensure_session(session_id)
    assert session1 is not None

    # Second call — should not fail, should return same session
    session2 = store.ensure_session(session_id)
    assert session2 is not None
    assert session2["id"] == session1["id"]
    assert session2["status"] == session1["status"]

    # Verify only one session exists with this ID
    rows = store._conn.execute(
        "SELECT COUNT(*) FROM sessions WHERE id = ?", (session_id,)
    ).fetchone()
    assert rows[0] == 1, f"Expected 1 session, found {rows[0]}"

    logger.info("✓ Test 2 passed: ensure_session is idempotent")


# ---------------------------------------------------------------------------
# Test 3: Public API unchanged — create_session still works
# ---------------------------------------------------------------------------


def test_create_session_still_works():
    """create_session should function identically to before."""
    store = _make_store()

    # Use the original create_session
    session = store.create_session(topic="test-manual", task_ids=["T-TEST-001"])
    assert session is not None
    assert session["status"] == "active"
    assert session["topic"] == "test-manual"
    assert session["task_ids"] == ["T-TEST-001"]

    logger.info("✓ Test 3a passed: create_session works identically")


# ---------------------------------------------------------------------------
# Test 4: Public API unchanged — get_session still works
# ---------------------------------------------------------------------------


def test_get_session_still_works():
    """get_session should work for both created and auto-created sessions."""
    store = _make_store()

    # Create session normally
    session = store.create_session(topic="test-get-session")
    sid = session["id"]

    # Retrieve it
    retrieved = store.get_session(sid)
    assert retrieved is not None
    assert retrieved["id"] == sid
    assert retrieved["topic"] == "test-get-session"

    # Non-existent returns None
    assert store.get_session("ses_nonexistent_999") is None

    logger.info("✓ Test 4 passed: get_session works identically")


# ---------------------------------------------------------------------------
# Test 5: ensure_session accepts custom topic and agent
# ---------------------------------------------------------------------------


def test_ensure_session_custom_params():
    """ensure_session should accept custom topic and agent."""
    store = _make_store()
    session_id = "ses_test_lazy_custom"

    session = store.ensure_session(
        session_id=session_id,
        topic="custom-topic",
        agent="Athena",
    )
    assert session["id"] == session_id
    assert session["topic"] == "custom-topic"
    assert session["agent"] == "Athena"
    assert session["status"] == "active"

    logger.info("✓ Test 5 passed: ensure_session accepts custom topic/agent")


# ---------------------------------------------------------------------------
# Test 6: Simulate full session_observe flow (as server.py would do it)
# ---------------------------------------------------------------------------


def test_full_observe_flow_with_lazy_recovery():
    """Simulate the exact flow in server.py: get_session -> None -> ensure_session."""
    store = _make_store()
    session_id = "ses_test_lazy_flow"

    # Step 1: session does not exist
    session = store.get_session(session_id)
    assert session is None

    # Step 2: lazy recovery (exactly as server.py does it)
    session = store.ensure_session(session_id)
    assert session is not None

    # Step 3: add observation (exactly as server.py does it)
    obs_id = store.add_observation(
        session_id=session_id,
        type="decision",
        content="This is a test decision after lazy recovery",
        agent="Efesto",
    )
    assert obs_id is not None and obs_id > 0

    # Step 4: verify observation is retrievable
    obs = store._conn.execute("SELECT * FROM observations WHERE id = ?", (obs_id,)).fetchone()
    assert obs is not None
    assert obs["session_id"] == session_id
    assert obs["type"] == "decision"

    logger.info("✓ Test 6 passed: full observe flow with lazy recovery works")


# ---------------------------------------------------------------------------
# Run all tests
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    test_observe_auto_creates_session()
    test_ensure_session_idempotent()
    test_create_session_still_works()
    test_get_session_still_works()
    test_ensure_session_custom_params()
    test_full_observe_flow_with_lazy_recovery()
    print("\n✅ All 6 tests passed!")
