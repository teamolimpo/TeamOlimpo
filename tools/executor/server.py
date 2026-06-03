"""MCP server: expose ``run()`` tool for shell command execution with
Token Juice output compression.

Usage::

    uv run python -m tools.executor.server

The server listens on stdio (MCP stdio transport). An MCP client (e.g.
``opencode.json``'s ``mcp`` section) connects to it and calls the ``run`` tool.

Pipeline
--------
subprocess.run(``command``)
    → stdout
    → [se intensity != "off"]:
        → C3 Rule Engine (classifica + trasforma + filtra + riassumi)
        → C2 Prose Compressor (comprime solo blocchi prosa)
        → Utility Gate (se ratio > 0.95 o len < 256 → originale)
    → return output (compresso o originale)
"""

from __future__ import annotations

import shlex
import subprocess
import sys

from loguru import logger

# ---------------------------------------------------------------------------
# MCP SDK — graceful fallback if missing
# ---------------------------------------------------------------------------

try:
    from mcp.server.fastmcp import FastMCP

    mcp = FastMCP("executor")
    MCP_AVAILABLE = True
except ImportError:
    MCP_AVAILABLE = False

# ---------------------------------------------------------------------------
# Token Juice — graceful fallback if missing
# ---------------------------------------------------------------------------

try:
    from tools.token_juice.compressor import ProseCompressor
    from tools.token_juice.rule_engine import (
        find_matching_rule,
        load_all_rules,
    )
    from tools.token_juice.rule_engine import (
        process as c3_process,
    )
    from tools.token_juice.tokenizer import tokenize as c1_tokenize

    TOKEN_JUICE_AVAILABLE = True
except ImportError:
    TOKEN_JUICE_AVAILABLE = False

# ---------------------------------------------------------------------------
# Intensity resolution ("auto" mode)
# ---------------------------------------------------------------------------

_VALID_INTENSITIES = frozenset({"auto", "lite", "full", "ultra", "off"})


def _resolve_intensity(command: str, output: str, intensity: str) -> str:
    """Resolve ``auto`` to an effective intensity level.

    Decision tree for ``intensity="auto"``:

    1. C3 Rule Engine matcha una regola specifica per il tool (non il
       fallback generico ``["*"]``) → ``ultra``.
    2. C3 non matcha regola specifica → ``full``.
    3. Output è principalmente prosa (C1 Tokenizer: <30% tecnico) → ``full``.
    """
    if intensity != "auto":
        return intensity

    if not TOKEN_JUICE_AVAILABLE:
        return "off"

    argv = shlex.split(command)
    rules = load_all_rules()
    matched_rule = find_matching_rule(argv, output, rules)

    # Regola specifica (non il fallback generic con argv0=["*"]) → ultra
    if matched_rule is not None and matched_rule.match.argv0 != ["*"]:
        logger.debug(f"auto → ultra (rule={matched_rule.id})")
        return "ultra"

    # Output prevalentemente prosa → full
    segments = c1_tokenize(output)
    if segments:
        total = sum(len(s.text) for s in segments)
        tech = sum(len(s.text) for s in segments if s.is_technical)
        tech_ratio = tech / total if total > 0 else 0.0
        if tech_ratio < 0.30:
            logger.debug("auto → full (mostly prose)")
            return "full"

    logger.debug("auto → full (generic fallback)")
    return "full"


# ---------------------------------------------------------------------------
# Compression pipeline
# ---------------------------------------------------------------------------


def _compress_output(command: str, output: str, intensity: str, locale: str = "en") -> str:
    """Apply Token Juice compression pipeline to ``output``.

    Steps
    -----
    1. **C3 Rule Engine** — ``rule_engine.process(argv, output)``
       applica trasformazioni, filtri, summarize e utility gate interni.
    2. **C2 Prose Compressor** — estrae i soli blocchi prosa via C1
       Tokenizer, li comprime con ``ProseCompressor(intensity, locale)``,
       e ricombina con i blocchi tecnici preservati.
    3. **Utility Gate** — se il risultato compresso è piú corto di 128
       caratteri o il ratio di compressione > 0.95, restituisce l'originale.
    """
    if intensity == "off" or not TOKEN_JUICE_AVAILABLE:
        return output

    # ── Step 1: C3 Rule Engine ─────────────────────────────────────
    argv = shlex.split(command)
    c3_result = c3_process(argv, output)
    logger.debug(f"C3 done: {len(output)} → {len(c3_result)} chars")

    # ── Step 2: C2 Prose Compressor (solo prosa) ───────────────────
    segments = c1_tokenize(c3_result)
    compressor = ProseCompressor(intensity, locale=locale)
    compressed_parts: list[str] = []

    for seg in segments:
        if seg.is_technical:
            compressed_parts.append(seg.text)
        else:
            compressed_parts.append(compressor.compress(seg.text))

    compressed = "".join(compressed_parts)
    logger.debug(f"C2 done: {len(c3_result)} → {len(compressed)} chars (intensity={intensity})")

    # ── Step 3: Utility Gate ───────────────────────────────────────
    # Output < 128 char → originale (troppo corto per compressione utile)
    # Ratio > 0.95 → originale (compressione trascurabile)
    original_len = len(output)
    compressed_len = len(compressed)

    if compressed_len < 128:
        logger.debug("Utility gate: compressed < 128 chars → originale")
        return output

    if original_len > 0:
        ratio = compressed_len / original_len
        if ratio > 0.95:
            logger.debug(f"Utility gate: ratio={ratio:.3f} > 0.95 → originale")
            return output

    logger.info(
        f"Output compressed: {original_len} → {compressed_len} chars "
        f"(ratio={compressed_len / original_len:.2%})"
    )
    return compressed


# ---------------------------------------------------------------------------
# MCP Tool: run
# ---------------------------------------------------------------------------


@mcp.tool()
def run(
    command: str,
    intensity: str = "auto",
    timeout: int = 30,
    locale: str = "en",
) -> str:
    """Execute shell command, compress output via Token Juice."""
    # ── Validate parameters ────────────────────────────────────────
    if intensity not in _VALID_INTENSITIES:
        valid = ", ".join(sorted(_VALID_INTENSITIES))
        return f"Error: invalid intensity '{intensity}'. Must be one of: {valid}."

    if locale not in ("en", "it"):
        return f"Error: invalid locale '{locale}'. Must be 'en' or 'it'."

    if timeout < 1:
        return "Error: timeout must be >= 1 second."

    logger.info(
        f"run: command='{command[:120]}', intensity={intensity}, timeout={timeout}, locale={locale}"
    )

    # ── Execute command ────────────────────────────────────────────
    try:
        argv = shlex.split(command)
        result = subprocess.run(
            argv,
            capture_output=True,
            text=True,
            timeout=timeout,
        )
    except subprocess.TimeoutExpired as e:
        partial_raw = e.stdout
        if isinstance(partial_raw, bytes):
            partial = partial_raw.decode("utf-8", errors="replace").strip()
        elif isinstance(partial_raw, str):
            partial = partial_raw.strip()
        else:
            partial = ""
        msg = f"Command timed out after {timeout}s." + (
            f"\nPartial output:\n{partial}" if partial else ""
        )
        logger.warning(f"Timeout: '{command[:80]}'")
        return msg
    except FileNotFoundError as e:
        msg = f"Command not found: {e}"
        logger.error(msg)
        return msg
    except OSError as e:
        msg = f"Execution error: {e}"
        logger.error(msg)
        return msg

    # ── Non-zero exit: return raw stdout + stderr ──────────────────
    if result.returncode != 0:
        combined = (result.stdout or "") + (result.stderr or "")
        logger.info(
            f"Command exited with code {result.returncode} ({len(combined)} chars raw output)"
        )
        # If both stdout and stderr are empty, return a descriptive message
        if not combined.strip():
            return f"Error: command exited with code {result.returncode} (no output)"
        return combined

    stdout = result.stdout or ""

    # ── Resolve intensity (auto mode) ──────────────────────────────
    effective = _resolve_intensity(command, stdout, intensity)

    # ── Compress via Token Juice pipeline ──────────────────────────
    return _compress_output(command, stdout, effective, locale=locale)


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------


def main_server() -> None:
    """Start the executor MCP server on stdio transport."""
    if not MCP_AVAILABLE:
        logger.error("MCP SDK not installed. Run: uv add mcp")
        sys.exit(1)

    if not TOKEN_JUICE_AVAILABLE:
        logger.warning("Token Juice not available — commands will run without compression")

    logger.info("Starting executor MCP server on stdio...")
    mcp.run()


if __name__ == "__main__":
    main_server()
