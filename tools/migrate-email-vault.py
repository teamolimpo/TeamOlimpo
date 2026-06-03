#!/usr/bin/env python3
"""
Migrazione sicura del vault email dal percorso originale al nuovo vault in inglese.

Script per migrare directory specifiche da un vault sorgente a uno di destinazione,
con supporto per dry-run e logging completo. Evita sovrascritture di directory esistenti.

Uso:
    python migrate-email-vault.py [--dry-run]

Esempio:
    python migrate-email-vault.py --dry-run  # Mostra cosa verrebbe fatto
    python migrate-email-vault.py            # Esegue la migrazione
"""

import argparse
import logging
import sys
from pathlib import Path
import shutil


# Configurazione logging
logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)

# Handler per console
console_handler = logging.StreamHandler(sys.stdout)
console_handler.setLevel(logging.INFO)
console_formatter = logging.Formatter("%(asctime)s - %(levelname)s - %(message)s")
console_handler.setFormatter(console_formatter)
logger.addHandler(console_handler)

# Handler per file
log_file_path = Path(__file__).parent / "migrate-email-vault.log"
file_handler = logging.FileHandler(log_file_path, encoding="utf-8")
file_handler.setLevel(logging.INFO)
file_formatter = logging.Formatter("%(asctime)s - %(levelname)s - %(message)s")
file_handler.setFormatter(file_formatter)
logger.addHandler(file_handler)


def copy_tree_with_conflicts(src: Path, dst: Path, dry_run: bool, counters: dict[str, int]) -> None:
    """
    Copia ricorsivamente i file da src a dst, saltando i file esistenti.

    Args:
        src: Directory sorgente.
        dst: Directory destinazione.
        dry_run: Se True, simula.
        counters: Dizionario per contare copiati e saltati.
    """
    for item in src.rglob("*"):
        if item.is_file():
            rel_path = item.relative_to(src)
            dest_file = dst / rel_path
            dest_file.parent.mkdir(parents=True, exist_ok=True)
            if dest_file.exists():
                counters["saltati"] += 1
                logger.warning(f"File '{dest_file}' già esiste, saltato.")
            else:
                if dry_run:
                    logger.info(f"[DRY-RUN] Copierebbe '{item}' in '{dest_file}'.")
                else:
                    shutil.copy2(item, dest_file)
                    logger.info(f"Copiato '{item}' in '{dest_file}'.")
                counters["copiati"] += 1


def migrate_vault(source_root: Path, dest_root: Path, dry_run: bool = False) -> None:
    """
    Migra le directory specificate dal vault sorgente a quello di destinazione,
    copiando i file singoli e gestendo i conflitti.

    Args:
        source_root: Percorso radice del vault sorgente.
        dest_root: Percorso radice del vault di destinazione.
        dry_run: Se True, simula le operazioni senza eseguirle.

    Raises:
        ValueError: Se i percorsi non sono directory valide.
    """
    if not source_root.is_dir():
        raise ValueError(f"Il percorso sorgente {source_root} non è una directory valida.")
    if not dest_root.is_dir():
        raise ValueError(f"Il percorso destinazione {dest_root} non è una directory valida.")

    # Mappatura delle directory da migrare
    mappings = {
        "Inbox/emails": "Inbox/emails",
        "Persone": "People",
        "_templates": "_templates",
        "_review": "_review",
    }

    total_counters = {"copiati": 0, "saltati": 0}

    for src_rel, dst_rel in mappings.items():
        src_path = source_root / src_rel
        dst_path = dest_root / dst_rel

        if not src_path.exists():
            logger.info(f"Directory sorgente '{src_rel}' non esiste, saltata.")
            continue

        counters = {"copiati": 0, "saltati": 0}
        copy_tree_with_conflicts(src_path, dst_path, dry_run, counters)
        logger.info(
            f"Per '{src_rel}': copiati {counters['copiati']}, saltati {counters['saltati']}"
        )
        total_counters["copiati"] += counters["copiati"]
        total_counters["saltati"] += counters["saltati"]

    logger.info(f"Totale: copiati {total_counters['copiati']}, saltati {total_counters['saltati']}")


def main() -> None:
    """Punto di ingresso principale dello script."""
    parser = argparse.ArgumentParser(
        description="Migrazione sicura del vault email.",
        epilog="Usa --dry-run per simulare le operazioni.",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Simula le operazioni senza eseguirle (default: False).",
    )
    args = parser.parse_args()

    # Percorsi hardcoded come richiesto (in produzione, considerare config esterna)
    source_root = Path("/home/stra/TeamOlimpo/Inbox/working")
    dest_root = Path("/home/stra/TeamOlimpo/vaults/email")

    try:
        logger.info("Inizio migrazione vault email.")
        migrate_vault(source_root, dest_root, args.dry_run)
        logger.info("Migrazione completata." if not args.dry_run else "Simulazione completata.")
    except Exception as e:
        logger.error(f"Errore durante la migrazione: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()
