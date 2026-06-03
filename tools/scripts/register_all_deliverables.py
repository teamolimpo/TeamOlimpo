"""One-time script: register all lib/ files in deliverables DB,
then replace file paths with hashes inside all text files.

Usage: uv run python -m tools.scripts.register_all_deliverables
"""

from __future__ import annotations

import sys
from pathlib import Path

from tools.common.paths import project_root
from tools.synapsis.store import SynapsisStore

# ── config ────────────────────────────────────────────────────────
# Only these dirs contain deliverable content
TARGET_DIRS = {"deliverables", "Handoff", "Wiki", "documents", "projects", "prompts"}
SKIP_DIRS = {".git", "__pycache__", ".obsidian"}
SKIP_EXTS = {".pyc", ".db", ".db-wal", ".db-shm", ".db-journal"}
TEXT_EXTS = {".md", ".txt", ".yaml", ".yml", ".json", ".toml", ".csv"}

root = project_root()
lib = root / "Library"

print(f"Project root: {root}")
print(f"Lib dir:     {lib}")
print()


def is_text(f: Path) -> bool:
    return f.suffix.lower() in TEXT_EXTS


def should_skip(f: Path) -> bool:
    rel = f.relative_to(lib).parts if lib in f.parents else f.parts
    if any(s in rel for s in SKIP_DIRS):
        return True
    if f.suffix in SKIP_EXTS:
        return True
    return False


def collect_files() -> list[Path]:
    """Return all files in TARGET_DIRS that should be processed."""
    result = []
    for d in TARGET_DIRS:
        dpath = lib / d
        if not dpath.is_dir():
            continue
        for f in sorted(dpath.rglob("*")):
            if not f.is_file():
                continue
            if should_skip(f):
                continue
            result.append(f)
    return result


def register_all(store: SynapsisStore, files: list[Path]) -> dict[str, str]:
    """Register every file path in deliverables DB. Return path→hash map."""
    pmap: dict[str, str] = {}
    total = len(files)
    for i, f in enumerate(files):
        rel = str(f.relative_to(root))
        h = store.deliverable_register(rel)
        pmap[rel] = h
        if (i + 1) % 1000 == 0:
            print(f"  Registered {i + 1}/{total}")
    print(f"  Registered {total}/{total}")
    return pmap


def replace_paths(files: list[Path], pmap: dict[str, str]) -> tuple[int, int]:
    """Scan text files, replace known paths with hashes.

    Returns (files_modified, total_replacements).
    """
    # Sort by length descending so longest paths match first
    sorted_paths = sorted(pmap.keys(), key=len, reverse=True)

    files_modified = 0
    total_replacements = 0

    for f in files:
        if not is_text(f):
            continue

        try:
            content = f.read_text(encoding="utf-8")
        except Exception:
            continue

        new_content = content
        for p in sorted_paths:
            if new_content.find(p) == -1:
                continue
            # Check it's not part of a longer path
            new_content = new_content.replace(p, pmap[p])

        if new_content != content:
            # Verify it's still valid UTF-8
            try:
                f.write_text(new_content, encoding="utf-8")
            except Exception:
                continue

            # Count replacements
            for p in sorted_paths:
                if p in content:
                    total_replacements += content.count(p)

            files_modified += 1

    return files_modified, total_replacements


def main() -> None:
    print("═" * 50)
    print("Phase 1: Collecting files...")
    files = collect_files()
    text_files = [f for f in files if is_text(f)]
    print(f"  Total files:     {len(files)}")
    print(f"  Text files:      {len(text_files)}")
    print()

    # Phase 1: Register all files
    print("Phase 2: Registering files in deliverables DB...")
    store = SynapsisStore()
    pmap = register_all(store, files)
    print()

    # Phase 2: Replace paths with hashes in text files
    print("Phase 3: Replacing paths with hashes in text files...")
    files_mod, repl_count = replace_paths(text_files, pmap)
    print(f"  Files modified:   {files_mod}")
    print(f"  Total repl:       {repl_count}")
    print()

    print("═" * 50)
    print("Done.")
    print(f"  {len(pmap)} paths registered")
    print(f"  {files_mod} files modified")
    print(f"  {repl_count} replacements made")


if __name__ == "__main__":
    main()
