"""SQLite backing store for Session Memory MCP server.

Provides ``SessionStore`` with full CRUD for sessions, observations, entities,
summaries, and FTS5 search.

Storage location: ``Library/System/Poros/session.db`` (relative to project root,
overridable via the ``SESSION_DB_PATH`` environment variable).
"""

from __future__ import annotations

import json
import os
from datetime import datetime
from pathlib import Path
from typing import Any

from loguru import logger

from tools.common.paths import resolve_absolute
from tools.session_memory.models import (
    compute_token_savings,
    generate_session_id,
    now_iso,
)

# ---------------------------------------------------------------------------
# Default storage path
# ---------------------------------------------------------------------------

_DEFAULT_DB_REL = Path("Library/System/Poros/session.db")


def _resolve_db_path() -> Path:
    """Resolve the database path from env var or default.

    Priority:
    1. ``SESSION_DB_PATH`` environment variable
       (absolute path or relative to project root)
    2. Default: ``Library/System/Poros/session.db`` relative to project root

    Returns:
        Absolute path to the SQLite database file.
    """
    env_path = os.environ.get("SESSION_DB_PATH")
    if env_path:
        p = Path(env_path)
        if p.is_absolute():
            return p
        # Cast Path to str for resolve_absolute which expects *str
        return resolve_absolute(str(p))
    return resolve_absolute(str(_DEFAULT_DB_REL))


# ---------------------------------------------------------------------------
# SQL schema (matches design doc exactly)
# ---------------------------------------------------------------------------

_SCHEMA_SQL = """
-- ============================================================
-- SESSIONS — one row per Poros session
-- ============================================================
CREATE TABLE IF NOT EXISTS sessions (
    id              TEXT PRIMARY KEY,
    status          TEXT NOT NULL DEFAULT 'active'
                    CHECK (status IN ('active', 'interrupted', 'completed')),
    topic           TEXT NOT NULL DEFAULT '',
    summary         TEXT NOT NULL DEFAULT '',
    agent           TEXT NOT NULL DEFAULT 'Poros',
    task_ids        TEXT NOT NULL DEFAULT '[]',
    token_budget    INTEGER NOT NULL DEFAULT 2000,
    token_discovery INTEGER NOT NULL DEFAULT 0,
    token_read      INTEGER NOT NULL DEFAULT 0,
    started_at      TEXT NOT NULL,
    ended_at        TEXT,
    updated_at      TEXT NOT NULL,
    metadata        TEXT NOT NULL DEFAULT '{}'
);

-- ============================================================
-- OBSERVATIONS — timeline of what happened
-- ============================================================
CREATE TABLE IF NOT EXISTS observations (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    session_id      TEXT NOT NULL REFERENCES sessions(id),
    parent_id       INTEGER REFERENCES observations(id),
    type            TEXT NOT NULL
                    CHECK (type IN (
                        'decision', 'delegation', 'result',
                        'note', 'handoff', 'user_message', 'system'
                    )),
    agent           TEXT NOT NULL DEFAULT 'Poros',
    content         TEXT NOT NULL,
    tokens_discovery INTEGER NOT NULL DEFAULT 0,
    tokens_read     INTEGER NOT NULL DEFAULT 0,
    token_savings   REAL GENERATED ALWAYS AS (
        CASE WHEN tokens_discovery > 0
        THEN (tokens_discovery - tokens_read) * 1.0 / tokens_discovery
        ELSE 0 END
    ) STORED,
    entities        TEXT NOT NULL DEFAULT '[]',
    handoff_path    TEXT,
    task_ref        TEXT,
    compression_level INTEGER NOT NULL DEFAULT 0,
    created_at      TEXT NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_obs_session ON observations(session_id, created_at);
CREATE INDEX IF NOT EXISTS idx_obs_type ON observations(type);
CREATE INDEX IF NOT EXISTS idx_obs_agent ON observations(agent);

-- ============================================================
-- ENTITIES — cross-session linking
-- ============================================================
CREATE TABLE IF NOT EXISTS entities (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    name            TEXT NOT NULL UNIQUE,
    entity_type     TEXT NOT NULL DEFAULT 'concept'
                    CHECK (entity_type IN (
                        'project', 'agent', 'concept',
                        'person', 'technology', 'task'
                    )),
    metadata        TEXT NOT NULL DEFAULT '{}',
    created_at      TEXT NOT NULL,
    updated_at      TEXT NOT NULL
);

-- ============================================================
-- OBSERVATION_ENTITIES — many-to-many join
-- ============================================================
CREATE TABLE IF NOT EXISTS observation_entities (
    observation_id  INTEGER NOT NULL REFERENCES observations(id),
    entity_id       INTEGER NOT NULL REFERENCES entities(id),
    PRIMARY KEY (observation_id, entity_id)
);

-- ============================================================
-- SUMMARIES — compression layers
-- ============================================================
CREATE TABLE IF NOT EXISTS summaries (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    session_id      TEXT NOT NULL REFERENCES sessions(id),
    level           INTEGER NOT NULL CHECK (level IN (1, 2, 3)),
    parent_id       INTEGER REFERENCES summaries(id),
    content         TEXT NOT NULL,
    token_count     INTEGER NOT NULL DEFAULT 0,
    created_at      TEXT NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_summary_session ON summaries(session_id, level);

-- ============================================================
-- FTS5 — full-text search on observations
-- ============================================================
CREATE VIRTUAL TABLE IF NOT EXISTS observations_fts USING fts5(
    content,
    content=observations,
    content_rowid=id,
    tokenize='porter unicode61'
);
"""

# ---------------------------------------------------------------------------
# FTS5 triggers (only created once)
# ---------------------------------------------------------------------------

_FTS_TRIGGERS_SQL = """
CREATE TRIGGER IF NOT EXISTS observations_ai AFTER INSERT ON observations BEGIN
    INSERT INTO observations_fts(rowid, content)
    VALUES (new.id, new.content);
END;

CREATE TRIGGER IF NOT EXISTS observations_ad AFTER DELETE ON observations BEGIN
    INSERT INTO observations_fts(observations_fts, rowid, content)
    VALUES ('delete', old.id, old.content);
END;

CREATE TRIGGER IF NOT EXISTS observations_au AFTER UPDATE ON observations BEGIN
    INSERT INTO observations_fts(observations_fts, rowid, content)
    VALUES ('delete', old.id, old.content);
    INSERT INTO observations_fts(rowid, content)
    VALUES (new.id, new.content);
END;
"""

# ---------------------------------------------------------------------------
# Compression helper
# ---------------------------------------------------------------------------


def _compress_obs_content(text: str, max_chars: int = 300) -> str:
    """Compress observation content using Token Juice C2 prose compressor.

    Args:
        text: Original observation content.
        max_chars: Maximum character length.

    Returns:
        Compressed string.
    """
    try:
        from tools.token_juice.compressor import compress as tj_compress

        compressed = tj_compress(text, intensity="full")
        if len(compressed) > max_chars:
            compressed = compressed[:max_chars]
        if len(compressed) < len(text) * 0.8:
            return compressed
        return text[:max_chars]
    except Exception:
        return text[:max_chars]


# ---------------------------------------------------------------------------
# SessionStore
# ---------------------------------------------------------------------------


class SessionStore:
    """SQLite CRUD for session memory.

    Manages the ``session.db`` with tables for sessions, observations, entities,
    summaries, and an FTS5 full-text search index.

    Args:
        db_path: Optional explicit database path. If ``None``, resolves
                 from ``SESSION_DB_PATH`` env var or default location.
    """

    def __init__(self, db_path: str | Path | None = None) -> None:
        self.path: Path
        if db_path is not None:
            self.path = Path(db_path)
        else:
            self.path = _resolve_db_path()

        logger.debug(f"SessionStore initialised with db_path={self.path}")

        # Ensure parent directory exists
        self.path.parent.mkdir(parents=True, exist_ok=True)

        self._conn: Any = None  # sqlite3.Connection
        self._connect()

    def _connect(self) -> None:
        """Open SQLite connection, enable WAL mode and foreign keys."""
        import sqlite3

        self._conn = sqlite3.connect(str(self.path))
        self._conn.row_factory = sqlite3.Row
        self._conn.execute("PRAGMA journal_mode=WAL;")
        self._conn.execute("PRAGMA foreign_keys=ON;")
        self._init_schema()

    def _init_schema(self) -> None:
        """Create tables and FTS5 triggers if they don't exist.

        Also runs safe migrations for columns added in later versions.
        """
        self._conn.executescript(_SCHEMA_SQL)
        self._conn.executescript(_FTS_TRIGGERS_SQL)
        self._safe_add_column("observations", "compression_level", "INTEGER NOT NULL DEFAULT 0")
        self._conn.commit()
        logger.debug("Schema initialised (tables + FTS5 triggers + migrations)")

    def _safe_add_column(self, table: str, column: str, col_def: str) -> None:
        """Add a column to a table if it doesn't already exist.

        Args:
            table: Table name.
            column: Column name.
            col_def: Column type and constraints (e.g. ``INTEGER NOT NULL DEFAULT 0``).
        """
        cursor = self._conn.execute(f"PRAGMA table_info({table})")
        existing_cols: set[str] = {row[1] for row in cursor.fetchall()}
        if column not in existing_cols:
            self._conn.execute(f"ALTER TABLE {table} ADD COLUMN {column} {col_def}")
            self._conn.commit()
            logger.debug(f"Added column '{column}' to table '{table}'")

    def close(self) -> None:
        """Close the SQLite connection."""
        if self._conn:
            self._conn.close()
            self._conn = None
            logger.debug("SessionStore connection closed")

    # ------------------------------------------------------------------
    # Sessions
    # ------------------------------------------------------------------

    def create_session(
        self,
        topic: str,
        task_ids: list[str] | None = None,
        token_budget: int = 2000,
    ) -> dict[str, Any]:
        """Create a new session and return its data.

        Args:
            topic: Main topic for the session.
            task_ids: Optional list of associated task IDs.
            token_budget: Maximum token budget for context (default 2000).

        Returns:
            Session data dict (JSON-friendly).
        """
        session_id = generate_session_id()
        ts = now_iso()
        task_ids_json = json.dumps(task_ids or [])

        self._conn.execute(
            """INSERT INTO sessions
               (id, status, topic, summary, agent, task_ids, token_budget,
                token_discovery, token_read, started_at, updated_at, metadata)
               VALUES (?, 'active', ?, '', 'Poros', ?, ?, 0, 0, ?, ?, '{}')""",
            (session_id, topic, task_ids_json, token_budget, ts, ts),
        )
        self._conn.commit()

        logger.info(f"Session created: {session_id} topic='{topic[:60]}'")

        return {
            "id": session_id,
            "status": "active",
            "topic": topic,
            "task_ids": task_ids or [],
            "token_budget": token_budget,
            "started_at": ts,
            "updated_at": ts,
        }

    def get_session(self, session_id: str) -> dict[str, Any] | None:
        """Retrieve a session by ID.

        Args:
            session_id: The session ID.

        Returns:
            Session data dict, or ``None`` if not found.
        """
        row = self._conn.execute("SELECT * FROM sessions WHERE id = ?", (session_id,)).fetchone()

        if row is None:
            return None

        return self._row_to_session_dict(row)

    def update_session(self, session_id: str, **kwargs: Any) -> bool:  # noqa: ANN401
        """Update fields on an existing session.

        Accepted keyword arguments: ``status``, ``topic``, ``summary``,
        ``token_discovery``, ``token_read``, ``ended_at``.

        Args:
            session_id: The session ID.
            **kwargs: Fields to update.

        Returns:
            ``True`` if the session was found and updated, ``False`` otherwise.
        """
        allowed = {
            "status",
            "topic",
            "summary",
            "agent",
            "token_budget",
            "token_discovery",
            "token_read",
            "ended_at",
            "metadata",
            "task_ids",
        }
        updates: dict[str, Any] = {k: v for k, v in kwargs.items() if k in allowed}
        if not updates:
            logger.debug(f"No valid fields to update for session {session_id}")
            return True  # no-op is not a failure

        updates["updated_at"] = now_iso()

        set_clause = ", ".join(f"{k} = ?" for k in updates)
        values = list(updates.values()) + [session_id]

        cur = self._conn.execute(
            f"UPDATE sessions SET {set_clause} WHERE id = ?",
            values,
        )
        self._conn.commit()

        if cur.rowcount == 0:
            logger.warning(f"Session {session_id} not found for update")
            return False

        logger.debug(f"Session {session_id} updated: {set(updates.keys())}")
        return True

    def get_active_session(self) -> dict[str, Any] | None:
        """Return the most recent non-completed session.

        Returns:
            Latest active/interrupted session dict, or ``None``.
        """
        row = self._conn.execute(
            """SELECT * FROM sessions
               WHERE status IN ('active', 'interrupted')
               ORDER BY rowid DESC
               LIMIT 1""",
        ).fetchone()

        if row is None:
            return None

        return self._row_to_session_dict(row)

    def get_session_metrics(self, session_id: str) -> dict[str, Any]:
        """Compute aggregate metrics for a session.

        Args:
            session_id: The session ID.

        Returns:
            Dict with ``observations_count``, ``total_tokens_discovery``,
            ``total_tokens_read``, ``token_savings_avg``,
            ``entity_count``, ``summary_count``.
        """
        obs_row = self._conn.execute(
            """SELECT COUNT(*) AS cnt,
                      COALESCE(SUM(tokens_discovery), 0) AS tot_disc,
                      COALESCE(SUM(tokens_read), 0) AS tot_read
               FROM observations WHERE session_id = ?""",
            (session_id,),
        ).fetchone()

        entity_row = self._conn.execute(
            """SELECT COUNT(DISTINCT e.id) AS cnt
               FROM entities e
               JOIN observation_entities oe ON oe.entity_id = e.id
               JOIN observations o ON o.id = oe.observation_id
               WHERE o.session_id = ?""",
            (session_id,),
        ).fetchone()

        summary_row = self._conn.execute(
            "SELECT COUNT(*) AS cnt FROM summaries WHERE session_id = ?",
            (session_id,),
        ).fetchone()

        obs_count = obs_row["cnt"] if obs_row else 0
        tot_disc = obs_row["tot_disc"] if obs_row else 0
        tot_read = obs_row["tot_read"] if obs_row else 0
        savings_avg = compute_token_savings(tot_disc, tot_read) if tot_disc > 0 else 0.0

        return {
            "observations_count": obs_count,
            "total_tokens_discovery": tot_disc,
            "total_tokens_read": tot_read,
            "token_savings_avg": round(savings_avg, 4),
            "entity_count": entity_row["cnt"] if entity_row else 0,
            "summary_count": summary_row["cnt"] if summary_row else 0,
        }

    # ------------------------------------------------------------------
    # Observations
    # ------------------------------------------------------------------

    def add_observation(
        self,
        session_id: str,
        type: str,
        content: str,
        agent: str = "Poros",
        entities: list[str] | None = None,
        handoff_path: str | None = None,
        task_ref: str | None = None,
        tokens_discovery: int = 0,
        tokens_read: int = 0,
        parent_id: int | None = None,
    ) -> int:
        """Add an observation to the timeline.

        Args:
            session_id: The session ID.
            type: Observation type (see ``ObservationType`` enum).
            content: Observation text.
            agent: Agent that produced the observation.
            entities: List of entity names to link.
            handoff_path: Optional handoff file path.
            task_ref: Optional task reference ID.
            tokens_discovery: Token count for generation.
            tokens_read: Token count for reading.
            parent_id: Optional parent observation ID (threading).

        Returns:
            The new observation ID (integer).
        """
        ts = now_iso()
        entities_json = json.dumps(entities or [])

        cur = self._conn.execute(
            """INSERT INTO observations
               (session_id, parent_id, type, agent, content,
                tokens_discovery, tokens_read, entities,
                handoff_path, task_ref, created_at)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (
                session_id,
                parent_id,
                type,
                agent,
                content,
                tokens_discovery,
                tokens_read,
                entities_json,
                handoff_path,
                task_ref,
                ts,
            ),
        )
        obs_id = cur.lastrowid
        if obs_id is None:
            msg = "Failed to insert observation — lastrowid is None"
            raise RuntimeError(msg)

        # Update session token counters
        self._conn.execute(
            """UPDATE sessions SET
               token_discovery = token_discovery + ?,
               token_read = token_read + ?,
               updated_at = ?
               WHERE id = ?""",
            (tokens_discovery, tokens_read, ts, session_id),
        )

        self._conn.commit()

        logger.debug(
            f"Observation {obs_id} added to session {session_id} (type={type}, agent={agent})"
        )

        return obs_id

    def get_observation(self, observation_id: int) -> dict[str, Any] | None:
        """Retrieve a single observation by ID.

        Args:
            observation_id: The observation ID.

        Returns:
            Observation data dict, or ``None`` if not found.
        """
        row = self._conn.execute(
            "SELECT * FROM observations WHERE id = ?", (observation_id,)
        ).fetchone()

        if row is None:
            return None

        return self._row_to_observation_dict(row)

    def get_observations(
        self,
        session_id: str,
        limit: int = 20,
        offset: int = 0,
        types: list[str] | None = None,
    ) -> list[dict[str, Any]]:
        """Retrieve observations for a session, newest first.

        Args:
            session_id: The session ID.
            limit: Maximum number of observations (default 20).
            offset: Offset for pagination.
            types: Optional filter by observation types.

        Returns:
            List of observation data dicts.
        """
        query = "SELECT * FROM observations WHERE session_id = ?"
        params: list[Any] = [session_id]

        if types:
            placeholders = ",".join("?" for _ in types)
            query += f" AND type IN ({placeholders})"
            params.extend(types)

        query += " ORDER BY created_at DESC LIMIT ? OFFSET ?"
        params.extend([limit, offset])

        rows = self._conn.execute(query, params).fetchall()
        return [self._row_to_observation_dict(r) for r in rows]

    def get_latest_observations(
        self,
        session_id: str,
        limit: int = 5,
    ) -> list[dict[str, Any]]:
        """Get the most recent observations for a session.

        Args:
            session_id: The session ID.
            limit: Number of observations (default 5).

        Returns:
            List of observation data dicts (newest first).
        """
        return self.get_observations(session_id, limit=limit, offset=0)

    # ------------------------------------------------------------------
    # Entities
    # ------------------------------------------------------------------

    def get_or_create_entity(
        self,
        name: str,
        entity_type: str = "concept",
    ) -> int:
        """Get an entity's ID, creating it if it doesn't exist.

        Entity names are normalised (lowercased, stripped).

        Args:
            name: Entity name (will be normalised).
            entity_type: Entity type (see ``EntityType`` enum).

        Returns:
            The entity ID.
        """
        normalised = name.strip().lower()
        ts = now_iso()

        row = self._conn.execute("SELECT id FROM entities WHERE name = ?", (normalised,)).fetchone()

        if row is not None:
            return row["id"]

        cur = self._conn.execute(
            """INSERT INTO entities (name, entity_type, metadata, created_at, updated_at)
               VALUES (?, ?, '{}', ?, ?)""",
            (normalised, entity_type, ts, ts),
        )
        self._conn.commit()

        entity_id = cur.lastrowid
        if entity_id is None:
            msg = f"Failed to create entity '{normalised}'"
            raise RuntimeError(msg)

        logger.debug(f"Entity created: id={entity_id} name='{normalised}' type={entity_type}")
        return entity_id

    def link_entity_to_observation(
        self,
        observation_id: int,
        entity_id: int,
    ) -> None:
        """Create a many-to-many link between an observation and an entity.

        Args:
            observation_id: The observation ID.
            entity_id: The entity ID.
        """
        try:
            self._conn.execute(
                """INSERT OR IGNORE INTO observation_entities
                   (observation_id, entity_id) VALUES (?, ?)""",
                (observation_id, entity_id),
            )
            self._conn.commit()
        except Exception:
            logger.warning(f"Failed to link entity {entity_id} to observation {observation_id}")

    def _resolve_entity_names(self, entity_ids: list[int]) -> list[str]:
        """Resolve entity IDs to their names."""
        if not entity_ids:
            return []
        placeholders = ",".join("?" for _ in entity_ids)
        rows = self._conn.execute(
            f"SELECT name FROM entities WHERE id IN ({placeholders})",
            entity_ids,
        ).fetchall()
        return [r["name"] for r in rows]

    def _get_entity_ids_for_observation(self, observation_id: int) -> list[int]:
        """Get entity IDs linked to an observation."""
        rows = self._conn.execute(
            "SELECT entity_id FROM observation_entities WHERE observation_id = ?",
            (observation_id,),
        ).fetchall()
        return [r["entity_id"] for r in rows]

    # ------------------------------------------------------------------
    # Search (FTS5 + filters)
    # ------------------------------------------------------------------

    def search_observations(
        self,
        query: str,
        entity: str | None = None,
        agent: str | None = None,
        type: str | None = None,
        session_id: str | None = None,
        max_results: int = 10,
        since: str | None = None,
    ) -> list[dict[str, Any]]:
        """Search observations using FTS5 BM25 ranking with optional filters.

        Args:
            query: Full-text search query (FTS5 syntax).
            entity: Filter by entity name (exact match on normalised name).
            agent: Filter by agent name.
            type: Filter by observation type.
            session_id: Limit to a specific session.
            max_results: Maximum results (default 10, max 50).
            since: ISO timestamp — only observations after this time.

        Returns:
            List of observation dicts with ``score`` added.
        """
        max_results = min(max_results, 50)

        # Step 1: FTS5 search to get matching row IDs with BM25 scores
        fts_query = self._conn.execute(
            """SELECT rowid, rank AS bm25_score
               FROM observations_fts
               WHERE observations_fts MATCH ?
               ORDER BY rank
               LIMIT ?""",
            (query, max_results * 2),  # fetch extra for filtering
        ).fetchall()

        if not fts_query:
            return []

        obs_ids = [r["rowid"] for r in fts_query]
        score_map: dict[int, float] = {r["rowid"]: abs(r["bm25_score"]) for r in fts_query}

        # Step 2: Fetch full observation rows
        placeholders = ",".join("?" for _ in obs_ids)
        sql = f"SELECT * FROM observations WHERE id IN ({placeholders})"
        params: list[Any] = list(obs_ids)

        # Apply optional filters
        filters: list[str] = []
        if entity:
            # Subquery: find observations linked to this entity
            filters.append(
                "id IN (SELECT observation_id FROM observation_entities oe "
                "JOIN entities e ON e.id = oe.entity_id "
                "WHERE e.name = ?)"
            )
            params.append(entity.strip().lower())
        if agent is not None:
            filters.append("agent = ?")
            params.append(agent)
        if type is not None:
            filters.append("type = ?")
            params.append(type)
        if session_id is not None:
            filters.append("session_id = ?")
            params.append(session_id)
        if since is not None:
            filters.append("created_at >= ?")
            params.append(since)

        if filters:
            sql += " AND " + " AND ".join(filters)

        rows = self._conn.execute(sql, params).fetchall()

        # Step 3: Build results with score
        results: list[dict[str, Any]] = []
        for r in rows:
            obs_dict = self._row_to_observation_dict(r)
            obs_id = obs_dict["id"]
            if obs_id is not None:
                obs_dict["score"] = round(score_map.get(obs_id, 0.0), 4)
                results.append(obs_dict)

        # Sort by score descending
        results.sort(key=lambda x: x.get("score", 0), reverse=True)

        return results[:max_results]

    # ------------------------------------------------------------------
    # Summaries
    # ------------------------------------------------------------------

    def add_summary(
        self,
        session_id: str,
        level: int,
        content: str,
        token_count: int = 0,
        parent_id: int | None = None,
    ) -> int:
        """Create a summary for a session.

        Args:
            session_id: The session ID.
            level: Summary level (1, 2, or 3).
            content: Summary text content.
            token_count: Approximate token count.
            parent_id: Optional parent summary ID (for hierarchical compression).

        Returns:
            The new summary ID.
        """
        ts = now_iso()
        cur = self._conn.execute(
            """INSERT INTO summaries
               (session_id, level, content, token_count, parent_id, created_at)
               VALUES (?, ?, ?, ?, ?, ?)""",
            (session_id, level, content, token_count, parent_id, ts),
        )
        self._conn.commit()

        summary_id = cur.lastrowid
        if summary_id is None:
            msg = "Failed to insert summary — lastrowid is None"
            raise RuntimeError(msg)

        logger.info(
            f"Summary {summary_id} created for session {session_id} "
            f"(level={level}, tokens={token_count})"
        )

        return summary_id

    def get_summaries(
        self,
        session_id: str,
        level: int | None = None,
    ) -> list[dict[str, Any]]:
        """Retrieve summaries for a session.

        Args:
            session_id: The session ID.
            level: Optional filter by level.

        Returns:
            List of summary data dicts (newest first).
        """
        if level is not None:
            rows = self._conn.execute(
                """SELECT * FROM summaries
                   WHERE session_id = ? AND level = ?
                   ORDER BY created_at DESC""",
                (session_id, level),
            ).fetchall()
        else:
            rows = self._conn.execute(
                """SELECT * FROM summaries
                   WHERE session_id = ?
                   ORDER BY level, created_at DESC""",
                (session_id,),
            ).fetchall()

        return [self._row_to_summary_dict(r) for r in rows]

    def get_summarization_candidates(
        self,
        session_id: str,
        level: int = 1,
    ) -> list[dict[str, Any]]:
        """Get observations not yet compressed into a summary at the given level.

        Finds the latest summary at this level, then returns observations
        with ``id`` greater than the last observation referenced by that
        summary. If no summary exists, returns all observations.

        Args:
            session_id: The session ID.
            level: Summary level (default 1).

        Returns:
            List of observation dicts eligible for summarization.
        """
        # Find the latest summary at this level
        latest = self._conn.execute(
            """SELECT id, created_at FROM summaries
               WHERE session_id = ? AND level = ?
               ORDER BY id DESC LIMIT 1""",
            (session_id, level),
        ).fetchone()

        if latest is None:
            # No summary yet — return all observations
            return self.get_observations(session_id, limit=1000, offset=0)

        # Use the summary id as a heuristic cutoff: get observations
        # whose id is greater than the last observation that *would have*
        # been included before this summary was created.
        # We find the max observation id that was created before the summary.
        last_obs = self._conn.execute(
            """SELECT COALESCE(MAX(id), 0) AS max_id
               FROM observations
               WHERE session_id = ? AND created_at <= ?""",
            (session_id, latest["created_at"]),
        ).fetchone()

        cutoff_id = last_obs["max_id"] if last_obs else 0
        rows = self._conn.execute(
            """SELECT * FROM observations
               WHERE session_id = ? AND id > ?
               ORDER BY id ASC""",
            (session_id, cutoff_id),
        ).fetchall()

        return [self._row_to_observation_dict(r) for r in rows]

    # ------------------------------------------------------------------
    # Compression
    # ------------------------------------------------------------------

    def compress_observations(
        self,
        age_days: int | None = None,
        max_level: int = 2,
        dry_run: bool = True,
    ) -> dict[str, Any]:
        """Compress old observations using progressive hot/warm/cold levels.

        - **Warm** (level 1): compress ``content`` via Token Juice (max 300 chars)
        - **Cold** (level 2): group by ISO week session, merge into level-3 summary

        Original rows are **not** deleted — ``compression_level`` is updated
        to mark them as compressed. Warm observations remain searchable with
        shortened content.

        Args:
            age_days: If set, only compress observations older than N days.
                      If ``None``, uses defaults (7 for warm, 30 for cold).
            max_level: Maximum level to apply (1=warm, 2=cold). Default 2.
            dry_run: If ``True``, only report what would be done.

        Returns:
            Dict with keys ``observations_warm``, ``observations_cold``,
            ``summaries_created``, ``sessions_affected``, ``dry_run``, ``details``.
        """
        warm_days = age_days if age_days is not None else 7
        cold_days = age_days if age_days is not None else 30

        results: dict[str, Any] = {
            "observations_warm": 0,
            "observations_cold": 0,
            "summaries_created": 0,
            "sessions_affected": set(),
            "dry_run": dry_run,
            "details": [],
        }

        # Phase 1: Warm compression (level 1)
        if max_level >= 1:
            warm_candidates = self._conn.execute(
                """SELECT * FROM observations
                   WHERE compression_level = 0
                   AND created_at < datetime('now', ? || ' days')
                   ORDER BY created_at ASC""",
                (f"-{warm_days}",),
            ).fetchall()

            for row in warm_candidates:
                obs = self._row_to_observation_dict(row)
                obs_id = obs["id"]
                content = obs.get("content", "")

                if len(content) <= 100:
                    # Already short, skip
                    self._conn.execute(
                        "UPDATE observations SET compression_level = 1 WHERE id = ?",
                        (obs_id,),
                    )
                    continue

                compressed = _compress_obs_content(content, max_chars=300)
                if not dry_run:
                    self._conn.execute(
                        """UPDATE observations
                           SET content = ?, compression_level = 1
                           WHERE id = ?""",
                        (compressed, obs_id),
                    )
                results["observations_warm"] += 1
                session_id = obs.get("session_id", "?")
                results["sessions_affected"].add(session_id)
                results["details"].append(
                    f"warm: obs#{obs_id} in {session_id} ({len(content)}→{len(compressed)} chars)"
                )

        # Phase 2: Cold compression (level 2) — group by session + ISO week
        if max_level >= 2:
            cold_candidates = self._conn.execute(
                """SELECT * FROM observations
                   WHERE compression_level IN (0, 1)
                   AND created_at < datetime('now', ? || ' days')
                   ORDER BY session_id, created_at ASC""",
                (f"-{cold_days}",),
            ).fetchall()

            # Group by (session_id, ISO week)
            groups: dict[tuple[str, str], list[dict[str, Any]]] = {}
            for row in cold_candidates:
                obs = self._row_to_observation_dict(row)
                dt = datetime.fromisoformat(obs["created_at"])
                iso_year, iso_week, _ = dt.isocalendar()
                week_key = f"W{iso_week:02d}-{iso_year}"
                groups.setdefault((obs["session_id"], week_key), []).append(obs)

            for (session_id, week_key), obs_list in groups.items():
                count = len(obs_list)
                type_counts: dict[str, int] = {}
                key_topics: list[str] = []
                total_orig_chars = 0

                for o in obs_list:
                    t = o.get("type", "unknown")
                    type_counts[t] = type_counts.get(t, 0) + 1
                    txt = o.get("content", "")
                    total_orig_chars += len(txt)
                    # Extract a brief topic per type
                    snippet = txt[:60].strip()
                    key_topics.append(f"[{t}] {snippet}")

                type_summary_parts = [f"{cnt} {t}" for t, cnt in sorted(type_counts.items())]
                type_summary = ", ".join(type_summary_parts)

                token_disc = sum(o.get("tokens_discovery", 0) for o in obs_list)
                summary_content = (
                    f"Period: {week_key} | Session: {session_id}\n"
                    f"Observations: {count} ({type_summary})\n"
                    f"Token discovery total: {token_disc}\n"
                    f"Key topics:\n" + "\n".join(key_topics[:20])
                )
                approx_tokens = len(summary_content) // 4

                if not dry_run:
                    # Mark all as compressed
                    obs_ids = [o["id"] for o in obs_list if o["id"] is not None]
                    placeholders = ",".join("?" for _ in obs_ids)
                    self._conn.execute(
                        f"UPDATE observations SET compression_level = 2 "
                        f"WHERE id IN ({placeholders})",
                        obs_ids,
                    )
                    # Create level-3 summary
                    self.add_summary(
                        session_id=session_id,
                        level=3,
                        content=summary_content,
                        token_count=approx_tokens,
                    )
                    results["summaries_created"] += 1

                results["observations_cold"] += count
                results["sessions_affected"].add(session_id)
                results["details"].append(
                    f"cold: {count} obs in {session_id}/{week_key} "
                    f"({type_summary}, ~{total_orig_chars}→{approx_tokens * 4} chars)"
                )

        if not dry_run:
            self._conn.commit()

        results["sessions_affected"] = sorted(results["sessions_affected"])
        return results

    # ------------------------------------------------------------------
    # Row → dict converters
    # ------------------------------------------------------------------

    @staticmethod
    def _row_to_session_dict(row: Any) -> dict[str, Any]:  # noqa: ANN401
        """Convert a ``sessions`` table row to a JSON-friendly dict."""

        task_ids_raw = row["task_ids"]
        if isinstance(task_ids_raw, str):
            task_ids = json.loads(task_ids_raw)
        else:
            task_ids = task_ids_raw or []

        metadata_raw = row["metadata"]
        if isinstance(metadata_raw, str):
            metadata = json.loads(metadata_raw)
        else:
            metadata = metadata_raw or {}

        return {
            "id": row["id"],
            "status": row["status"],
            "topic": row["topic"],
            "summary": row["summary"],
            "agent": row["agent"],
            "task_ids": task_ids,
            "token_budget": row["token_budget"],
            "token_discovery": row["token_discovery"],
            "token_read": row["token_read"],
            "started_at": row["started_at"],
            "ended_at": row["ended_at"],
            "updated_at": row["updated_at"],
            "metadata": metadata,
        }

    @staticmethod
    def _row_to_observation_dict(row: Any) -> dict[str, Any]:  # noqa: ANN401
        """Convert an ``observations`` table row to a JSON-friendly dict."""

        entities_raw = row["entities"]
        if isinstance(entities_raw, str):
            entities = json.loads(entities_raw)
        else:
            entities = entities_raw or []

        return {
            "id": row["id"],
            "session_id": row["session_id"],
            "parent_id": row["parent_id"],
            "type": row["type"],
            "agent": row["agent"],
            "content": row["content"],
            "tokens_discovery": row["tokens_discovery"],
            "tokens_read": row["tokens_read"],
            "token_savings": row["token_savings"],
            "entities": entities,
            "handoff_path": row["handoff_path"],
            "task_ref": row["task_ref"],
            "compression_level": row["compression_level"],
            "created_at": row["created_at"],
        }

    @staticmethod
    def _row_to_summary_dict(row: Any) -> dict[str, Any]:  # noqa: ANN401
        """Convert a ``summaries`` table row to a JSON-friendly dict."""

        return {
            "id": row["id"],
            "session_id": row["session_id"],
            "level": row["level"],
            "parent_id": row["parent_id"],
            "content": row["content"],
            "token_count": row["token_count"],
            "created_at": row["created_at"],
        }
