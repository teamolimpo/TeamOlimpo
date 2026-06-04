"""
Utility condivise per il tool pdf_converter.

Funzioni di supporto per generazione slug, gestione path
e altre operazioni comuni ai moduli del pacchetto.
"""

from __future__ import annotations

import hashlib
import os
import re
from pathlib import Path


def slugify(text: str, max_length: int = 60) -> str:
    """
    Genera uno slug URL-safe da un nome file o stringa generica.

    Rimuove l'estensione se presente, converte in lowercase,
    sostituisce spazi e caratteri speciali con trattini,
    collassa trattini multipli consecutivi.

    Il risultato viene troncato a max_length caratteri per evitare
    path troppo lunghi su Windows (limite MAX_PATH = 260 caratteri).
    Il troncamento avviene sul confine di parola (trattino) piu' vicino
    per non spezzare token a meta'.

    Args:
        text: Stringa di input (nome file, titolo, ecc.)
        max_length: Lunghezza massima dello slug (default: 60)

    Returns:
        Slug normalizzato, es. "report-vendite-q1-2026"

    Examples:
        >>> slugify("Report Vendite Q1 2026.pdf")
        'report-vendite-q1-2026'
        >>> slugify("Analisi_Costi & Benefici")
        'analisi-costi-benefici'
    """
    # Rimuove l'estensione del file se presente
    stem = Path(text).stem
    # Lowercase
    slug = stem.lower()
    # Rimuove caratteri non alfanumerici (eccetto trattini e underscore)
    slug = re.sub(r"[^\w\s-]", "", slug)
    # Converte spazi e underscore in trattini
    slug = re.sub(r"[\s_]+", "-", slug)
    # Collassa trattini multipli consecutivi
    slug = re.sub(r"-+", "-", slug)
    # Rimuove trattini iniziali e finali
    slug = slug.strip("-")
    # Tronca a max_length sul confine di parola piu' vicino
    if len(slug) > max_length:
        slug = slug[:max_length].rsplit("-", 1)[0]
    return slug


def extract_doc_id(filename: str) -> str:
    """
    Estrae l'ID documento dalla prima parte del nome file, se presente.

    I documenti KBA Emerson seguono il pattern AA-NNNN-NNNN (es. NK-1000-0109).
    Se il pattern e' riconoscibile, viene usato come ID breve e univoco.
    Altrimenti si usa lo slug troncato come fallback.

    Args:
        filename: Nome del file (con o senza estensione)

    Returns:
        ID breve in lowercase (es. "nk-1000-0109") o slug troncato

    Examples:
        >>> extract_doc_id("NK-1000-0109 - The Error Cannot generate SSPI.pdf")
        'nk-1000-0109'
        >>> extract_doc_id("report-annuale-2026.pdf")
        'report-annuale-2026'
    """
    stem = Path(filename).stem
    match = re.match(r"^([A-Za-z]{2}-\d{4}-\d{4})", stem)
    if match:
        return match.group(1).lower()
    return slugify(stem)


def ensure_dir(path: Path) -> Path:
    """
    Crea la directory specificata (e tutte le parent) se non esiste.

    Operazione idempotente: non lancia errori se la directory esiste gia'.

    Args:
        path: Path della directory da creare

    Returns:
        Lo stesso path ricevuto in input (per chaining)
    """
    path.mkdir(parents=True, exist_ok=True)
    return path


def count_images_in_dir(images_dir: Path) -> int:
    """
    Conta i file immagine presenti in una directory.

    Considera solo file con estensione .png, .jpg, .jpeg, .gif, .webp.

    Args:
        images_dir: Path della directory da analizzare

    Returns:
        Numero di file immagine trovati. 0 se la directory non esiste.
    """
    if not images_dir.exists():
        return 0

    image_extensions = {".png", ".jpg", ".jpeg", ".gif", ".webp"}
    return sum(
        1 for f in images_dir.iterdir() if f.is_file() and f.suffix.lower() in image_extensions
    )


def relative_path(path: Path, base: Path) -> str:
    """
    Calcola il path relativo di `path` rispetto a `base`.

    Usa `os.path.relpath()` che gestisce correttamente la navigazione verso
    l'alto con `..`, anche quando le due directory non sono in relazione
    parent-child (es. Library/documents/ → Library/assets/images/slug/).

    Args:
        path: Path da relativizzare
        base: Directory base di riferimento

    Returns:
        Stringa con path relativo (separatori Unix), es. '../assets/images/slug'
    """
    return os.path.relpath(path, base).replace("\\", "/")


def calculate_file_hash(file_path: Path) -> str:
    """
    Calcola l'hash SHA256 del file specificato.

    Legge il file in chunks per gestire file di grandi dimensioni senza
    caricare tutto in memoria.

    Args:
        file_path: Path al file da hashare

    Returns:
        Stringa esadecimale con l'hash SHA256

    Raises:
        FileNotFoundError: se il file non esiste
        OSError: se si verifica un errore di I/O durante la lettura
    """
    if not file_path.exists():
        raise FileNotFoundError(f"File non trovato: {file_path}")

    sha256 = hashlib.sha256()
    with open(file_path, "rb") as f:
        for chunk in iter(lambda: f.read(8192), b""):
            sha256.update(chunk)
    return sha256.hexdigest()
