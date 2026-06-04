"""Tests for tools.llm image generation — CLI and core functionality.

Ported from tests/test_image_gen.py after merging image_gen into llm.
"""

from __future__ import annotations

from typer.testing import CliRunner

from tools.llm.cli import app
from tools.llm.image_processor import compute_crc32, slugify

runner = CliRunner()

# ---------------------------------------------------------------------------
# CLI smoke tests (image mode)
# ---------------------------------------------------------------------------


def test_generate_dry_run() -> None:
    """generate --image --dry-run returns success JSON without API call."""
    result = runner.invoke(
        app,
        [
            "test icon",
            "--model",
            "openai/gpt-5-image-mini",
            "--size",
            "1K",
            "--ratio",
            "1:1",
            "--image",
            "--dry-run",
        ],
    )
    assert result.exit_code == 0
    assert '"status": "success"' in result.stdout
    assert '"dry_run": true' in result.stdout
    assert "deadbeef" in result.stdout  # mock hash


def test_generate_invalid_size() -> None:
    """Invalid size argument returns exit code 2."""
    result = runner.invoke(
        app,
        [
            "test icon",
            "--model",
            "openai/gpt-5-image-mini",
            "--size",
            "3K",
            "--ratio",
            "1:1",
            "--image",
            "--dry-run",
        ],
    )
    assert result.exit_code == 2
    assert '"status": "fail"' in result.stdout
    assert "Invalid size" in result.stdout


def test_generate_invalid_ratio() -> None:
    """Invalid ratio argument returns exit code 2."""
    result = runner.invoke(
        app,
        [
            "test icon",
            "--model",
            "openai/gpt-5-image-mini",
            "--size",
            "1K",
            "--ratio",
            "5:1",
            "--image",
            "--dry-run",
        ],
    )
    assert result.exit_code == 2
    assert '"status": "fail"' in result.stdout
    assert "Invalid ratio" in result.stdout


def test_image_missing_prompt() -> None:
    """--image without prompt returns error."""
    result = runner.invoke(
        app,
        [
            "--image",
            "--dry-run",
        ],
    )
    assert result.exit_code == 1
    assert '"status": "fail"' in result.stdout
    assert "Prompt richiesto" in result.stdout


# ---------------------------------------------------------------------------
# Unit tests
# ---------------------------------------------------------------------------


def test_slugify() -> None:
    """slugify produces safe filesystem names."""
    assert slugify("Hello World!") == "hello-world"
    assert slugify("  Test   Slug  ") == "test-slug"
    assert slugify("a" * 100) == "a" * 60
    assert slugify("special chars: @#$%^&*()") == "special-chars"


def test_compute_crc32() -> None:
    """compute_crc32 returns 8-char hex string."""
    h = compute_crc32(b"hello world")
    assert len(h) == 8
    assert h == "0d4a1185"  # known CRC32 of "hello world"
