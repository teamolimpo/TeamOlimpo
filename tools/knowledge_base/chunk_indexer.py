"""Index chunks into SQLite + FTS5.

CLI with three subcommands::

    # Rebuild the full index from scratch
    python -m tools.knowledge_base.chunk_indexer rebuild

    # Incremental update (SHA256 change detection)
    python -m tools.knowledge_base.chunk_indexer update

    # Remove orphan chunks (files no longer on disk)
    python -m tools.knowledge_base.chunk_indexer clean

Database location
-----------------
``lib/data/chunks.db`` (resolved via ``tools.common.paths``).

Schema
------
- **chunks** — every chunk row with metadata.
- **chunks_fts** — FTS5 virtual table for full-text search (content-synced).
- **file_state** — tracks per-file SHA256 hash for change detection.
"""

from __future__ import annotations

import hashlib
import json
import re
import sqlite3
import sys
import time
from pathlib import Path
from typing import Any

import typer
from loguru import logger

from tools.common.paths import resolve_absolute, resolve_relative
from tools.knowledge_base.entity_extractor import (
    clean_orphan_entities,
    ensure_entities_table,
    extract_entities,
    index_all_entities,
    load_dictionary,
)
from tools.knowledge_base.heading_chunker import chunk_markdown
from tools.knowledge_base.rrf_fusion import fuse_rrf
from tools.knowledge_base.vector_indexer import (
    clean_orphan_vectors,
    ensure_vec_table,
    index_all_embeddings,
)

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

DB_PATH = resolve_absolute("Library", "System", "Poros", "synapsis.db")
DICTIONARY_PATH = Path(__file__).resolve().parent / "entity_dictionary.yaml"

# Relative paths to scan for .md files
SEARCH_REL_PATHS: list[str] = [
    "Library/Wiki/",
    "lib/documents/",
    "Library/Handoff/",
    "lib/emails/",
    "lib/projects/",
    "Inbox/",
]

SCHEMA_SQL = """
CREATE TABLE IF NOT EXISTS chunks (
    id TEXT PRIMARY KEY,
    file_path TEXT NOT NULL,
    file_hash TEXT NOT NULL,
    heading_path TEXT NOT NULL,
    heading_level INTEGER NOT NULL DEFAULT 2,
    content TEXT NOT NULL,
    frontmatter TEXT,
    token_count INTEGER,
    line_start INTEGER,
    line_end INTEGER,
    created_at TEXT DEFAULT (datetime('now')),
    updated_at TEXT DEFAULT (datetime('now'))
);

CREATE VIRTUAL TABLE IF NOT EXISTS chunks_fts USING fts5(
    content, heading_path, file_path,
    content='chunks', content_rowid='rowid'
);

CREATE TABLE IF NOT EXISTS file_state (
    file_path TEXT PRIMARY KEY,
    file_hash TEXT NOT NULL,
    chunk_count INTEGER NOT NULL DEFAULT 0,
    last_indexed_at TEXT DEFAULT (datetime('now'))
);
"""

TRIGGERS_SQL = """
CREATE TRIGGER IF NOT EXISTS chunks_ai AFTER INSERT ON chunks
BEGIN
    INSERT INTO chunks_fts(rowid, content, heading_path, file_path)
    VALUES (new.rowid, new.content, new.heading_path, new.file_path);
END;

CREATE TRIGGER IF NOT EXISTS chunks_ad AFTER DELETE ON chunks
BEGIN
    INSERT INTO chunks_fts(chunks_fts, rowid, content, heading_path, file_path)
    VALUES ('delete', old.rowid, old.content, old.heading_path, old.file_path);
END;

CREATE TRIGGER IF NOT EXISTS chunks_au AFTER UPDATE ON chunks
BEGIN
    INSERT INTO chunks_fts(chunks_fts, rowid, content, heading_path, file_path)
    VALUES ('delete', old.rowid, old.content, old.heading_path, old.file_path);
    INSERT INTO chunks_fts(rowid, content, heading_path, file_path)
    VALUES (new.rowid, new.content, new.heading_path, new.file_path);
END;
"""

# ---------------------------------------------------------------------------
# App
# ---------------------------------------------------------------------------

app = typer.Typer(
    name="chunk_indexer",
    help="Index .md vault files into SQLite + FTS5 chunks.",
    no_args_is_help=True,
)


# ---------------------------------------------------------------------------
# Database helpers
# ---------------------------------------------------------------------------


def _get_conn(conn: sqlite3.Connection | None = None) -> sqlite3.Connection:
    """Open (or reuse) the chunks database and ensure schema exists.

    If *conn* is provided, returns it as-is (caller manages its lifecycle).
    Otherwise opens synapsis.db directly and ensures schema + triggers exist.
    """
    if conn is not None:
        return conn

    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    new_conn = sqlite3.connect(str(DB_PATH))
    new_conn.execute("PRAGMA journal_mode=WAL;")
    new_conn.execute("PRAGMA synchronous=OFF;")
    new_conn.execute("PRAGMA cache_size=-64000;")  # 64 MB cache
    new_conn.row_factory = sqlite3.Row

    # Create tables + triggers
    new_conn.executescript(SCHEMA_SQL)
    new_conn.executescript(TRIGGERS_SQL)
    new_conn.commit()

    # Ensure entity table exists (created lazily, no-op if already present)
    ensure_entities_table(new_conn)

    return new_conn


def _chunk_id(file_path: str, heading_path: str, content: str) -> str:
    """Compute a deterministic chunk ID."""
    raw = f"{file_path}||{heading_path}||{content}"
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()[:16]


def _collect_md_files() -> list[Path]:
    """Collect all ``.md`` files from configured search paths."""
    files: list[Path] = []
    for rel in SEARCH_REL_PATHS:
        base = resolve_relative(rel)
        if not base.is_dir():
            logger.warning(f"Search path not found, skipping: {base}")
            continue
        for p in sorted(base.rglob("*.md")):
            if p.is_file():
                files.append(p)
    logger.info(f"Collected {len(files)} .md files for indexing")
    return files


# ---------------------------------------------------------------------------
# Indexing logic
# ---------------------------------------------------------------------------


def _index_file(
    conn: sqlite3.Connection,
    file_path: Path,
    rel_path: str,
    file_hash: str,
) -> int:
    """Chunk a single file and insert into database.

    Always records the file in ``file_state`` for change detection,
    even when the file produces zero chunks.

    Returns the number of chunks inserted.
    """
    try:
        text = file_path.read_text(encoding="utf-8", errors="replace")
    except OSError as e:
        logger.error(f"Cannot read {rel_path}: {e}")
        return 0

    chunks = chunk_markdown(text, rel_path)

    # ── Skip deprecated/superseded files ──────────────────────────────
    if chunks and chunks[0].frontmatter.get("lifecycle") in (
        "superseded",
        "deprecated",
        "archived",
    ):
        cur = conn.cursor()
        cur.execute("DELETE FROM chunks WHERE file_path = ?", (rel_path,))
        cur.execute("DELETE FROM file_state WHERE file_path = ?", (rel_path,))
        conn.commit()
        logger.info(f"Skipped ({chunks[0].frontmatter['lifecycle']}): {rel_path}")
        return 0
    # ──────────────────────────────────────────────────────────────────

    cur = conn.cursor()
    inserted = 0
    for chunk in chunks:
        cid = _chunk_id(chunk.file_path, chunk.heading_path, chunk.content)
        # Serialise frontmatter as JSON text
        fm_json = json.dumps(chunk.frontmatter, ensure_ascii=False) if chunk.frontmatter else "{}"
        try:
            cur.execute(
                """INSERT OR REPLACE INTO chunks
                (id, file_path, file_hash, heading_path, heading_level,
                 content, frontmatter, token_count, line_start, line_end)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                (
                    cid,
                    chunk.file_path,
                    chunk.file_hash,
                    chunk.heading_path,
                    chunk.heading_level,
                    chunk.content,
                    fm_json,
                    chunk.token_count,
                    chunk.start_line,
                    chunk.end_line,
                ),
            )
            inserted += 1
        except sqlite3.Error as e:
            logger.error(f"Failed to insert chunk {cid}: {e}")

    # Update file_state (always — even for 0-chunk files, for change detection)
    cur.execute(
        """INSERT OR REPLACE INTO file_state
        (file_path, file_hash, chunk_count, last_indexed_at)
        VALUES (?, ?, ?, datetime('now'))""",
        (rel_path, file_hash, inserted),
    )
    conn.commit()
    return inserted


def _file_hash(file_path: Path) -> str:
    """Compute SHA256 of a file's content."""
    try:
        data = file_path.read_bytes()
        return hashlib.sha256(data).hexdigest()
    except OSError:
        return ""


# ---------------------------------------------------------------------------
# CLI commands
# ---------------------------------------------------------------------------


@app.command()
def rebuild(
    verbose: bool = typer.Option(False, "--verbose", "-v", help="Verbose logging."),
    conn: sqlite3.Connection | None = None,
) -> None:
    """Scan ALL .md files, chunk, and (re)build the index from scratch.

    Drops and recreates all tables for a clean state.
    If *conn* is provided, it is used directly and NOT closed.
    """
    _setup_logging(verbose)
    logger.info("Rebuilding full index — clearing existing data...")

    own_conn = conn is None  # Do we manage the connection lifecycle?
    conn = _get_conn(conn)

    conn.executescript("""
        DROP TABLE IF EXISTS chunks_fts;
        DROP TABLE IF EXISTS chunks;
        DROP TABLE IF EXISTS file_state;
    """)
    conn.commit()

    # Re-create schema tables
    conn.executescript(SCHEMA_SQL)
    conn.executescript(TRIGGERS_SQL)
    conn.commit()

    files = _collect_md_files()
    total_chunks = 0
    total_errors = 0
    start_ts = time.time()

    for fp in files:
        try:
            rel = str(fp.relative_to(resolve_relative(".")))
        except ValueError:
            rel = str(fp)
        fh = _file_hash(fp)
        if not fh:
            total_errors += 1
            continue
        n = _index_file(conn, fp, rel, fh)
        total_chunks += n
        if verbose and n > 0:
            logger.debug(f"  {rel} → {n} chunks")

    elapsed = time.time() - start_ts
    logger.info(
        f"Rebuild complete: {len(files)} files, "
        f"{total_chunks} chunks, {total_errors} errors "
        f"in {elapsed:.1f}s"
    )

    # Generate embeddings
    logger.info("Generating embeddings for all chunks...")
    ensure_vec_table(conn)
    n_emb = index_all_embeddings(conn)
    logger.info(f"Indexed {n_emb} embeddings")

    # Extract entities
    logger.info("Extracting entities for all chunks...")
    dictionary = load_dictionary(DICTIONARY_PATH)
    ensure_entities_table(conn)
    n_ent = index_all_entities(conn, dictionary)
    logger.info(f"Indexed {n_ent} entities")

    if own_conn:
        conn.close()


@app.command()
def update(
    verbose: bool = typer.Option(False, "--verbose", "-v", help="Verbose logging."),
    dry_run: bool = typer.Option(
        False,
        "--dry-run",
        "-n",
        help="Show what would change without doing it.",
    ),
    conn: sqlite3.Connection | None = None,
) -> None:
    """Incremental update: re-chunk only files whose SHA256 changed.

    Uses ``file_state.file_hash`` for change detection.
    If *conn* is provided, it is used directly and NOT closed.
    """
    _setup_logging(verbose)
    own_conn = conn is None
    conn = _get_conn(conn)
    cur = conn.cursor()

    def _maybe_close() -> None:
        if own_conn:
            conn.close()

    files = _collect_md_files()
    changed: list[tuple[Path, str, str]] = []
    removed: list[str] = []
    added = 0

    # Check which files changed
    for fp in files:
        try:
            rel = str(fp.relative_to(resolve_relative(".")))
        except ValueError:
            rel = str(fp)
        fh = _file_hash(fp)
        if not fh:
            continue

        row = cur.execute("SELECT file_hash FROM file_state WHERE file_path = ?", (rel,)).fetchone()
        if row is None or row["file_hash"] != fh:
            changed.append((fp, rel, fh))

    # Check for orphaned file_state entries
    all_rel = {str(fp.relative_to(resolve_relative("."))) for fp in files}
    orphan_rows = cur.execute("SELECT file_path FROM file_state").fetchall()
    for row in orphan_rows:
        if row["file_path"] not in all_rel:
            removed.append(row["file_path"])

    if dry_run:
        logger.info(f"DRY-RUN: {len(changed)} files changed, {len(removed)} orphans to clean")
        for _fp, rel, _ in changed:
            logger.info(f"  would update: {rel}")
        for r in removed:
            logger.info(f"  would remove: {r}")
        _maybe_close()
        return

    # Process changed files
    start_ts = time.time()
    for fp, rel, fh in changed:
        # Delete old chunks
        cur.execute("DELETE FROM chunks WHERE file_path = ?", (rel,))
        n = _index_file(conn, fp, rel, fh)
        added += n
        if verbose:
            logger.debug(f"  {rel} → {n} chunks")

    # Clean orphans
    for r in removed:
        cur.execute("DELETE FROM chunks WHERE file_path = ?", (r,))
        cur.execute("DELETE FROM file_state WHERE file_path = ?", (r,))
        if verbose:
            logger.debug(f"  removed orphan: {r}")

    elapsed = time.time() - start_ts
    conn.commit()

    # Clean orphan vectors, index embeddings, and entities for new chunks
    ensure_vec_table(conn)
    n_cleaned = clean_orphan_vectors(conn)
    n_emb = index_all_embeddings(conn)

    dictionary = load_dictionary(DICTIONARY_PATH)
    ensure_entities_table(conn)
    n_ent_cleaned = clean_orphan_entities(conn)
    n_ent = index_all_entities(conn, dictionary)
    _maybe_close()

    logger.info(
        f"Update complete: {len(changed)} re-indexed (+{added} chunks), "
        f"{len(removed)} orphans cleaned, {n_cleaned} orphan vectors, "
        f"+{n_emb} embeddings, {n_ent_cleaned} orphan entities, "
        f"+{n_ent} entities in {elapsed:.1f}s"
    )


@app.command()
def clean(
    verbose: bool = typer.Option(False, "--verbose", "-v", help="Verbose logging."),
    dry_run: bool = typer.Option(
        False,
        "--dry-run",
        "-n",
        help="Show what would be removed without doing it.",
    ),
    conn: sqlite3.Connection | None = None,
) -> None:
    """Remove orphan chunks (files no longer on disk).

    If *conn* is provided, it is used directly and NOT closed.
    """
    _setup_logging(verbose)
    own_conn = conn is None
    conn = _get_conn(conn)
    cur = conn.cursor()

    def _maybe_close() -> None:
        if own_conn:
            conn.close()

    # Collect all file_paths that exist on disk
    files = _collect_md_files()
    on_disk = set()
    for fp in files:
        try:
            on_disk.add(str(fp.relative_to(resolve_relative("."))))
        except ValueError:
            on_disk.add(str(fp))

    # Find orphans in db
    db_files = cur.execute("SELECT DISTINCT file_path FROM chunks").fetchall()
    orphans = [r["file_path"] for r in db_files if r["file_path"] not in on_disk]

    if not orphans:
        logger.info("No orphans found.")
        _maybe_close()
        return

    if dry_run:
        logger.info(f"DRY-RUN: would remove {len(orphans)} orphan file entries")
        for o in orphans:
            logger.info(f"  {o}")
        _maybe_close()
        return

    # Delete orphans
    for o in orphans:
        cur.execute("DELETE FROM chunks WHERE file_path = ?", (o,))
        cur.execute("DELETE FROM file_state WHERE file_path = ?", (o,))

    conn.commit()
    _maybe_close()
    logger.info(f"Cleaned {len(orphans)} orphan file entries.")


@app.command()
def clean_vectors(
    verbose: bool = typer.Option(False, "--verbose", "-v", help="Verbose logging."),
    dry_run: bool = typer.Option(
        False,
        "--dry-run",
        "-n",
        help="Show what would be removed without doing it.",
    ),
) -> None:
    """Remove orphan vectors (chunk_ids no longer in chunks table)."""
    _setup_logging(verbose)
    conn = _get_conn()
    ensure_vec_table(conn)

    if dry_run:
        cur = conn.cursor()
        orphans = cur.execute(
            """SELECT v.chunk_id
               FROM chunks_vec v
               LEFT JOIN chunks c ON v.chunk_id = c.id
               WHERE c.id IS NULL"""
        ).fetchall()
        logger.info(f"DRY-RUN: {len(orphans)} orphan vectors would be removed")
        for o in orphans:
            logger.info(f"  {o['chunk_id']}")
        conn.close()
        return

    n = clean_orphan_vectors(conn)
    logger.info(f"Cleaned {n} orphan vectors")
    conn.close()


@app.command()
def rebuild_entities(
    verbose: bool = typer.Option(False, "--verbose", "-v", help="Verbose logging."),
) -> None:
    """Extract entities for ALL chunks using the dictionary + pattern pipeline.

    Creates the ``chunk_entities`` table if missing, then processes every
    chunk that has no extracted entities yet (the LEFT JOIN ensures
    idempotency).
    """
    _setup_logging(verbose)
    conn = _get_conn()
    ensure_entities_table(conn)
    dictionary = load_dictionary(DICTIONARY_PATH)
    start_ts = time.time()
    n = index_all_entities(conn, dictionary)
    elapsed = time.time() - start_ts
    logger.info(f"Rebuild entities complete: {n} entities indexed in {elapsed:.1f}s")
    conn.close()


@app.command()
def update_entities(
    verbose: bool = typer.Option(False, "--verbose", "-v", help="Verbose logging."),
) -> None:
    """Extract entities for NEW chunks only (incremental).

    Processes only chunks that don't yet have any entity rows in
    ``chunk_entities`` (LEFT JOIN IS NULL). Also cleans orphan entities.
    """
    _setup_logging(verbose)
    conn = _get_conn()
    ensure_entities_table(conn)
    dictionary = load_dictionary(DICTIONARY_PATH)
    start_ts = time.time()

    n_orphans = clean_orphan_entities(conn)
    n = index_all_entities(conn, dictionary)
    elapsed = time.time() - start_ts

    logger.info(
        f"Update entities complete: {n_orphans} orphans cleaned, {n} new entities in {elapsed:.1f}s"
    )
    conn.close()


@app.command()
def clean_entities(
    verbose: bool = typer.Option(False, "--verbose", "-v", help="Verbose logging."),
    dry_run: bool = typer.Option(
        False,
        "--dry-run",
        "-n",
        help="Show what would be removed without doing it.",
    ),
) -> None:
    """Remove orphan entity rows (chunk_ids no longer in ``chunks`` table)."""
    _setup_logging(verbose)
    conn = _get_conn()
    ensure_entities_table(conn)

    if dry_run:
        cur = conn.cursor()
        orphans = cur.execute(
            """SELECT e.id, e.chunk_id, e.entity_text
               FROM chunk_entities e
               LEFT JOIN chunks c ON c.id = e.chunk_id
               WHERE c.id IS NULL"""
        ).fetchall()
        logger.info(f"DRY-RUN: {len(orphans)} orphan entity rows would be removed")
        for o in orphans[:20]:
            logger.info(f"  {o['chunk_id']}: {o['entity_text']}")
        if len(orphans) > 20:
            logger.info(f"  ... and {len(orphans) - 20} more")
        conn.close()
        return

    n = clean_orphan_entities(conn)
    logger.info(f"Cleaned {n} orphan entity rows")
    conn.close()


# ---------------------------------------------------------------------------
# Search helpers (used by server.py)
# ---------------------------------------------------------------------------


def search_chunks(
    query: str,
    limit: int = 15,
    context_chunks: int = 0,
) -> list[dict[str, Any]]:
    """Search the chunks index via FTS5.

    Parameters
    ----------
    query : str
        FTS5 query string (e.g. ``"MCP"``, ``"MCP AND server"``).
    limit : int
        Maximum results to return.
    context_chunks : int
        Number of adjacent chunks to include before/after each match.

    Returns
    -------
    list[dict]
        List of result dicts with keys: ``id``, ``file_path``, ``heading_path``,
        ``heading_level``, ``content``, ``token_count``, ``line_start``,
        ``line_end``, ``frontmatter``, ``rank``, plus optionally ``context``
        (list of adjacent chunks) when *context_chunks* > 0.

    Returns an empty list if the index is missing or empty.
    """
    db_path = DB_PATH
    if not db_path.exists():
        logger.warning("Chunks index not found — call 'rebuild' first")
        return []

    try:
        conn = sqlite3.connect(str(db_path))
        conn.row_factory = sqlite3.Row
        cur = conn.cursor()

        # Verify FTS table exists
        try:
            cur.execute("SELECT count(*) FROM chunks_fts")
        except sqlite3.OperationalError:
            conn.close()
            return []

        # Sanitize query for FTS5: replace intra-word hyphens with spaces
        # (unicode61 tokenizer splits on hyphens; FTS5 query parser can
        #  misinterpret hyphenated terms as column:expression syntax)
        safe_query = re.sub(r"(?<=\w)-(?=\w)", " ", query)

        rows = cur.execute(
            """SELECT c.id, c.file_path, c.heading_path, c.heading_level,
                      c.content, c.token_count, c.line_start, c.line_end,
                      c.frontmatter, rank
               FROM chunks_fts
               JOIN chunks c ON c.rowid = chunks_fts.rowid
               WHERE chunks_fts MATCH ?
               ORDER BY rank
               LIMIT ?""",
            (safe_query, limit),
        ).fetchall()

        results: list[dict[str, Any]] = []
        for row in rows:
            res = dict(row)
            try:
                res["frontmatter"] = json.loads(res.get("frontmatter") or "{}")
            except (json.JSONDecodeError, TypeError):
                res["frontmatter"] = {}
            results.append(res)

        # -- Context chunks --
        if context_chunks > 0 and results:
            results = _attach_context(results, conn, context_chunks)

        conn.close()
        return results

    except sqlite3.Error as e:
        logger.error(f"FTS5 search error: {e}")
        return []


def _attach_context(
    results: list[dict[str, Any]],
    conn: sqlite3.Connection,
    n: int,
) -> list[dict[str, Any]]:
    """Attach *n* preceding/succeeding chunks to each result."""
    cur = conn.cursor()
    for res in results:
        file_path = res["file_path"]
        line_start = res["line_start"]

        # Previous chunks (same file, lower line_start)
        prev_rows = cur.execute(
            """SELECT content, heading_path, line_start, line_end
               FROM chunks
               WHERE file_path = ? AND line_start < ?
               ORDER BY line_start DESC
               LIMIT ?""",
            (file_path, line_start, n),
        ).fetchall()

        # Next chunks
        next_rows = cur.execute(
            """SELECT content, heading_path, line_start, line_end
               FROM chunks
               WHERE file_path = ? AND line_start > ?
               ORDER BY line_start ASC
               LIMIT ?""",
            (file_path, line_start, n),
        ).fetchall()

        res["context"] = {
            "before": [dict(r) for r in reversed(prev_rows)],
            "after": [dict(r) for r in next_rows],
        }

    return results


# ---------------------------------------------------------------------------
# Embedding search + hybrid (BM25 + RRF)
# ---------------------------------------------------------------------------


def _embedding_search(
    query: str,
    limit: int = 15,
) -> list[dict[str, Any]]:
    """Search via embedding KNN on ``chunks_vec``.

    Encodes the query with SentenceTransformer, then runs a KNN query
    against the sqlite-vec virtual table, joining with ``chunks`` for
    metadata.

    Returns results in the same format as ``search_chunks()``, with
    ``rank`` set to the cosine distance.

    Returns an empty list if ``chunks_vec`` does not exist.
    """
    db_path = DB_PATH
    if not db_path.exists():
        return []

    try:
        conn = sqlite3.connect(str(db_path))
        conn.row_factory = sqlite3.Row

        # Check vec table exists
        try:
            ensure_vec_table(conn)
        except sqlite3.OperationalError:
            conn.close()
            return []

        # Get query embedding
        from tools.knowledge_base.vector_indexer import get_model

        model = get_model()
        query_emb = model.encode([query], normalize_embeddings=True)[0]

        cur = conn.cursor()
        rows = cur.execute(
            """SELECT c.id, c.file_path, c.heading_path, c.heading_level,
                      c.content, c.token_count, c.line_start, c.line_end,
                      c.frontmatter, v.distance
               FROM chunks_vec v
               LEFT JOIN chunks c ON c.id = v.chunk_id
               WHERE v.embedding MATCH ? AND k = ?
               ORDER BY v.distance""",
            (query_emb.astype("float32").tobytes(), limit),
        ).fetchall()

        results: list[dict[str, Any]] = []
        for row in rows:
            res = dict(row)
            try:
                res["frontmatter"] = json.loads(res.get("frontmatter") or "{}")
            except (json.JSONDecodeError, TypeError):
                res["frontmatter"] = {}
            # Keep distance (embedding similarity) and add rank alias
            res["distance"] = res.get("distance", 0.0)
            results.append(res)

        conn.close()
        return results

    except sqlite3.Error as e:
        logger.error(f"Embedding search error: {e}")
        return []


# ---------------------------------------------------------------------------
# Entity search
# ---------------------------------------------------------------------------


def entity_search(
    query: str,
    limit: int = 15,
    dictionary: dict | None = None,
) -> list[dict[str, Any]]:
    """Search chunks by entity matching.

    Extracts entities from the query using the full 2-level pipeline
    (dictionary + patterns), then matches against ``chunk_entities.entity_text``
    via LIKE queries. Results are ranked by the number of matching entities
    per chunk.

    Parameters
    ----------
    query : str
        Search query. Entities are extracted via pipeline (dict + patterns).
    limit : int
        Maximum results to return (default 15).
    dictionary : dict | None
        Optional entity dictionary for Level 1 matching. Uses the default
        ``entity_dictionary.yaml`` when ``None``.

    Returns
    -------
    list[dict]
        Ranked list of chunk dicts (same schema as ``search_chunks``),
        with ``rank`` set to the negative entity-match count.
        Empty list when no entities are found in *query*.
    """
    # Load default dictionary if none provided
    if dictionary is None:
        try:
            dictionary = load_dictionary(DICTIONARY_PATH)
        except (FileNotFoundError, ValueError):
            dictionary = None

    # Extract entities from query (full pipeline: dict + patterns)
    query_entities = extract_entities(query, dictionary)
    if not query_entities:
        return []

    db_path = DB_PATH
    if not db_path.exists():
        return []

    conn = sqlite3.connect(str(db_path))
    conn.row_factory = sqlite3.Row

    # Build LIKE conditions — one per extracted entity
    conditions: list[str] = []
    params: list[str] = []
    for ent in query_entities:
        conditions.append("LOWER(entity_text) LIKE ?")
        params.append(f"%{ent['entity_text'].lower()}%")

    if not conditions:
        conn.close()
        return []

    where_clause = " OR ".join(conditions)

    try:
        cur = conn.cursor()
        rows = cur.execute(
            f"""SELECT c.id, c.file_path, c.heading_path, c.heading_level,
                       c.content, c.token_count, c.line_start, c.line_end,
                       c.frontmatter, COUNT(DISTINCT e.entity_text) AS entity_matches
                FROM chunk_entities e
                JOIN chunks c ON c.id = e.chunk_id
                WHERE ({where_clause})
                GROUP BY c.id
                ORDER BY entity_matches DESC, c.id
                LIMIT ?""",
            (*params, limit),
        ).fetchall()

        results: list[dict[str, Any]] = []
        for row in rows:
            res = dict(row)
            try:
                res["frontmatter"] = json.loads(res.get("frontmatter") or "{}")
            except (json.JSONDecodeError, TypeError):
                res["frontmatter"] = {}
            # Negative rank so that more matches = higher (less negative) rank,
            # compatible with existing rank semantics (lower = better)
            res["rank"] = -res.pop("entity_matches")
            results.append(res)

        conn.close()
        return results

    except sqlite3.Error as e:
        conn.close()
        logger.error(f"Entity search error: {e}")
        return []


def hybrid_search(
    query: str,
    limit: int = 15,
    mode: str = "auto",
    k: int = 60,
) -> list[dict[str, Any]]:
    """Multi-signal search: BM25 + embedding fused with RRF.

    Parameters
    ----------
    query : str
        Search query (used for both FTS5 match and embedding).
    limit : int
        Maximum results to return.
    mode : str
        ``"bm25"`` → FTS5 only (same as ``search_chunks``).
        ``"embedding"`` → embedding search only.
        ``"entity"`` → entity matching only (no BM25/embedding).
        ``"hybrid"`` → BM25 + embedding + entity, fused with RRF.
        ``"auto"`` → hybrid if vector index exists and entity table has
        data; falls back to simpler modes otherwise (default).
    k : int
        RRF constant (default 60).

    Returns
    -------
    list[dict]
        Same format as ``search_chunks()``, with added ``_rrf_score``
        when multiple signals are fused.
    """
    if mode == "bm25":
        return search_chunks(query, limit=limit)

    if mode == "embedding":
        return _embedding_search(query, limit=limit)

    if mode == "entity":
        return entity_search(query, limit=limit)

    # mode == "hybrid" or "auto" — fuse up to 3 signals
    bm25_results = search_chunks(query, limit=limit)
    embedding_results = _embedding_search(query, limit=limit)
    entity_results = entity_search(query, limit=limit)

    # In "auto" mode, skip unavailable or empty signals
    if mode == "auto":
        if not embedding_results and not entity_results:
            return bm25_results

    signals: dict[str, list[dict[str, Any]]] = {}
    if bm25_results:
        signals["bm25"] = bm25_results
    if embedding_results:
        signals["embedding"] = embedding_results
    if entity_results:
        signals["entity"] = entity_results

    if len(signals) < 2:
        return next(iter(signals.values())) if signals else []

    fused = fuse_rrf(signals, k=k)

    # Deduplicate and rank-limit — already sorted by RRF score
    seen: set[str] = set()
    final: list[dict[str, Any]] = []
    for doc in fused:
        if doc["id"] not in seen:
            seen.add(doc["id"])
            final.append(doc)
        if len(final) >= limit:
            break

    return final


# ---------------------------------------------------------------------------
# Logging setup
# ---------------------------------------------------------------------------


def _setup_logging(verbose: bool) -> None:
    """Configure loguru: WARNING by default, DEBUG with --verbose."""
    logger.remove()
    level = "DEBUG" if verbose else "INFO"
    logger.add(sys.stderr, level=level, format="<level>{level}</level>: {message}")


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------


if __name__ == "__main__":
    app()
