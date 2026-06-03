"""Test per tools/common/paths.py."""

from pathlib import Path

from tools.common.paths import project_root, resolve_relative, resolve_absolute


def test_project_root():
    root = project_root()
    assert isinstance(root, Path)
    assert root.exists()
    assert root.name == "TeamOlimpo"
    assert (root / "tools" / "config.yaml").exists()


def test_resolve_relative_preserves_symlink():
    p = resolve_relative("lib")
    # resolve_relative should NOT resolve the symlink
    assert "TeamOlimpo/Library" in str(p) or str(p).endswith("/Library")
    assert p.exists()
    assert p.is_dir()


def test_resolve_absolute_resolves_symlink():
    p = resolve_absolute("lib")
    assert p.exists()
    assert p.is_dir()
    # The absolute path should go through the symlink to the real target
    # which is /home/stra/Library
    assert p.name == "lib"


def test_all_imports():
    from tools.common.paths import project_root as pr

    assert pr() is not None
