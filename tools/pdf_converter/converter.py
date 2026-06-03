"""
Logica di conversione PDF -> Markdown per il tool pdf_converter.

Utilizza pymupdf4llm per la conversione e pymupdf per l'estrazione
dei metadati. Gestisce l'estrazione immagini e la preparazione
dell'output per il post-processing.
"""

from __future__ import annotations

import time
from pathlib import Path

from loguru import logger

from tools.pdf_converter.config import (
    ConversionConfig,
    PathConfig,
    TOOL_VERSION,
    conversion as default_conversion,
    paths as default_paths,
)
from tools.pdf_converter.models import ConversionResult, DocumentMetadata
from tools.pdf_converter.utils import (
    calculate_file_hash,
    count_images_in_dir,
    ensure_dir,
    extract_doc_id,
    slugify,
)


def extract_metadata(pdf_path: Path) -> DocumentMetadata:
    """
    Estrae i metadati da un file PDF usando pymupdf.

    Legge titolo, autore, soggetto, numero pagine e dimensione file.
    I campi testuali possono essere vuoti se il PDF non li contiene.

    Args:
        pdf_path: Path assoluto al file PDF

    Returns:
        Istanza DocumentMetadata popolata con i metadati estratti

    Raises:
        FileNotFoundError: se il file PDF non esiste
        RuntimeError: se pymupdf non riesce ad aprire il file
    """
    if not pdf_path.exists():
        raise FileNotFoundError(f"File PDF non trovato: {pdf_path}")

    try:
        import pymupdf  # noqa: PLC0415
    except ImportError as exc:
        raise ImportError("pymupdf non e' installato. Eseguire: uv add pymupdf") from exc

    logger.debug(f"Estrazione metadati da: {pdf_path.name}")

    doc = pymupdf.open(str(pdf_path))
    try:
        meta = doc.metadata or {}
        num_pages = doc.page_count
    finally:
        doc.close()

    return DocumentMetadata(
        filename=pdf_path.name,
        slug=extract_doc_id(pdf_path.name),
        pdf_path=pdf_path,
        title=meta.get("title", "") or "",
        author=meta.get("author", "") or "",
        subject=meta.get("subject", "") or "",
        num_pages=num_pages,
        file_size_bytes=pdf_path.stat().st_size,
        file_hash=calculate_file_hash(pdf_path),
    )


def convert_pdf(
    pdf_path: Path,
    path_config: PathConfig | None = None,
    conv_config: ConversionConfig | None = None,
) -> ConversionResult:
    """
    Converte un singolo file PDF in Markdown con estrazione immagini.

    Pipeline:
    1. Estrae i metadati del documento (titolo, autore, pagine)
    2. Crea le directory di output necessarie
    3. Esegue la conversione con pymupdf4llm (include le immagini)
    4. Salva il Markdown grezzo nel file di output
    5. Costruisce e ritorna il ConversionResult

    Il Markdown prodotto da questa funzione NON e' ancora post-processato:
    va passato a PostProcessor prima del salvataggio definitivo.

    Args:
        pdf_path: Path assoluto al file PDF da convertire
        path_config: Configurazione path (usa default se None)
        conv_config: Configurazione conversione (usa default se None)

    Returns:
        ConversionResult con status 'completed' o 'error'
    """
    try:
        import pymupdf4llm  # noqa: PLC0415
    except ImportError as exc:
        raise ImportError("pymupdf4llm non e' installato. Eseguire: uv add pymupdf4llm") from exc

    pc = path_config or default_paths
    cc = conv_config or default_conversion

    start_time = time.monotonic()

    # --- Estrazione metadati ---
    try:
        metadata = extract_metadata(pdf_path)
    except Exception as exc:
        logger.error(f"Impossibile leggere metadati da {pdf_path.name}: {exc}")
        # Metadati minimi di fallback per registrare l'errore nel DB
        slug = extract_doc_id(pdf_path.name)
        file_hash = ""
        if pdf_path.exists():
            try:
                file_hash = calculate_file_hash(pdf_path)
            except Exception:
                logger.debug(f"Impossibile calcolare hash per {pdf_path.name}")
        metadata = DocumentMetadata(
            filename=pdf_path.name,
            slug=slug,
            pdf_path=pdf_path,
            num_pages=1,
            file_size_bytes=pdf_path.stat().st_size if pdf_path.exists() else 0,
            file_hash=file_hash,
        )
        return ConversionResult(
            metadata=metadata,
            status="error",
            error_message=f"Errore lettura metadati: {exc}",
            processing_time_seconds=time.monotonic() - start_time,
        )

    # --- Preparazione path di output ---
    md_output_path = pc.output / f"{metadata.slug}.md"
    images_dir = pc.assets / metadata.slug

    # Crea le directory (idempotente)
    ensure_dir(pc.output)
    ensure_dir(images_dir)

    logger.info(
        f"Conversione: {pdf_path.name} ({metadata.num_pages} pag.) -> {md_output_path.name}"
    )

    # --- Conversione PDF -> Markdown ---
    # pymupdf4llm genera nomi immagine dal nome del PDF originale. Per le KBA
    # Emerson i nomi file superano spesso 200 caratteri, causando errori MAX_PATH
    # su Windows (limite 260 caratteri totali).
    # Soluzione: copiare il PDF in una temp dir con nome corto (<slug>.pdf) prima
    # della conversione. pymupdf4llm genera immagini con nome corto automaticamente.
    # La copia temporanea viene eliminata automaticamente all'uscita dal context manager.
    import shutil as _shutil  # noqa: PLC0415
    import tempfile as _tempfile  # noqa: PLC0415

    with _tempfile.TemporaryDirectory() as _tmp_dir:
        _short_pdf = Path(_tmp_dir) / f"{metadata.slug}.pdf"
        _shutil.copy2(str(pdf_path), str(_short_pdf))
        try:
            md_text: str = pymupdf4llm.to_markdown(
                doc=str(_short_pdf),
                write_images=cc.write_images,
                image_path=str(images_dir),
                image_format=cc.image_format,
                dpi=cc.dpi,
            )
        except Exception as exc:
            logger.error(f"Errore conversione {pdf_path.name}: {exc}")
            return ConversionResult(
                metadata=metadata,
                status="error",
                error_message=f"Errore pymupdf4llm: {exc}",
                processing_time_seconds=time.monotonic() - start_time,
            )

    # --- Rinomina immagini con nome breve e aggiorna riferimenti nel MD ---
    # pymupdf4llm genera nomi immagine dal nome del PDF originale (spesso lunghi
    # centinaia di caratteri). Li rinominiamo in <slug>-0001.png, <slug>-0002.png...
    # per evitare il limite MAX_PATH di Windows (260 caratteri).
    image_extensions = {".png", ".jpg", ".jpeg", ".gif", ".webp"}
    old_images = (
        sorted(
            f for f in images_dir.iterdir() if f.is_file() and f.suffix.lower() in image_extensions
        )
        if images_dir.exists()
        else []
    )

    for idx, old_path in enumerate(old_images, start=1):
        new_name = f"{metadata.slug}-{idx:04d}{old_path.suffix.lower()}"
        new_path = images_dir / new_name
        if old_path.name != new_name:
            md_text = md_text.replace(old_path.name, new_name)
            old_path.rename(new_path)
            logger.debug(f"Rinominata immagine: {old_path.name} -> {new_name}")

    # --- Salvataggio Markdown grezzo (sovrascrivibile dal post-processor) ---
    try:
        md_output_path.write_text(md_text, encoding="utf-8")
    except OSError as exc:
        logger.error(f"Impossibile scrivere {md_output_path}: {exc}")
        return ConversionResult(
            metadata=metadata,
            status="error",
            error_message=f"Errore scrittura file: {exc}",
            processing_time_seconds=time.monotonic() - start_time,
        )

    elapsed = time.monotonic() - start_time
    num_images = count_images_in_dir(images_dir)

    logger.success(
        f"Convertito: {pdf_path.name} in {elapsed:.2f}s ({num_images} immagini estratte)"
    )

    return ConversionResult(
        metadata=metadata,
        md_path=md_output_path,
        images_dir=images_dir if num_images > 0 else None,
        num_images=num_images,
        md_size_bytes=md_output_path.stat().st_size,
        processing_time_seconds=elapsed,
        status="completed",
    )
