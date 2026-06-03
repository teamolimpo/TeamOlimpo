"""Entry point: uv run python -m tools.file_type_counter

Scansiona una directory ricorsivamente e conta i file per estensione.
Stampa un riepilogo ordinato (più comune prima).
"""

from __future__ import annotations

import sys
from collections import Counter
from pathlib import Path


def count_files_by_extension(root: Path) -> Counter[str]:
    """Scansiona *root* ricorsivamente e conta i file per estensione.

    I file senza estensione vengono contati sotto la chiave ``(senza estensione)``.
    Gli errori di permesso vengono gestiti silenziosamente (skip).

    Args:
        root: Directory radice da scansionare.

    Returns:
        Counter con estensione → conteggio.
    """
    counts: Counter[str] = Counter()

    for path in root.rglob("*"):
        try:
            if not path.is_file():
                continue
        except PermissionError:
            continue

        ext = path.suffix.lower() if path.suffix else "(senza estensione)"
        counts[ext] += 1

    return counts


def print_summary(counts: Counter[str]) -> None:
    """Stampa il riepilogo ordinato per conteggio decrescente."""
    if not counts:
        print("Nessun file trovato.")
        return

    total = sum(counts.values())
    print(f"\n{'Estensione':<25} {'Conteggio':>10} {'%':>8}")
    print("-" * 45)

    for ext, count in counts.most_common():
        pct = count / total * 100
        print(f"{ext:<25} {count:>10} {pct:>7.1f}%")

    print("-" * 45)
    print(f"{'TOTALE':<25} {total:>10} {100.0:>7.1f}%")
    print(f"\n{len(counts)} estensioni diverse, {total} file totali.\n")


def main() -> None:
    """Punto di ingresso principale."""
    root = Path("/home/stra/TeamOlimpo")

    if not root.is_dir():
        print(f"Errore: la directory '{root}' non esiste.", file=sys.stderr)
        sys.exit(1)

    counts = count_files_by_extension(root)
    print_summary(counts)


if __name__ == "__main__":
    main()
