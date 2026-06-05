"""Tests for tools/file_stats CLI -- directory scan and extension reporting."""

from pathlib import Path

import pytest

from tools.file_stats.cli import _scan_directory


def test_normal_directory_scan(tmp_path: Path) -> None:
    """Scan a directory with mixed file types."""
    (tmp_path / "readme.md").write_text("# Hello")
    (tmp_path / "data.csv").write_text("a,b,c")
    (tmp_path / "script.py").write_text("print(1)")
    (tmp_path / "notes.txt").write_text("notes")
    (tmp_path / "image.png").write_bytes(b"PNG
")

    counter, total_files, total_dirs = _scan_directory(tmp_path, recursive=False)

    assert total_files == 5
    assert total_dirs == 0
    assert counter[".md"] == 1
    assert counter[".csv"] == 1
    assert counter[".py"] == 1
    assert counter[".txt"] == 1
    assert counter[".png"] == 1
    assert sum(counter.values()) == 5


def test_recursive_scan(tmp_path: Path) -> None:
    """Scan a directory with nested subdirectories."""
    (tmp_path / "root.txt").write_text("root")
    subdir = tmp_path / "subdir"
    subdir.mkdir()
    (subdir / "nested.py").write_text("# nested")
    (subdir / "data.json").write_text('{"key": "value"}')

    counter, total_files, total_dirs = _scan_directory(tmp_path, recursive=True)

    assert total_files == 3
    assert total_dirs == 1
    assert counter[".txt"] == 1
    assert counter[".py"] == 1
    assert counter[".json"] == 1


def test_non_recursive_scan_ignores_nested(tmp_path: Path) -> None:
    """Non-recursive scan should only count top-level files."""
    (tmp_path / "top.txt").write_text("top")
    subdir = tmp_path / "subdir"
    subdir.mkdir()
    (subdir / "nested.py").write_text("# nested")

    counter, total_files, _ = _scan_directory(tmp_path, recursive=False)

    assert total_files == 1
    assert counter[".txt"] == 1
    assert ".py" not in counter


def test_empty_directory(tmp_path: Path) -> None:
    """Scan an empty directory."""
    counter, total_files, total_dirs = _scan_directory(tmp_path, recursive=False)

    assert total_files == 0
    assert total_dirs == 0
    assert len(counter) == 0


def test_scan_nonexistent_path(tmp_path: Path) -> None:
    """Scanning a non-existent directory raises FileNotFoundError."""
    nonexistent = tmp_path / "does_not_exist"

    with pytest.raises(FileNotFoundError):
        _scan_directory(nonexistent, recursive=False)


def test_scan_file_path(tmp_path: Path) -> None:
    """Scanning a file path (not a directory) raises NotADirectoryError."""
    file_path = tmp_path / "not_a_dir.txt"
    file_path.write_text("just a file")

    with pytest.raises(NotADirectoryError):
        _scan_directory(file_path, recursive=False)


def test_no_extension_files(tmp_path: Path) -> None:
    """Files without extension should be counted under '(nessuna)'."""
    (tmp_path / "Makefile").write_text("all:")
    (tmp_path / "README").write_text("text")

    counter, total_files, _ = _scan_directory(tmp_path, recursive=False)

    assert total_files == 2
    assert counter["(nessuna)"] == 2
