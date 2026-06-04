"""Condivisione path di progetto per tutti i tool Team Olimpo.

Fornisce tre funzioni per risolvere i path in modo consistente,
gestendo correttamente lo ``symlink Library/ → /home/stra/Library``.

* :func:`project_root` — radice del repository (via ``Path(__file__)`` resolution)
* :func:`resolve_relative` — join con ``project_root`` **senza** risolvere symlink
* :func:`resolve_absolute` — join con ``project_root`` **con** risoluzione symlink

Usage::

    from tools.common.paths import project_root, resolve_relative, resolve_absolute

    root = project_root()                    # /home/stra/TeamOlimpo
    rel  = resolve_relative("lib")       # /home/stra/TeamOlimpo/Library
    abs  = resolve_absolute("lib")       # /home/stra/Library
"""

from __future__ import annotations

from pathlib import Path

_PROJECT_ROOT: Path | None = None


def project_root() -> Path:
    """Return the absolute project root path (cache after first call).

    Discovery strategy: walk up from ``tools/common/paths.py`` to find the
    ``tools/`` parent directory. This is reliable because this module lives at
    ``tools/common/paths.py``, exactly three levels below the project root.

    Returns:
        Absolute path to the repository root (e.g. ``/home/stra/TeamOlimpo``).
    """
    global _PROJECT_ROOT  # noqa: PLW0603
    if _PROJECT_ROOT is None:
        _PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
    return _PROJECT_ROOT


def resolve_relative(*parts: str) -> Path:
    """Join *parts* with :func:`project_root` — does **not** resolve symlinks.

    Use this when the resulting path must remain under ``project_root`` for
    operations like :meth:`~pathlib.Path.relative_to`, cache keys, or
    arguments passed to subprocesses (e.g. ``ripgrep``).

    Args:
        *parts: Path segments to join after ``project_root``.

    Returns:
        A ``Path`` that is ``project_root / joined_parts`` **without**
        calling ``.resolve()``, so the ``Library`` symlink is preserved.
    """
    return project_root().joinpath(*parts)


def resolve_absolute(*parts: str) -> Path:
    """Join *parts* with :func:`project_root` and resolve **all** symlinks.

    Use this for actual I/O operations (``read_text``, ``write_text``,
    ``is_file``, ``is_dir``, ``exists``) so that the real filesystem path
    is used.

    Args:
        *parts: Path segments to join after ``project_root``.

    Returns:
        A ``Path`` with all symlinks resolved (e.g. ``/home/stra/Library/...``).
    """
    return project_root().joinpath(*parts).resolve()
