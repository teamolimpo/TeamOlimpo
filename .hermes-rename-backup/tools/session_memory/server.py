"""MCP server: expose 6 ``session_*`` tools for session memory management.

Usage::

    uv run python -m tools.session_memory.server

The server listens on stdio (MCP stdio transport). An MCP client (e.g.
``opencode.json``'s ``mcp`` section) connects to it and calls the
``session_*`` tools.

Tools
-----
- session_init — Initialize or resume a session with 3-layer context.
- session_observe — Log an observation to the timeline.
- session_context — Retrieve progressive context (3-layer disclosure).
- session_recall — FTS5 search across sessions with entity/type filters.
- session_summarize — Compress observations into a summary.
- session_compress — Compress old observations (hot/warm/cold).
"""

from __future__ import annotations

import json
import time
from typing import Any

from loguru import logger

from tools.session_memory.store import SessionStore

# ---------------------------------------------------------------------------
# MCP SDK — graceful fallback if missing
# ---------------------------------------------------------------------------

try:
    from mcp.server.fastmcp import FastMCP

    mcp = FastMCP("session_memory")
    MCP_AVAILABLE = True
except ImportError:
    MCP_AVAILABLE = False

# ---------------------------------------------------------------------------
# Backing store (singleton-like, created on first use)
# ---------------------------------------------------------------------------

_store: SessionStore | None = None


def _get_store() -> SessionStore:
    """Return the global ``SessionStore`` instance, creating it if needed."""
    global _store  # noqa: PLW0603
    if _store is None:
        _store = SessionStore()
    return _store


# ---------------------------------------------------------------------------
# Tool 1: session_init
# ---------------------------------------------------------------------------


@mcp.tool()
def session_init(
    topic: str,
    task_ids: list[str] | None = None,
    resume: bool = True,
    token_budget: int = 2000,
) -> str:
    """Initialize a new session or resume the most recent active one.

    If ``resume=True``, looks for the last session with status ``active`` or
    ``interrupted`` and resumes it. Otherwise creates a fresh session.

    Returns a 3-layer context pack for injection into the agent's prompt.

    Parameters
    ----------
    topic : str
        Main topic for this session (e.g. "Fase 1.7 — Auto-Capture").
    task_ids : list[str] | None
        Associated task IDs (e.g. ["T-FASE-007"]).
    resume : bool
        If True, try to resume the last non-completed session (default True).
    token_budget : int
        Maximum token budget for context (default 2000).
    """
    logger.info(
        f"session_init: topic='{topic[:60]}', task_ids={task_ids}, "
        f"resume={resume}, budget={token_budget}"
    )

    if not topic or not topic.strip():
        return json.dumps({"error": "Il parametro 'topic' è obbligatorio."})

    store = _get_store()
    session: dict[str, Any] | None = None
    is_resumed = False

    # Try to resume
    if resume:
        session = store.get_active_session()
        if session is not None:
            session_id = session["id"]
            logger.info(f"Resuming active session {session_id}")
            # Update topic and task_ids
            existing_ids: list[str] = session.get("task_ids", [])
            new_ids = task_ids or []
            merged_ids = list(dict.fromkeys(existing_ids + new_ids))  # unique
            store.update_session(
                session_id,
                topic=topic.strip(),
                task_ids=json.dumps(merged_ids),
            )
            session["topic"] = topic.strip()
            session["task_ids"] = merged_ids
            is_resumed = True

    # Create new if not resumed
    if session is None:
        result = store.create_session(
            topic=topic.strip(),
            task_ids=task_ids,
            token_budget=token_budget,
        )
        session = result
        session_id = session["id"]
        is_resumed = False

    session_id = session["id"]
    metrics = store.get_session_metrics(session_id)
    observations = store.get_latest_observations(session_id, limit=5)

    # Build 3-layer context
    layer1 = _build_layer1(session, metrics)
    layer2 = _build_layer2(observations)
    layer3 = _build_layer3(observations)

    result = {
        "session_id": session_id,
        "context": {
            "layer1": layer1,
            "layer2": layer2,
            "layer3": layer3,
        },
        "observations_count": metrics["observations_count"],
        "is_resumed": is_resumed,
        "token_budget": session.get("token_budget", token_budget),
    }

    logger.info(
        f"Session {'resumed' if is_resumed else 'created'}: "
        f"{session_id} ({metrics['observations_count']} observations)"
    )

    return json.dumps(result)


# ---------------------------------------------------------------------------
# Tool 2: session_observe
# ---------------------------------------------------------------------------


@mcp.tool()
def session_observe(
    session_id: str,
    type: str,
    content: str,
    agent: str = "Hermes",
    entities: list[str] | None = None,
    handoff_path: str | None = None,
    task_ref: str | None = None,
    tokens_discovery: int = 0,
    tokens_read: int = 0,
    parent_id: int | None = None,
) -> str:
    """Log an observation to the session timeline.

    Writes the observation to SQLite, links any provided entities, and
    optionally logs an event to the taskmanager (best-effort, via MCP
    if available).

    Parameters
    ----------
    session_id : str
        The target session ID.
    type : str
        Observation type: ``decision``, ``delegation``, ``result``,
        ``note``, ``handoff``, ``user_message``, ``system``.
    content : str
        The observation text (max ~1000 chars recommended).
    agent : str
        Agent that produced the observation (default ``"Hermes"``).
    entities : list[str] | None
        Entity names to extract and link (optional).
    handoff_path : str | None
        Handoff file path (optional, for ``type=handoff``).
    task_ref : str | None
        Task ID reference (optional; triggers a best-effort log on taskmanager).
    tokens_discovery : int
        Token count for generating the observation (optional).
    tokens_read : int
        Token count for reading the observation (optional).
    parent_id : int | None
        Parent observation ID for threading (optional).
    """
    logger.info(
        f"session_observe: session={session_id}, type={type}, "
        f"agent={agent}, entities={entities}, task_ref={task_ref}"
    )

    # --- Validate ---
    valid_types = {
        "decision",
        "delegation",
        "result",
        "note",
        "handoff",
        "user_message",
        "system",
    }
    if type not in valid_types:
        return json.dumps(
            {"error": f"Tipo '{type}' non valido. Usa uno di: {', '.join(sorted(valid_types))}."}
        )

    if not content or not content.strip():
        return json.dumps({"error": "Il parametro 'content' è obbligatorio."})

    store = _get_store()

    # Verify session exists
    session = store.get_session(session_id)
    if session is None:
        return json.dumps({"error": f"Session '{session_id}' non trovata."})

    # --- Add observation ---
    obs_id = store.add_observation(
        session_id=session_id,
        type=type,
        content=content.strip(),
        agent=agent,
        entities=entities,
        handoff_path=handoff_path,
        task_ref=task_ref,
        tokens_discovery=tokens_discovery,
        tokens_read=tokens_read,
        parent_id=parent_id,
    )

    # --- Link entities ---
    entities_found = 0
    if entities:
        for entity_name in entities:
            entity_name = entity_name.strip()
            if not entity_name:
                continue
            # Infer entity type heuristically
            etype = _infer_entity_type(entity_name)
            entity_id = store.get_or_create_entity(entity_name, entity_type=etype)
            store.link_entity_to_observation(obs_id, entity_id)
            entities_found += 1

    # --- Best-effort taskmanager event ---
    if task_ref:
        _log_to_taskmanager(task_ref, type, content, session_id, handoff_path)

    # Update session status if observation marks end
    session_updated = False
    if type in ("result", "system"):
        # Touch session updated_at

        store.update_session(session_id, topic=session.get("topic", ""))
        session_updated = True

    result = {
        "observation_id": obs_id,
        "entities_found": entities_found,
        "session_updated": session_updated,
    }

    logger.debug(f"Observation {obs_id} stored ({entities_found} entities linked)")

    return json.dumps(result)


# ---------------------------------------------------------------------------
# Tool 3: session_context
# ---------------------------------------------------------------------------


@mcp.tool()
def session_context(
    session_id: str,
    layer: int = 1,
    max_tokens: int | None = None,
) -> str:
    """Retrieve progressive context for a session.

    Layer 1 (~200 tokens): header with topic, metrics, active tasks, key entities.
    Layer 2 (~800 tokens): timeline with last 5 observations and token savings.
    Layer 3 (~1500 tokens): full content of the most recent observation.

    If ``max_tokens`` is specified, the context is truncated to fit.

    Parameters
    ----------
    session_id : str
        The session ID.
    layer : int
        Context layer: 1 (header), 2 (timeline), or 3 (full).
        Default is 1.
    max_tokens : int | None
        Optional token budget for truncation.
    """
    logger.info(f"session_context: session={session_id}, layer={layer}, max_tokens={max_tokens}")

    if layer not in (1, 2, 3):
        return json.dumps({"error": "layer deve essere 1, 2, o 3."})

    store = _get_store()
    session = store.get_session(session_id)
    if session is None:
        return json.dumps({"error": f"Session '{session_id}' non trovata."})

    metrics = store.get_session_metrics(session_id)
    observations = store.get_latest_observations(session_id, limit=5)

    if layer == 1:
        context = _build_layer1(session, metrics)
    elif layer == 2:
        context = _build_layer2(observations)
    else:
        context = _build_layer3(observations)

    token_count = _count_tokens(context)

    # Truncate if max_tokens is specified
    if max_tokens is not None and token_count > max_tokens:
        context = _truncate_to_tokens(context, max_tokens)
        token_count = max_tokens

    has_more = layer < 3
    suggestions = {
        1: "Usa layer=2 per dettaglio timeline.",
        2: "Usa layer=3 per osservazione completa.",
        3: "Usa session_recall per ricerca cross-sessione.",
    }

    result = {
        "layer": layer,
        "context": context,
        "token_count": token_count,
        "has_more": has_more,
        "suggestion": suggestions.get(layer, ""),
    }

    return json.dumps(result)


# ---------------------------------------------------------------------------
# Tool 4: session_recall
# ---------------------------------------------------------------------------


@mcp.tool()
def session_recall(
    query: str,
    entity: str | None = None,
    agent: str | None = None,
    type: str | None = None,
    session_id: str | None = None,
    max_results: int = 10,
    since: str | None = None,
) -> str:
    """Search observations using FTS5 BM25 with optional filters.

    Parameters
    ----------
    query : str
        Full-text search query (FTS5 syntax, e.g. ``"session memory"``).
    entity : str | None
        Filter by entity name (exact match, case-insensitive).
    agent : str | None
        Filter by agent name.
    type : str | None
        Filter by observation type.
    session_id : str | None
        Limit results to a specific session.
    max_results : int
        Maximum results (default 10, max 50).
    since : str | None
        ISO 8601 timestamp — return only observations after this time.
    """
    logger.info(
        f"session_recall: query='{query[:60]}', entity={entity}, "
        f"agent={agent}, type={type}, session={session_id}, "
        f"max_results={max_results}, since={since}"
    )

    if not query or not query.strip():
        return json.dumps({"error": "Il parametro 'query' è obbligatorio."})

    if max_results < 1:
        max_results = 10
    if max_results > 50:
        max_results = 50

    start_time = time.time()
    store = _get_store()

    results = store.search_observations(
        query=query.strip(),
        entity=entity,
        agent=agent,
        type=type,
        session_id=session_id,
        max_results=max_results,
        since=since,
    )

    query_time_ms = round((time.time() - start_time) * 1000, 2)

    # Build output with snippets
    output_results = []
    for r in results:
        content = r.get("content", "")
        output_results.append(
            {
                "observation_id": r.get("id"),
                "session_id": r.get("session_id"),
                "type": r.get("type"),
                "agent": r.get("agent"),
                "content_snippet": content[:200] + ("..." if len(content) > 200 else ""),
                "entities": r.get("entities", []),
                "handoff_path": r.get("handoff_path"),
                "task_ref": r.get("task_ref"),
                "created_at": r.get("created_at"),
                "score": r.get("score", 0.0),
            }
        )

    result = {
        "results": output_results,
        "total": len(output_results),
        "query_time_ms": query_time_ms,
    }

    logger.debug(f"session_recall: {len(output_results)} results in {query_time_ms}ms")

    return json.dumps(result)


# ---------------------------------------------------------------------------
# Tool 5: session_summarize
# ---------------------------------------------------------------------------


@mcp.tool()
def session_summarize(
    session_id: str,
    force: bool = False,
    level: int = 1,
) -> str:
    """Compress unsummarised observations into a summary.

    Takes observations that have not yet been compressed at the given
    ``level`` and produces a summary. If ``force=True``, re-processes all
    observations regardless.

    Parameters
    ----------
    session_id : str
        The session ID.
    force : bool
        If True, re-compress all observations (default False).
    level : int
        Summary level to update (1, 2, or 3; default 1).
    """
    logger.info(f"session_summarize: session={session_id}, force={force}, level={level}")

    if level not in (1, 2, 3):
        return json.dumps({"error": "level deve essere 1, 2, o 3."})

    store = _get_store()
    session = store.get_session(session_id)
    if session is None:
        return json.dumps({"error": f"Session '{session_id}' non trovata."})

    # Get candidate observations
    if force:
        candidates = store.get_observations(session_id, limit=1000, offset=0)
    else:
        candidates = store.get_summarization_candidates(session_id, level=level)

    if not candidates:
        return json.dumps(
            {
                "summary_id": None,
                "level": level,
                "observations_compressed": 0,
                "token_savings": 0,
                "content": "",
                "warning": "Nessuna nuova osservazione da comprimere.",
            }
        )

    # Build compressed content
    obs_count = len(candidates)
    total_disc = sum(o.get("tokens_discovery", 0) for o in candidates)

    # Simple compression: concatenate with type prefixes
    lines: list[str] = []
    for o in candidates:
        prefix = {
            "decision": "🧠 Decision",
            "delegation": "📤 Delegation",
            "result": "📥 Result",
            "note": "📝 Note",
            "handoff": "📄 Handoff",
            "user_message": "💬 User",
            "system": "⚙️ System",
        }.get(o.get("type", ""), "📌")
        agent = o.get("agent", "?")
        content = o.get("content", "")
        lines.append(f"[{prefix} / {agent}] {content[:300]}")

    summary_content = "\n\n".join(lines)
    # Token savings heuristic: compressed is ~60% of raw content
    compressed_tokens = _count_tokens(summary_content)
    token_savings_actual = max(0, total_disc - compressed_tokens)

    summary_id = store.add_summary(
        session_id=session_id,
        level=level,
        content=summary_content,
        token_count=compressed_tokens,
        parent_id=None,
    )

    # Update session summary field (for level 1)
    if level == 1:
        store.update_session(
            session_id,
            summary=summary_content[:500],
            token_discovery=session.get("token_discovery", 0),
            token_read=session.get("token_read", 0),
        )

    result = {
        "summary_id": summary_id,
        "level": level,
        "observations_compressed": obs_count,
        "token_savings": token_savings_actual,
        "content": summary_content,
    }

    logger.info(
        f"Summary {summary_id} created: {obs_count} observations compressed, "
        f"{token_savings_actual} tokens saved"
    )

    return json.dumps(result)


# ---------------------------------------------------------------------------
# Context builders (3-layer progressive disclosure)
# ---------------------------------------------------------------------------


def _build_layer1(session: dict[str, Any], metrics: dict[str, Any]) -> str:
    """Build Layer 1 — Header (~200 tokens).

    Includes topic, duration, metrics, active tasks, key entities.
    """
    session_id = session.get("id", "?")
    topic = session.get("topic", "?")
    started = session.get("started_at", "?")[:16]  # trim seconds
    obs_count = metrics.get("observations_count", 0)
    tot_disc = metrics.get("total_tokens_discovery", 0)
    tot_read = metrics.get("total_tokens_read", 0)
    savings_pct = metrics.get("token_savings_avg", 0) * 100

    task_ids = session.get("task_ids", [])

    lines = [
        f" Session: {topic}",
        f" Started: {started} | Observations: {obs_count}",
    ]

    if tot_disc > 0:
        lines.append(
            f" Token Economics: discovery={tot_disc} | read={tot_read} | savings={savings_pct:.0f}%"
        )

    if task_ids:
        lines.append("")
        lines.append(" Active Tasks:")
        for tid in task_ids:
            lines.append(f"   {tid}")

    # Get key entities from metrics scope
    try:
        store = _get_store()
        # Latest observation entities for key items
        latest = store.get_latest_observations(session_id, limit=3)
        all_entities: set[str] = set()
        for obs in latest:
            for ent in obs.get("entities", []):
                all_entities.add(ent)
        if all_entities:
            lines.append("")
            lines.append(f" Key Entities: {', '.join(sorted(all_entities)[:8])}")
    except Exception:
        pass

    lines.append("")
    lines.append("(Usa layer=2 per dettaglio timeline)")

    return "\n".join(lines)


def _build_layer2(observations: list[dict[str, Any]]) -> str:
    """Build Layer 2 — Timeline (~800 tokens).

    Lists the last 5 observations with type, snippet, entities, and token savings.
    """
    if not observations:
        return " Timeline: (nessuna osservazione)"

    lines = [" Timeline (ultime osservazioni):", ""]

    for obs in observations:
        t = obs.get("created_at", "")[11:16]  # HH:MM
        otype = obs.get("type", "?")
        content = obs.get("content", "")[:120]
        entities_list = obs.get("entities", [])
        savings_pct = obs.get("token_savings", 0) * 100

        type_icon = {
            "decision": "",
            "delegation": "",
            "result": "",
            "note": "",
            "handoff": "",
            "user_message": "",
            "system": "",
        }.get(otype, "")

        task_ref = obs.get("task_ref")
        handoff_path = obs.get("handoff_path")

        lines.append(f"[{t}] {type_icon} {otype} — {content}")
        if entities_list:
            lines.append(f"       Entities: {', '.join(entities_list[:5])}")
        if task_ref:
            lines.append(f"       Task: {task_ref}")
        if handoff_path:
            lines.append(f"       Handoff: {handoff_path}")
        lines.append(f"       Token savings: {savings_pct:.0f}%")
        lines.append("")

    lines.append('Gestures: "layer=3" per dettaglio completo | "recall <query>" per ricerca')

    return "\n".join(lines)


def _build_layer3(observations: list[dict[str, Any]]) -> str:
    """Build Layer 3 — Full observation (~1500 tokens).

    Shows the most recent observation in full.
    """
    if not observations:
        return " Nessuna osservazione disponibile."

    latest = observations[0]
    content = latest.get("content", "")
    otype = latest.get("type", "?")
    agent = latest.get("agent", "Hermes")
    created = latest.get("created_at", "?")
    entities_list = latest.get("entities", [])
    task_ref = latest.get("task_ref")
    handoff_path = latest.get("handoff_path")
    tokens_disc = latest.get("tokens_discovery", 0)
    tokens_read = latest.get("tokens_read", 0)

    lines = [
        " Ultima osservazione (full):",
        f" Type: {otype} | Agent: {agent} | Time: {created}",
        "",
        content,
        "",
    ]

    if entities_list:
        lines.append(f"Entities: {', '.join(entities_list)}")
    if task_ref:
        lines.append(f"Task: {task_ref}")
    if handoff_path:
        lines.append(f"Handoff: {handoff_path}")

    if tokens_disc > 0 or tokens_read > 0:
        if tokens_disc > 0:
            savings_pct = (tokens_disc - tokens_read) * 100.0 / tokens_disc
        else:
            savings_pct = 0.0
        line = (
            f"Token economics: discovery={tokens_disc}"
            f" | read={tokens_read} | savings={savings_pct:.0f}%"
        )
        lines.append(line)

    return "\n".join(lines)


def _count_tokens(text: str) -> int:
    """Rough token count (4 chars per token heuristic)."""
    return max(1, len(text) // 4)


def _truncate_to_tokens(text: str, max_tokens: int) -> str:
    """Truncate text to approximately ``max_tokens``."""
    max_chars = max_tokens * 4
    if len(text) <= max_chars:
        return text
    return text[:max_chars] + "\n[...troncato...]"


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _infer_entity_type(name: str) -> str:
    """Heuristic entity type inference from name.

    Args:
        name: Entity name string.

    Returns:
        Entity type from ``EntityType`` enum.
    """
    name_lower = name.lower().strip()

    # Known agent names
    agents = {
        "hermes",
        "proteo",
        "atena",
        "clio",
        "dike",
        "efesto",
        "eunomia",
        "euterpe",
        "metis",
        "pythagoras",
        "hermione",
    }
    if name_lower in agents:
        return "agent"

    # Technology indicators
    tech_indicators = {
        "sqlite",
        "python",
        "mcp",
        "api",
        "sdk",
        "cli",
        "db",
        "yaml",
        "json",
        "fts5",
        "fastmcp",
        "typer",
        "pydantic",
        "loguru",
        "pytest",
        "ruff",
        "mypy",
        "httpx",
        "git",
    }
    if name_lower in tech_indicators:
        return "technology"

    # Project indicators
    if name_lower.startswith("t-") or name_lower.startswith("fase"):
        return "task"
    if "chimer" in name_lower:
        return "project"

    return "concept"


def _log_to_taskmanager(
    task_ref: str,
    obs_type: str,
    content: str,
    session_id: str,
    handoff_path: str | None = None,
) -> None:
    """Best-effort log an event to the taskmanager via subprocess MCP call.

    This is a best-effort operation — failures are logged but not propagated.
    """
    try:
        import subprocess
        import sys

        session_prefix = f"[session:{session_id[:16]}]"
        details = f"{session_prefix} {obs_type}: {content[:150]}"

        cmd = [
            sys.executable,
            "-m",
            "tools.taskmanager.server",
            "task_log_event",
            task_ref,
            "--event-type",
            "note",
            "--details",
            details,
        ]
        if handoff_path:
            cmd.extend(["--handoff-path", handoff_path])

        # NOTE: This is a fallback approach. In production, the MCP client
        # (Hermes) should call task_log_event directly. This subprocess
        # call is a best-effort attempt only.
        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=5,
        )
        if result.returncode != 0:
            logger.debug(f"taskmanager log (best-effort) returned code {result.returncode}")
    except Exception as e:
        logger.debug(f"taskmanager log (best-effort) failed: {e}")


# ---------------------------------------------------------------------------
# Tool 6: session_compress
# ---------------------------------------------------------------------------


@mcp.tool()
def session_compress(
    age_days: int | None = None,
    max_level: int = 2,
    dry_run: bool = True,
) -> str:
    """Compress old observations using progressive hot/warm/cold levels.

    - **Warm** (level 1): compress ``content`` via Token Juice (max 300 chars).
      Observations remain searchable with shortened content.
    - **Cold** (level 2): group by ISO week per-session, write level-3 summary.
      Original rows are flagged with ``compression_level=2`` but not deleted.

    Parameters
    ----------
    age_days : int | None
        If set, only compress observations older than N days.
        If ``None``, uses defaults (7 for warm, 30 for cold).
    max_level : int
        Maximum compression level: 1 (warm) or 2 (cold). Default 2.
    dry_run : bool
        If ``True`` (default), only report what would be done.
    """
    logger.info(f"session_compress: age_days={age_days}, max_level={max_level}, dry_run={dry_run}")

    if max_level not in (1, 2):
        return json.dumps({"error": "max_level deve essere 1 (warm) o 2 (cold)."})

    store = _get_store()
    try:
        results = store.compress_observations(
            age_days=age_days,
            max_level=max_level,
            dry_run=dry_run,
        )
        logger.info(
            f"Session compression {'dry-run' if dry_run else 'applied'}: "
            f"{results['observations_warm']} warm, "
            f"{results['observations_cold']} cold, "
            f"{results['summaries_created']} summaries"
        )
        return json.dumps(results)
    except Exception as e:
        logger.error(f"Session compression failed: {e}")
        return json.dumps({"error": f"Compressione sessioni fallita: {e}"})


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------


def main_server() -> None:
    """Start the session_memory MCP server on stdio transport."""
    if not MCP_AVAILABLE:
        logger.error("MCP SDK not installed. Run: uv add mcp")
        import sys

        sys.exit(1)

    logger.info("Starting session_memory MCP server on stdio...")

    # Validate DB is accessible on startup
    try:
        store = _get_store()
        store.get_session_metrics("__dummy__")
        logger.info(f"Session DB ready at {store.path}")
    except Exception as e:
        logger.error(f"Failed to initialise session DB: {e}")
        import sys

        sys.exit(1)

    mcp.run()


if __name__ == "__main__":
    main_server()
