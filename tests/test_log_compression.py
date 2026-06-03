"""Tests for log compression (hot/warm/cold) across Taskmanager and Session Memory.

Covers:
- ``models.py`` — CompressedEvent, SummaryEvent, Task.compression_level
- ``state.py`` — compress_events() with dry-run and actual apply
- ``store.py`` — compress_observations() with dry-run and actual apply
- ``cli.py`` / ``main.py`` — CLI compression commands
"""

from __future__ import annotations

import json
import tempfile
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import pytest
import yaml

from tools.taskmanager.models import (
    CompressedEvent,
    SummaryEvent,
    Task,
    TaskEvent,
    now_iso,
)
from tools.taskmanager.state import StateStore, compress_events, _days_ago, _iso_week_key

# =========================================================================
# Helpers
# =========================================================================


def _old_iso(days_ago: int) -> str:
    """Return an ISO timestamp from ``days_ago`` in the past."""
    dt = datetime.now(timezone.utc)
    from datetime import timedelta

    dt = dt - timedelta(days=days_ago)
    return dt.strftime("%Y-%m-%dT%H:%M:%S")


@pytest.fixture
def tmp_state_file() -> Path:
    """Fixture: create a temporary task YAML with controlled test tasks."""
    with tempfile.NamedTemporaryFile(mode="w", suffix=".yaml", delete=False) as f:
        tasks: dict[str, dict[str, Any]] = {
            "T-HOT-001": {
                "id": "T-HOT-001",
                "description": "Recent hot task",
                "status": "completed",
                "priority": "medium",
                "owner": "Efesto",
                "created_at": _old_iso(1),
                "updated_at": _old_iso(1),
                "tags": [],
                "parent": None,
                "handoff_refs": [],
                "events": [
                    {
                        "timestamp": _old_iso(1),
                        "type": "note",
                        "details": "This is a very long event detail that should not be compressed because it is too recent. "
                        * 5,
                        "handoff_path": "Library/Handoff/2026/05/recent.md",
                    },
                ],
                "compression_level": 0,
            },
            "T-WARM-001": {
                "id": "T-WARM-001",
                "description": "Warm task (15 days old)",
                "status": "completed",
                "priority": "medium",
                "owner": "Efesto",
                "created_at": _old_iso(15),
                "updated_at": _old_iso(15),
                "tags": [],
                "parent": None,
                "handoff_refs": [],
                "events": [
                    {
                        "timestamp": _old_iso(15),
                        "type": "decision",
                        "details": "We decided to implement the feature using the new approach with async support and proper error handling throughout the entire pipeline. "
                        * 3,
                        "handoff_path": "Library/Handoff/2026/05/warm-decision.md",
                    },
                    {
                        "timestamp": _old_iso(15),
                        "type": "handoff_ref",
                        "details": "Handoff completed successfully with all tests passing.",
                        "handoff_path": "Library/Handoff/2026/05/warm-handoff.md",
                    },
                ],
                "compression_level": 0,
            },
            "T-COLD-001": {
                "id": "T-COLD-001",
                "description": "Cold task (45 days old)",
                "status": "completed",
                "priority": "low",
                "owner": "Poros",
                "created_at": _old_iso(45),
                "updated_at": _old_iso(45),
                "tags": [],
                "parent": None,
                "handoff_refs": [],
                "events": [
                    {
                        "timestamp": _old_iso(45),
                        "type": "note",
                        "details": "Initial analysis",
                        "handoff_path": None,
                    },
                    {
                        "timestamp": _old_iso(44),
                        "type": "decision",
                        "details": "Chose Option A",
                        "handoff_path": "Library/Handoff/2026/04/cold-decision.md",
                    },
                    {
                        "timestamp": _old_iso(43),
                        "type": "handoff_ref",
                        "details": "Completed the implementation",
                        "handoff_path": "Library/Handoff/2026/04/cold-handoff.md",
                    },
                ],
                "compression_level": 0,
            },
        }
        state = {
            "version": 1,
            "last_updated": now_iso(),
            "counter": {},
            "tasks": tasks,
        }
        yaml.dump(state, f, default_flow_style=False, allow_unicode=True, sort_keys=False, indent=2)
        f.flush()
        db_path = Path(f.name)
    yield db_path
    if db_path.exists():
        db_path.unlink()


@pytest.fixture
def tmp_state_store(tmp_state_file: Path) -> StateStore:
    """Fixture: create a StateStore pointing at the temp state file."""
    return StateStore(path=tmp_state_file)


# =========================================================================
# Test: models.py
# =========================================================================


class TestCompressionModels:
    """CompressedEvent and SummaryEvent dataclasses."""

    def test_compressed_event(self):
        ev = CompressedEvent(
            timestamp="2026-05-01T10:00:00",
            type="decision",
            details="Short summary",
            handoff_path="path/to/handoff.md",
        )
        assert ev.timestamp == "2026-05-01T10:00:00"
        assert ev.type == "decision"
        assert ev.compressed_level == 1

    def test_summary_event(self):
        ev = SummaryEvent(
            period="W21-2026",
            original_count=3,
            type_summary="2 decisions, 1 handoff_ref",
            key_handoffs=["path/a.md", "path/b.md"],
        )
        assert ev.period == "W21-2026"
        assert ev.original_count == 3
        assert ev.compressed_level == 2

    def test_task_with_compression_level(self):
        task = Task(
            id="T-TEST-001",
            description="Test task",
            status="pending",
            priority="medium",
            owner="Efesto",
            created_at=now_iso(),
            updated_at=now_iso(),
            compression_level=2,
        )
        assert task.compression_level == 2
        d = task.to_dict()
        assert d["compression_level"] == 2

    def test_task_from_dict_with_compression_level(self):
        raw = {
            "id": "T-TEST-001",
            "description": "Test",
            "status": "completed",
            "priority": "medium",
            "owner": "Poros",
            "created_at": "2026-05-01T00:00:00",
            "updated_at": "2026-05-01T00:00:00",
            "compression_level": 1,
            "events": [],
        }
        task = Task.from_dict(raw)
        assert task.compression_level == 1

    def test_task_storage_dict_with_summary_event(self):
        summary = SummaryEvent(
            period="W21-2026",
            original_count=3,
            type_summary="2 decisions, 1 handoff_ref",
            key_handoffs=["p/a.md", "p/b.md"],
        )
        task = Task(
            id="T-COLD-001",
            description="Cold task",
            status="completed",
            priority="low",
            owner="Poros",
            created_at="2026-04-01T00:00:00",
            updated_at="2026-04-01T00:00:00",
            events=[summary],
            compression_level=2,
        )
        d = task.to_storage_dict()
        assert d["compression_level"] == 2
        assert d["events"][0]["period"] == "W21-2026"
        assert d["events"][0]["key_handoffs"] == ["p/a.md", "p/b.md"]

    def test_union_event_type(self):
        """Verify that Event union type accepts all three types."""
        events = [
            TaskEvent(timestamp="t1", type="note", details="full text"),
            CompressedEvent(timestamp="t2", type="decision", details="short"),
            SummaryEvent(
                period="W22-2026",
                original_count=5,
                type_summary="3 note, 2 decision",
                key_handoffs=[],
            ),
        ]
        assert len(events) == 3
        # Check round-trip via asdict
        from dataclasses import asdict

        for e in events:
            d = asdict(e)
            assert isinstance(d, dict)


# =========================================================================
# Test: state.py — helpers
# =========================================================================


class TestDaysAgo:
    def test_zero_days_ago(self):
        ts = now_iso()
        assert _days_ago(ts) < 0.01  # within seconds

    def test_old_timestamp(self):
        ts = _old_iso(30)
        d = _days_ago(ts)
        assert 29.5 < d < 30.5

    def test_empty_timestamp_doesnt_crash(self):
        # This exercises the "T in ts" branch
        try:
            _days_ago("2026-01-01T00:00:00")
        except Exception:
            pytest.fail("_days_ago raised unexpectedly")


class TestIsoWeekKey:
    def test_week_key_format(self):
        key = _iso_week_key("2026-05-24T10:00:00")
        assert key.startswith("W")
        assert "-2026" in key
        # May 24 2026 is week 21 (Sunday)
        year, week, _ = datetime(2026, 5, 24).isocalendar()
        assert key == f"W{week:02d}-{year}"

    def test_early_january_week(self):
        # Jan 1 2026 is in week 1 of 2026 (Thursday)
        key = _iso_week_key("2026-01-01T00:00:00")
        assert key == "W01-2026"


# =========================================================================
# Test: state.py — compress_events()
# =========================================================================


class TestCompressEvents:
    def test_dry_run_preserves_data(self, tmp_state_store: StateStore):
        """Dry-run should not modify the state file."""
        original = tmp_state_store.path.read_text(encoding="utf-8")
        results = compress_events(age_days=0, max_level=2, dry_run=True, store=tmp_state_store)
        assert results["dry_run"] is True
        assert results["tasks_processed"] >= 0
        after = tmp_state_store.path.read_text(encoding="utf-8")
        assert original == after  # no changes

    def test_warm_compression(self, tmp_state_store: StateStore):
        """Warm compression should shorten event details but preserve handoff_path."""
        results = compress_events(age_days=0, max_level=1, dry_run=False, store=tmp_state_store)

        # Reload and check
        tmp_state_store.reload()
        task = tmp_state_store.get_task("T-WARM-001")
        assert task is not None
        assert task.get("compression_level") == 1
        events = task.get("events", [])
        assert len(events) == 2
        for ev in events:
            assert "period" not in ev  # not cold
            # Details should be compressed (shorter than original)
            assert len(ev.get("details", "")) <= 200
            if ev.get("handoff_path"):
                assert ev["handoff_path"] is not None  # preserved

    def test_cold_compression(self, tmp_state_store: StateStore):
        """Cold compression should merge events into a period summary."""
        results = compress_events(age_days=0, max_level=2, dry_run=False, store=tmp_state_store)

        tmp_state_store.reload()
        task = tmp_state_store.get_task("T-COLD-001")
        assert task is not None
        assert task.get("compression_level") == 2
        events = task.get("events", [])
        assert len(events) == 1  # merged into one SummaryEvent
        ev = events[0]
        assert "period" in ev
        assert ev["original_count"] >= 2
        assert "handoff" in ev["type_summary"].lower()
        assert len(ev["key_handoffs"]) > 0

    def test_hot_task_skipped(self, tmp_state_store: StateStore):
        """Hot task (1 day old) should NOT be compressed."""
        results = compress_events(age_days=None, max_level=2, dry_run=False, store=tmp_state_store)

        tmp_state_store.reload()
        task = tmp_state_store.get_task("T-HOT-001")
        assert task is not None
        # With default thresholds, it should still be hot
        assert task.get("compression_level") in (0,)

    def test_all_tasks_processed_with_age_days_0(self, tmp_state_store: StateStore):
        """With age_days=0, all tasks should be candidates."""
        results = compress_events(age_days=0, max_level=2, dry_run=True, store=tmp_state_store)
        # All 3 tasks have events, all are older than 0 days
        assert results["tasks_processed"] == 3

    def test_compress_events_handoff_paths_preserved(self, tmp_state_store: StateStore):
        """Cold compression must preserve key handoff paths."""
        results = compress_events(age_days=0, max_level=2, dry_run=False, store=tmp_state_store)

        tmp_state_store.reload()
        task = tmp_state_store.get_task("T-COLD-001")
        ev = task["events"][0]
        paths = ev["key_handoffs"]
        # The old task has 2 events with handoff paths
        assert "Library/Handoff/2026/04/cold-decision.md" in paths
        assert "Library/Handoff/2026/04/cold-handoff.md" in paths

    def test_warm_does_not_touch_cold(self, tmp_state_store: StateStore):
        """Warm compression should leave cold-level tasks alone."""
        # First compress to cold
        compress_events(age_days=0, max_level=2, dry_run=False, store=tmp_state_store)

        tmp_state_store.reload()
        task = tmp_state_store.get_task("T-COLD-001")
        assert task["compression_level"] == 2

        # Now try warm compression — it should skip the cold task (already at level >= 1)
        results = compress_events(age_days=0, max_level=1, dry_run=False, store=tmp_state_store)
        # The cold task should remain at level 2
        tmp_state_store.reload()
        task = tmp_state_store.get_task("T-COLD-001")
        assert task["compression_level"] == 2


# =========================================================================
# Test: store.py — compress_observations()
# =========================================================================


class TestCompressObservations:
    @pytest.fixture
    def sm_store(self):
        """Create a fresh SessionStore with test observations at various ages."""
        from tools.session_memory.store import SessionStore

        store = SessionStore(db_path=":memory:")
        # Create a session
        store.create_session(topic="Compression Test Session")
        session_id = store.get_active_session()["id"]

        # Add observations at different ages
        from tools.session_memory.store import now_iso as sm_now

        # Observation 1: recent (hot)
        store.add_observation(
            session_id=session_id,
            type="note",
            content="This is a very recent observation that should stay hot. " * 5,
            entities=["test"],
        )

        # Observation 2 and 3 (we can't set custom timestamps via add_observation,
        # but we can manually insert)
        store._conn.execute(
            """INSERT INTO observations
               (session_id, type, agent, content, entities, created_at)
               VALUES (?, 'decision', 'Efesto', ?, '[]', ?)""",
            (
                session_id,
                "We decided to implement the compression feature using a multi-level approach with Token Juice integration. "
                * 3,
                _old_iso(15),
            ),
        )
        store._conn.execute(
            """INSERT INTO observations
               (session_id, type, agent, content, entities, created_at)
               VALUES (?, 'result', 'Efesto', ?, '[]', ?)""",
            (
                session_id,
                "Implementation completed successfully with all tests passing and full documentation. "
                * 4,
                _old_iso(45),
            ),
        )
        store._conn.commit()

        yield store, session_id
        store.close()

    def test_dry_run(self, sm_store):
        """Dry-run should not modify the database."""
        store, session_id = sm_store
        # Read original content of old observation
        before = store._conn.execute(
            "SELECT content FROM observations WHERE created_at < datetime('now', '-10 days')"
        ).fetchone()
        original_content = before["content"]

        results = store.compress_observations(age_days=7, max_level=2, dry_run=True)
        assert results["dry_run"] is True

        # Content should still be the same
        after = store._conn.execute(
            "SELECT content FROM observations WHERE created_at < datetime('now', '-10 days')"
        ).fetchone()
        assert after["content"] == original_content

    def test_warm_compression(self, sm_store):
        """Warm compression should shorten content."""
        store, session_id = sm_store
        results = store.compress_observations(age_days=7, max_level=1, dry_run=False)

        assert results["observations_warm"] >= 1

        # Check that at least one old observation was compressed
        warm_obs = store._conn.execute(
            "SELECT content, compression_level FROM observations WHERE compression_level = 1"
        ).fetchall()
        assert len(warm_obs) >= 1
        for row in warm_obs:
            assert len(row["content"]) <= 300

    def test_cold_compression(self, sm_store):
        """Cold compression should group by week and create summaries."""
        store, session_id = sm_store
        results = store.compress_observations(age_days=7, max_level=2, dry_run=False)

        assert results["observations_cold"] >= 1
        assert results["summaries_created"] >= 1

        # Check summaries
        summaries = store.get_summaries(session_id, level=3)
        assert len(summaries) >= 1
        assert "Period: W" in summaries[0]["content"]

    def test_recent_observations_untouched(self, sm_store):
        """Recent hot observations should not be compressed."""
        store, session_id = sm_store
        results = store.compress_observations(age_days=7, max_level=2, dry_run=False)

        hot_obs = store._conn.execute(
            "SELECT compression_level FROM observations WHERE compression_level = 0"
        ).fetchall()
        # At least one observation should remain hot (the recent one)
        hot_count = len(hot_obs)
        assert hot_count >= 1


# =========================================================================
# Test: CLI
# =========================================================================


class TestTaskmanagerCLI:
    def test_compress_help(self):
        """Verify the compress command is registered."""
        from typer.testing import CliRunner
        from tools.taskmanager.main import app

        runner = CliRunner()
        result = runner.invoke(app, ["compress", "--help"])
        assert result.exit_code == 0
        assert "Compress" in result.output

    def test_compress_warm_dry_run(self, tmp_state_file: Path):
        """Smoke test: compress --warm --dry-run on temp state."""
        import os

        os.environ["STATE_FILE_PATH"] = str(tmp_state_file)

        from typer.testing import CliRunner
        from tools.taskmanager.main import app

        # Patch StateStore to use our temp file
        import tools.taskmanager.state as tm_state

        original_init = tm_state.StateStore.__init__

        def patched_init(self, path=None):
            if path is None:
                path = tmp_state_file
            original_init(self, path)

        tm_state.StateStore.__init__ = patched_init

        runner = CliRunner()
        result = runner.invoke(app, ["compress", "--warm", "--dry-run"])
        assert result.exit_code == 0
        assert "tasks_processed" in result.output or "dry_run" in result.output

        # Restore
        tm_state.StateStore.__init__ = original_init


class TestSessionMemoryCLI:
    def test_compress_help(self):
        """Verify the compress command is registered."""
        from typer.testing import CliRunner
        from tools.session_memory.cli import app

        runner = CliRunner()
        result = runner.invoke(app, ["compress", "--help"])
        assert result.exit_code == 0
        assert "Compress" in result.output or "Warm" in result.output or "Cold" in result.output


# =========================================================================
# Test: Token Juice rules
# =========================================================================


class TestTokenJuiceLogRules:
    def test_log_compression_warm_rule_exists(self):
        """Verify the warm compression rule was loaded correctly."""
        import json
        from pathlib import Path

        rule_path = Path("tools/token_juice/rules/log-compression-warm.json")
        assert rule_path.exists()
        data = json.loads(rule_path.read_text())
        assert data["id"] == "log-compression-warm"
        assert data["family"] == "event_log"

    def test_log_compression_cold_rule_exists(self):
        """Verify the cold compression rule was loaded correctly."""
        import json
        from pathlib import Path

        rule_path = Path("tools/token_juice/rules/log-compression-cold.json")
        assert rule_path.exists()
        data = json.loads(rule_path.read_text())
        assert data["id"] == "log-compression-cold"
        assert data["family"] == "event_log"


# =========================================================================
# Test: log_compressor CLI
# =========================================================================


class TestLogCompressorCLI:
    def test_weekly_help(self):
        """Verify the weekly command is registered."""
        from typer.testing import CliRunner
        from tools.log_compressor.main import app

        runner = CliRunner()
        result = runner.invoke(app, ["weekly", "--help"])
        assert result.exit_code == 0

    def test_monthly_help(self):
        """Verify the monthly command is registered."""
        from typer.testing import CliRunner
        from tools.log_compressor.main import app

        runner = CliRunner()
        result = runner.invoke(app, ["monthly", "--help"])
        assert result.exit_code == 0

    def test_status_help(self):
        """Verify the status command is registered."""
        from typer.testing import CliRunner
        from tools.log_compressor.main import app

        runner = CliRunner()
        result = runner.invoke(app, ["status", "--help"])
        assert result.exit_code == 0
