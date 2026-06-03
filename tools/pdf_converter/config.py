"""
Configurazione centralizzata per il tool pdf_converter.

Tutti i path sono relativi alla root del progetto PKM.
La root viene determinata automaticamente risalendo dal file corrente.
"""

from __future__ import annotations

from pathlib import Path

from tools.common.paths import project_root

# ---------------------------------------------------------------------------
# Root del progetto
# ---------------------------------------------------------------------------
PROJECT_ROOT: Path = project_root()


# ---------------------------------------------------------------------------
# Path di default (sovrascrivibili via argomenti CLI)
# ---------------------------------------------------------------------------
class PathConfig:
    """Configurazione dei path di lavoro del tool."""

    # Cartella di input: PDF da convertire
    inbox: Path = PROJECT_ROOT / "Team" / "Inbox"

    # Cartella di output: file Markdown generati
    output: Path = PROJECT_ROOT / "lib" / "documents"

    # Cartella immagini estratte
    assets: Path = PROJECT_ROOT / "lib" / "assets" / "images"

    # Database SQLite per l'indicizzazione
    database: Path = PROJECT_ROOT / "lib" / "data" / "pdf_index.db"

    # File di log
    log_file: Path = PROJECT_ROOT / "lib" / "data" / "pdf_converter.log"


# ---------------------------------------------------------------------------
# Opzioni di conversione
# ---------------------------------------------------------------------------
class ConversionConfig:
    """Parametri per la conversione PDF -> Markdown."""

    # Formato di output delle immagini estratte (png o jpg)
    image_format: str = "png"

    # Risoluzione delle immagini estratte in DPI
    dpi: int = 150

    # Estrai e salva le immagini durante la conversione
    write_images: bool = True


# ---------------------------------------------------------------------------
# Opzioni di post-processing
# ---------------------------------------------------------------------------
class PostProcessingConfig:
    """Parametri per la pulizia del Markdown generato."""

    # Aggiunge frontmatter YAML in testa al file Markdown
    add_frontmatter: bool = True

    # Normalizza la gerarchia degli heading (non salta livelli)
    normalize_headings: bool = True

    # Collassa 3+ righe vuote consecutive in 2
    collapse_blank_lines: bool = True

    # Rimuove numeri di pagina isolati (riga contenente solo un numero)
    remove_page_numbers: bool = True


# ---------------------------------------------------------------------------
# Versione del tool (usata per tracciamento nel DB)
# ---------------------------------------------------------------------------
TOOL_VERSION: str = "0.1.0"


# ---------------------------------------------------------------------------
# Istanze di default — usate dai moduli se non viene passata config custom
# ---------------------------------------------------------------------------
paths = PathConfig()
conversion = ConversionConfig()
post_processing = PostProcessingConfig()
