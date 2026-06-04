"""
Post-processing del Markdown generato dalla conversione PDF.

Applica una pipeline di pulizia e normalizzazione al testo Markdown grezzo
prodotto da pymupdf4llm, migliorando la leggibilita' e aggiungendo
metadati strutturati tramite frontmatter YAML.
"""

from __future__ import annotations

import re
from pathlib import Path

import yaml
from loguru import logger

from tools.pdf_converter.config import PostProcessingConfig, post_processing as default_pp
from tools.pdf_converter.models import ConversionResult
from tools.pdf_converter.utils import relative_path


def _collapse_blank_lines(text: str) -> str:
    """
    Riduce le sequenze di 3+ righe vuote consecutive a massimo 2.

    Args:
        text: Testo Markdown di input

    Returns:
        Testo con righe vuote collassate
    """
    return re.sub(r"\n{3,}", "\n\n", text)


def _remove_page_numbers(text: str) -> str:
    """
    Rimuove le righe che contengono solo un numero (tipicamente numeri di pagina PDF).

    Riconosce pattern come: "42", "  42  ", "-42-", "- 42 -".
    Non rimuove numeri che fanno parte di contenuto testuale.

    Args:
        text: Testo Markdown di input

    Returns:
        Testo senza righe-numero isolate
    """
    # Riga che contiene SOLO un numero (con eventuale whitespace o trattini intorno)
    return re.sub(r"^\s*[-–]?\s*\d+\s*[-–]?\s*$", "", text, flags=re.MULTILINE)


def _normalize_headings(text: str) -> str:
    """
    Normalizza la gerarchia degli heading Markdown.

    Problema comune: pymupdf4llm a volte genera heading che partono da ## o ###
    saltando il livello #. Questa funzione individua il livello minimo usato
    e, se non c'e' nessun H1, promuove tutti gli heading di un livello.

    Non modifica heading che gia' hanno una gerarchia corretta.

    Args:
        text: Testo Markdown di input

    Returns:
        Testo con heading normalizzati
    """
    # Trova tutti gli heading e i loro livelli
    heading_pattern = re.compile(r"^(#{1,6})\s", re.MULTILINE)
    matches = heading_pattern.findall(text)

    if not matches:
        return text

    # Livello minimo presente nel documento (es. se il minimo e' ##, e' livello 2)
    min_level = min(len(h) for h in matches)

    # Se il documento inizia gia' con H1 non e' necessario nulla
    if min_level == 1:
        return text

    # Promuovi tutti gli heading di (min_level - 1) livelli
    # per portare il minimo a H1
    promotion = min_level - 1

    def _promote_heading(match: re.Match) -> str:
        hashes = match.group(1)
        new_level = max(1, len(hashes) - promotion)
        return "#" * new_level + match.group(0)[len(hashes) :]

    return heading_pattern.sub(_promote_heading, text)


def _normalize_image_syntax(text: str, images_dir: Path) -> str:
    """
    Normalizza la sintassi wikilink per le immagini in sintassi Markdown standard.

    pymupdf4llm puo' produrre immagini come `![[nome.png]]` (wikilink senza path)
    oppure come `![](path/img.png)` (Markdown standard). Questa funzione converte
    i wikilink senza path in Markdown standard in modo che `_fix_image_paths()`
    riceva un formato uniforme da elaborare.

    Vengono convertiti solo i wikilink che:
    - Contengono un nome file con estensione immagine riconosciuta
    - Non hanno gia' un path esplicito (nessun `/` o `\` nel nome)

    Wikilink con path esplicito (`![[cartella/img.png]]`) e wikilink a note
    (senza estensione immagine) vengono lasciati invariati.

    Args:
        text: Testo Markdown di input
        images_dir: Path assoluto della cartella immagini del documento;
                    lo slug e' ricavato da `images_dir.name`

    Returns:
        Testo con wikilink immagine senza path convertiti in Markdown standard
    """
    slug = images_dir.name
    image_extensions = r"png|jpg|jpeg|gif|bmp|svg|webp"

    # Pattern: ![[nome.ext]] dove il nome NON contiene / o \
    # Il lookahead negativo garantisce che non ci sia gia' un path
    pattern = re.compile(
        r"!\[\[([^\[\]/\\]+\.(?:" + image_extensions + r"))\]\]",
        re.IGNORECASE,
    )

    def _to_markdown(match: re.Match) -> str:
        filename = match.group(1)
        return f"![](../assets/images/{slug}/{filename})"

    return pattern.sub(_to_markdown, text)


def _fix_image_paths(text: str, md_path: Path, images_dir: Path | None) -> str:
    """
    Aggiusta i path delle immagini nel Markdown per renderli relativi al file MD.

    pymupdf4llm salva le immagini con path assoluti o relativi alla CWD.
    Questo li converte in path relativi alla posizione del file Markdown,
    cosi funzionano in qualsiasi viewer (Obsidian, VS Code, GitHub).

    Args:
        text: Testo Markdown di input
        md_path: Path assoluto del file Markdown di output
        images_dir: Path assoluto della cartella immagini del documento

    Returns:
        Testo con path immagini corretti
    """
    if images_dir is None:
        return text

    # Calcola il path relativo dalla cartella del MD alla cartella immagini
    md_dir = md_path.parent

    try:
        # Path relativo da Converted/ a assets/images/slug/
        rel_images = relative_path(images_dir, md_dir)
    except Exception:
        logger.warning("Impossibile calcolare path relativo per le immagini")
        return text

    # Sostituisce i path assoluti della cartella immagini con il path relativo
    # Il pattern cerca qualsiasi path che punta alla cartella immagini
    abs_images_str = str(images_dir).replace("\\", "/")
    abs_images_str_win = str(images_dir)

    # Normalizza i separatori nel testo
    text = text.replace(abs_images_str_win, rel_images)
    text = text.replace(abs_images_str, rel_images)

    # Sostituisce i path CWD-relativi generati da pymupdf4llm.
    # Esempio: "Library/assets/images/<slug>/" oppure "Library\assets\images\<slug>\"
    # La CWD del processo e' la root del progetto, quindi il path CWD-relativo
    # e' la porzione di abs_images_str che segue il prefisso assoluto.
    # Lo ricaviamo cercando il marker "Library/" nel path assoluto posix.
    try:
        marker = "Library/"
        marker_idx = abs_images_str.find(marker)
        if marker_idx != -1:
            cwd_rel_posix = abs_images_str[marker_idx:]  # es. Library/assets/images/slug/
            cwd_rel_win = cwd_rel_posix.replace("/", "\\")  # es. Library\assets\images\slug\
            text = text.replace(cwd_rel_win, rel_images)
            text = text.replace(cwd_rel_posix, rel_images)
    except Exception:
        logger.warning("Impossibile sostituire path CWD-relativi delle immagini")

    return text


def _build_frontmatter(result: ConversionResult) -> str:
    """
    Costruisce il blocco frontmatter YAML per il file Markdown.

    Include titolo, autore, data di conversione, path della fonte PDF
    e numero di pagine. Il frontmatter e' compatibile con Obsidian,
    Jekyll e la maggior parte dei parser Markdown.

    Args:
        result: ConversionResult con metadati del documento

    Returns:
        Stringa con il blocco frontmatter completo (inclusi i delimitatori ---)
    """
    meta = result.metadata

    # Titolo: usa quello dai metadati PDF, altrimenti il nome file senza estensione
    title = meta.title if meta.title else Path(meta.filename).stem

    frontmatter_data: dict = {
        "title": title,
    }

    # Aggiunge kba_id se lo slug segue il pattern KBA Emerson (aa-nnnn-nnnn)
    if re.match(r"^[a-z]{2}-\d{4}-\d{4}$", meta.slug):
        frontmatter_data["kba_id"] = meta.slug.upper()

    frontmatter_data.update(
        {
            "source_pdf": meta.filename,
            "converted_at": result.converted_at,
            "num_pages": meta.num_pages,
            "tags": [],
        }
    )

    # Aggiunge autore solo se presente nei metadati
    if meta.author:
        frontmatter_data["author"] = meta.author

    # Aggiunge soggetto solo se presente nei metadati
    if meta.subject:
        frontmatter_data["subject"] = meta.subject

    # Aggiunge conteggio immagini se ne sono state estratte
    if result.num_images > 0:
        frontmatter_data["num_images"] = result.num_images

    yaml_str = yaml.dump(
        frontmatter_data,
        allow_unicode=True,
        default_flow_style=False,
        sort_keys=False,
    ).rstrip()

    return f"---\n{yaml_str}\n---\n\n"


def post_process(
    result: ConversionResult,
    config: PostProcessingConfig | None = None,
) -> ConversionResult:
    """
    Applica la pipeline di post-processing al file Markdown generato dalla conversione.

    Sequenza operazioni:
    1. Legge il Markdown grezzo dal file di output
    2. Rimuove numeri di pagina isolati (opzionale)
    3. Collassa righe vuote eccessive (opzionale)
    4. Normalizza la gerarchia degli heading (opzionale)
    5. Normalizza wikilink immagine senza path in Markdown standard
    6. Aggiusta i path delle immagini per renderli relativi
    7. Aggiunge il frontmatter YAML (opzionale)
    8. Riscrive il file con il contenuto processato

    Se la conversione e' fallita (status != 'completed') o il file MD
    non esiste, la funzione ritorna il risultato invariato.

    Args:
        result: ConversionResult prodotto dal converter
        config: Configurazione post-processing (usa default se None)

    Returns:
        ConversionResult aggiornato con la dimensione MD finale
    """
    if not result.success or result.md_path is None:
        logger.debug(
            f"Post-processing saltato per {result.metadata.filename} (status: {result.status})"
        )
        return result

    if not result.md_path.exists():
        logger.warning(f"File Markdown non trovato per post-processing: {result.md_path}")
        return result

    cfg = config or default_pp

    logger.debug(f"Post-processing: {result.md_path.name}")

    # Legge il Markdown grezzo
    text = result.md_path.read_text(encoding="utf-8")

    # --- Pipeline di pulizia ---
    if cfg.remove_page_numbers:
        text = _remove_page_numbers(text)

    if cfg.collapse_blank_lines:
        text = _collapse_blank_lines(text)

    if cfg.normalize_headings:
        text = _normalize_headings(text)

    # Normalizza wikilink immagine senza path in Markdown standard (sempre)
    if result.images_dir is not None:
        text = _normalize_image_syntax(text, result.images_dir)

    # Aggiusta path immagini (sempre, indipendentemente dalla config)
    text = _fix_image_paths(text, result.md_path, result.images_dir)

    # Pulizia finale: rimuove spazio bianco in testa al documento
    text = text.lstrip()

    # --- Aggiunta frontmatter YAML ---
    if cfg.add_frontmatter:
        frontmatter = _build_frontmatter(result)
        text = frontmatter + text

    # Riscrive il file processato
    result.md_path.write_text(text, encoding="utf-8")

    # Aggiorna la dimensione del file nel risultato
    result.md_size_bytes = result.md_path.stat().st_size

    logger.debug(f"Post-processing completato: {result.md_path.name} ({result.md_size_bytes} byte)")

    return result
