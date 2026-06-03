"""MCP server: expose ``run()`` tool for shell command execution with
Token Juice output compression.

Usage::

    uv run python -m tools.executor.server

The server listens on stdio (MCP stdio transport). An MCP client (e.g.
``opencode.json``'s ``mcp`` section) connects to it and calls the ``run`` tool.

Key design choices
------------------
- **shell=True** — supports pipes, redirects, env vars, &&, || (unlike shlex.split).
- **Token Juice is lazy** — imported only when ``run()`` is called,
  never at module level. Zero startup cost if no commands are run.
- **Command sanitization** — length cap, block dangerous patterns.
"""

from __future__ import annotations

import re
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
# Token Juice — lazy, never imported at module level
# ---------------------------------------------------------------------------

_TOKEN_JUICE_AVAILABLE: bool | None = None  # tri-state: None = unchecked


def _check_token_juice() -> bool:
    """Check if Token Juice is available (cached after first check)."""
    global _TOKEN_JUICE_AVAILABLE
    if _TOKEN_JUICE_AVAILABLE is None:
        try:
            # Import each component individually to catch partial failures
            from tools.token_juice.compressor import ProseCompressor  # noqa: F401
            from tools.token_juice.rule_engine import find_matching_rule, load_all_rules  # noqa: F401
            from tools.token_juice.rule_engine import process as c3_process  # noqa: F401
            from tools.token_juice.tokenizer import tokenize as c1_tokenize  # noqa: F401

            _TOKEN_JUICE_AVAILABLE = True
        except ImportError:
            _TOKEN_JUICE_AVAILABLE = False
    return _TOKEN_JUICE_AVAILABLE


# ---------------------------------------------------------------------------
# Command sanitization
# ---------------------------------------------------------------------------

_MAX_COMMAND_LEN = 2000

# Patterns that are always rejected
_DANGEROUS_PATTERNS: list[re.Pattern] = [
    re.compile(r"\brm\s+-rf\s+/\s*$"),           # rm -rf /
    re.compile(r"\bsudo\s+rm\s+-rf\s+/\s*"),      # sudo rm -rf /
    re.compile(r">\s*/dev/sd[a-z]"),               # write to block device
    re.compile(r"\|>\s*/dev/sd[a-z]"),             # redirect to block device
    re.compile(r"\bdd\s+if=.*\s+of=/dev/sd"),      # dd to block device
    re.compile(r"\bmkfs\."),                        # filesystem creation
    re.compile(r"\bchmod\s+777\s+/"),              # recursive perms on root
]

# Non-blocking but suspicious — logged, not rejected
_SUSPICIOUS_PATTERNS: list[re.Pattern] = [
    re.compile(r"\bsudo\s"),                        # sudo (most cases fine)
    re.compile(r"\bshutdown\b"),                    # system shutdown
    re.compile(r"\breboot\b"),                      # system reboot
    re.compile(r"\bpoweroff\b"),                    # system poweroff
    re.compile(r"\bhibernate\b"),                   # system hibernate
]


def _sanitize(command: str) -> str | None:
    """Validate command. Returns the command if OK, or an error message."""
    if len(command) > _MAX_COMMAND_LEN:
        return (
            f"Error: command exceeds {_MAX_COMMAND_LEN} characters "
            f"({len(command)} given)."
        )

    for pattern in _DANGEROUS_PATTERNS:
        if pattern.search(command):
            return (
                f"Error: command blocked by security policy "
                f"(matched pattern: {pattern.pattern})."
            )

    for pattern in _SUSPICIOUS_PATTERNS:
        if pattern.search(command):
            logger.warning(f"Suspicious pattern '{pattern.pattern}' in command: {command[:120]}")

    return None  # OK


# ---------------------------------------------------------------------------
# Intensity resolution ("auto" mode)
# ---------------------------------------------------------------------------

_VALID_INTENSITIES = frozenset({"auto", "lite", "full", "ultra", "off"})


def _resolve_intensity(command: str, output: str, intensity: str) -> str:
    """Resolve ``auto`` to an effective intensity level.

    Decision tree for ``intensity="auto"``:

    1. C3 Rule Engine matches a tool-specific rule (not the generic ``["*"]``
       fallback) → ``ultra``.
    2. C3 no specific rule match → ``full``.
    3. Output is mostly prose (C1 Tokenizer: <30% technical) → ``full``.
    """
    if intensity != "auto":
        return intensity

    if not _check_token_juice():
        return "off"

    # Lazy imports — Token Juice was confirmed available above
    import shlex

    from tools.token_juice.rule_engine import find_matching_rule, load_all_rules
    from tools.token_juice.tokenizer import tokenize as c1_tokenize

    argv = shlex.split(command)
    rules = load_all_rules()
    matched_rule = find_matching_rule(argv, output, rules)

    if matched_rule is not None and matched_rule.match.argv0 != ["*"]:
        logger.debug(f"auto -> ultra (rule={matched_rule.id})")
        return "ultra"

    segments = c1_tokenize(output)
    if segments:
        total = sum(len(s.text) for s in segments)
        tech = sum(len(s.text) for s in segments if s.is_technical)
        tech_ratio = tech / total if total > 0 else 0.0
        if tech_ratio < 0.30:
            logger.debug("auto -> full (mostly prose)")
            return "full"

    logger.debug("auto -> full (generic fallback)")
    return "full"


# ---------------------------------------------------------------------------
# Compression pipeline
# ---------------------------------------------------------------------------


def _compress_output(command: str, output: str, intensity: str, locale: str = "en") -> str:
    """Apply Token Juice compression pipeline to ``output``.

    Steps
    -----
    1. **C3 Rule Engine** — applies transformations, filters, summaries.
    2. **C2 Prose Compressor** — compresses only prose blocks, preserves
       technical blocks verbatim.
    3. **Utility Gate** — if compressed result is < 128 chars or compression
       ratio > 0.95, returns the original.
    """
    if intensity == "off" or not _check_token_juice():
        return output

    # Lazy imports — Token Juice was confirmed available above
    import shlex

    from tools.token_juice.compressor import ProseCompressor
    from tools.token_juice.rule_engine import process as c3_process
    from tools.token_juice.tokenizer import tokenize as c1_tokenize

    argv = shlex.split(command)
    c3_result = c3_process(argv, output)
    logger.debug(f"C3 done: {len(output)} -> {len(c3_result)} chars")

    segments = c1_tokenize(c3_result)
    compressor = ProseCompressor(intensity, locale=locale)
    compressed_parts: list[str] = []

    for seg in segments:
        if seg.is_technical:
            compressed_parts.append(seg.text)
        else:
            compressed_parts.append(compressor.compress(seg.text))

    compressed = "".join(compressed_parts)
    logger.debug(f"C2 done: {len(c3_result)} -> {len(compressed)} chars (intensity={intensity})")

    original_len = len(output)
    compressed_len = len(compressed)

    if compressed_len < 128:
        logger.debug("Utility gate: compressed < 128 chars -> original")
        return output

    if original_len > 0:
        ratio = compressed_len / original_len
        if ratio > 0.95:
            logger.debug(f"Utility gate: ratio={ratio:.3f} > 0.95 -> original")
            return output

    logger.info(
        f"Output compressed: {original_len} -> {compressed_len} chars "
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
    """Execute shell command via bash, compress output via Token Juice.

    Supports pipes (``|``), redirects (``>``, ``<``), env vars (``$VAR``),
    command chaining (``&&``, ``||``), and all bash syntax.
    """
    # -- Validate parameters ------------------------------------------------
    if intensity not in _VALID_INTENSITIES:
        valid = ", ".join(sorted(_VALID_INTENSITIES))
        return f"Error: invalid intensity '{intensity}'. Must be one of: {valid}."

    if locale not in ("en", "it"):
        return f"Error: invalid locale '{locale}'. Must be 'en' or 'it'."

    if timeout < 1:
        return "Error: timeout must be >= 1 second."

    # -- Sanitize command ---------------------------------------------------
    err = _sanitize(command)
    if err is not None:
        return err

    logger.info(
        f"run: command='{command[:120]}', intensity={intensity}, "
        f"timeout={timeout}, locale={locale}"
    )

    # -- Execute via bash (shell=True for pipe/redirect support) ------------
    try:
        result = subprocess.run(
            command,
            capture_output=True,
            text=True,
            timeout=timeout,
            shell=True,
            executable="/bin/bash",
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
    except OSError as e:
        msg = f"Execution error: {e}"
        logger.error(msg)
        return msg

    # -- Non-zero exit: return raw stdout + stderr --------------------------
    if result.returncode != 0:
        combined = (result.stdout or "") + (result.stderr or "")
        logger.info(
            f"Command exited with code {result.returncode} "
            f"({len(combined)} chars raw output)"
        )
        if not combined.strip():
            return f"Error: command exited with code {result.returncode} (no output)"
        return combined

    stdout = result.stdout or ""

    # -- Resolve intensity (auto mode) --------------------------------------
    effective = _resolve_intensity(command, stdout, intensity)

    # -- Compress via Token Juice pipeline ----------------------------------
    return _compress_output(command, stdout, effective, locale=locale)


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------


def main_server() -> None:
    """Start the executor MCP server on stdio transport."""
    if not MCP_AVAILABLE:
        logger.error("MCP SDK not installed. Run: uv add mcp")
        sys.exit(1)

    logger.info("Starting executor MCP server on stdio...")
    mcp.run()


if __name__ == "__main__":
    main_server()
