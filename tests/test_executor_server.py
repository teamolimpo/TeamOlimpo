"""Tests for tools.executor.server — MCP Executor Server."""

from __future__ import annotations

from tools.executor.server import run

# ---------------------------------------------------------------------------
# Success cases
# ---------------------------------------------------------------------------


def test_simple_command_off() -> None:
    """Simple echo returns output verbatim with intensity=off."""
    result = run("echo hello world", intensity="off")
    assert "hello world" in result


def test_simple_command_auto() -> None:
    """Simple echo with auto intensity returns output (gate: too short)."""
    result = run("echo hello world", intensity="auto")
    assert "hello world" in result


def test_list_dir_ultra() -> None:
    """ls returns non-empty output with ultra compression."""
    result = run("ls -la", intensity="ultra")
    assert result
    assert len(result) > 0


# ---------------------------------------------------------------------------
# Git status compression — verifies C3 rules match
# ---------------------------------------------------------------------------


def test_git_status_compressed() -> None:
    """Git status is compressed by C3 rules (auto → ultra for known tool)."""
    result = run("git status", intensity="auto")
    # Git status output is usually long; compression should yield < 2000
    assert len(result) < 2000


# ---------------------------------------------------------------------------
# Error handling
# ---------------------------------------------------------------------------


def test_nonzero_exit() -> None:
    """Non-zero exit returns raw stderr without compression."""
    result = run("false", intensity="off")
    # 'false' returns exit code 1 with no output
    assert "Error" in result or "code 1" in result


def test_file_not_found() -> None:
    """Command not found returns shell error message."""
    result = run("nonexistent_cmd_xyz_123", intensity="off")
    assert "not found" in result or "not found" in result


def test_timeout() -> None:
    """Timeout returns clear message."""
    result = run("sleep 10", intensity="off", timeout=1)
    assert "timed out" in result.lower()


def test_invalid_intensity() -> None:
    """Invalid intensity value returns error message."""
    result = run("echo hi", intensity="bogus")
    assert "Error" in result
    assert "invalid intensity" in result.lower()


# ---------------------------------------------------------------------------
# Utility gate behavior
# ---------------------------------------------------------------------------


def test_utility_gate_short_output() -> None:
    """Very short output (< 256 chars) bypasses compression (gate)."""
    result_off = run("echo short", intensity="off")
    result_auto = run("echo short", intensity="auto")
    # Both should be identical because compression gate passes original
    assert result_off == result_auto


# ---------------------------------------------------------------------------
# Integration: verify the full pipeline executes without error
# ---------------------------------------------------------------------------


def test_pipeline_roundtrip() -> None:
    """Compression pipeline runs without raising for various intensities."""
    for intensity in ("lite", "full", "ultra", "auto", "off"):
        result = run("echo pipeline_test", intensity=intensity)
        assert "pipeline_test" in result, f"Failed with intensity={intensity}"


# ---------------------------------------------------------------------------
# MCP Availability (import smoke test)
# ---------------------------------------------------------------------------


def test_mcp_importable() -> None:
    """The server module imports without error (MCP is optional)."""
    import importlib

    mod = importlib.import_module("tools.executor.server")
    assert hasattr(mod, "run")
    assert hasattr(mod, "mcp")
    assert hasattr(mod, "MCP_AVAILABLE")
