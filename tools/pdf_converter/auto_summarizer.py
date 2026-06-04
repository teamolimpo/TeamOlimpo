"""
Auto-Summarizer V1+V2 per il Progetto Chimera — Fase 2.3.

Genera pagine wiki per i documenti convertiti in ``Library/documents/``
usando TextRank (V2) con fallback al primo paragrafo (V1) per documenti
troppo corti.

Usage::

    from tools.pdf_converter.auto_summarizer import generate_wiki_page

    result = generate_wiki_page("Library/documents/mio-doc.md", force=True)
"""

from __future__ import annotations

import re
from datetime import datetime
from pathlib import Path
from typing import Any

import frontmatter
import yaml
from loguru import logger

from tools.knowledge_base.entity_extractor import extract_entities
from tools.pdf_converter.config import PROJECT_ROOT as _PROJECT_ROOT
from tools.pdf_converter.config import paths as default_paths

# ---------------------------------------------------------------------------
# Costanti
# ---------------------------------------------------------------------------

PROJECT_ROOT: Path = _PROJECT_ROOT
DOCUMENTS_DIR: Path = default_paths.output  # Library/documents/
WIKI_RESEARCH_BASE: Path = PROJECT_ROOT / "lib" / "Wiki" / "research"
WIKI_INDEX_PATH: Path = PROJECT_ROOT / "lib" / "Wiki" / "index.md"
WIKI_LOG_PATH: Path = PROJECT_ROOT / "lib" / "Wiki" / "log.md"

_HEADING_RE = re.compile(r"^(#{2,3})\s+(.+?)(?:\s+#+)?$", re.MULTILINE)

# ---------------------------------------------------------------------------
# 1. Lettura documento
# ---------------------------------------------------------------------------


def read_document(doc_path: str | Path) -> tuple[dict[str, Any], str]:
    """Legge un file .md e restituisce (frontmatter, body).

    Usa ``python-frontmatter`` per il parsing del frontmatter YAML.
    Il body viene restituito senza frontmatter.

    Args:
        doc_path: Path assoluto o relativo al file Markdown.

    Returns:
        Tupla (frontmatter_dict, body_string).

    Raises:
        FileNotFoundError: Se il file non esiste.
        ValueError: Se il frontmatter non è parsabile.
    """
    path = Path(doc_path).resolve()
    if not path.exists():
        raise FileNotFoundError(f"Documento non trovato: {path}")

    try:
        post = frontmatter.load(str(path))
    except Exception as exc:
        raise ValueError(f"Errore parsing frontmatter per {path}: {exc}") from exc

    frontmatter_data: dict[str, Any] = dict(post.metadata) if post.metadata else {}
    body: str = post.content

    return frontmatter_data, body


# ---------------------------------------------------------------------------
# 2. Heading tree
# ---------------------------------------------------------------------------


def extract_heading_tree(body: str) -> list[dict[str, Any]]:
    """Estrae l'albero degli heading dal body Markdown.

    Cerca heading H2 (``##``) e H3 (``###``) nel testo del body e restituisce
    una lista ordinata con level, text e children annidati.

    Args:
        body: Testo Markdown senza frontmatter.

    Returns:
        Lista di dict con chiavi ``level``, ``text``, ``children``.
    """
    raw_headings: list[dict[str, Any]] = []
    for match in _HEADING_RE.finditer(body):
        level = len(match.group(1))  # 2 or 3
        text = match.group(2).strip()
        raw_headings.append({"level": level, "text": text})

    if not raw_headings:
        return []

    # Build nested tree: H2 → root, H3 → children of last H2
    tree: list[dict[str, Any]] = []
    current_h2: dict[str, Any] | None = None

    for h in raw_headings:
        if h["level"] == 2:
            current_h2 = {"level": 2, "text": h["text"], "children": []}
            tree.append(current_h2)
        elif h["level"] == 3 and current_h2 is not None:
            current_h2["children"].append({"level": 3, "text": h["text"]})
        elif h["level"] == 3:
            # H3 without H2 parent — append as root
            tree.append({"level": 3, "text": h["text"]})

    return tree


def _heading_tree_to_markdown(tree: list[dict[str, Any]]) -> str:
    """Converte l'albero degli heading in bullet list Markdown."""
    if not tree:
        return "*(nessuna struttura)*"

    lines: list[str] = []
    for h in tree:
        if h["level"] == 2:
            lines.append(f"- **{h['text']}**")
            for child in h.get("children", []):
                lines.append(f"  - {child['text']}")
        else:
            lines.append(f"- {h['text']}")

    return "\n".join(lines)


# ---------------------------------------------------------------------------
# 3. Scoring frasi (TextRank V2 / fallback V1)
# ---------------------------------------------------------------------------


def _split_sentences(text: str) -> list[str]:
    """Split del testo in frasi.

    Usa regex per dividere su punteggiatura forte (. ! ?) seguita da spazio.
    Restituisce solo frasi con almeno 20 caratteri (dopo strip).

    Args:
        text: Testo da splittare.

    Returns:
        Lista di frasi pulite.
    """
    raw = re.split(r"(?<=[.!?])\s+", text)
    sentences: list[str] = []
    for s in raw:
        cleaned = s.strip()
        if len(cleaned) >= 20:
            sentences.append(cleaned)
    return sentences


def score_sentences(body: str, top_n: int = 5) -> list[str]:
    """Estrae le frasi più significative dal body usando TextRank (V2).

    **V2 (primario)**: TextRank con ``TfidfVectorizer`` + ``cosine_similarity``.

    1. Split in frasi con ``_split_sentences()``.
    2. Se ``<= top_n`` frasi: restituisce tutte (documento troppo corto per TextRank).
    3. ``TfidfVectorizer(stop_words='english', max_features=5000)`` → matrice TF-IDF.
    4. ``cosine_similarity`` → matrice di similarità.
    5. Score = somma similarità per ogni frase (PageRank semplificato).
    6. Top N frasi per score, ordinate per posizione nel documento.

    **V1 (fallback)**: primo paragrafo (prima frase >20 caratteri).
    Scatta quando:
    - ``len(frasi) < 3`` (documento troppo corto).
    - ``len(frasi) <= top_n`` (troppo corto per ranking).
    - Eccezione durante il calcolo V2.

    Args:
        body: Testo Markdown senza frontmatter.
        top_n: Numero di frasi da estrarre (default: 5).

    Returns:
        Lista di frasi ordinate per posizione nel documento.
    """
    # Pre-pulisci il body: rimuovi elementi non testuali
    text = body
    # Rimuovi blocchi code
    text = re.sub(r"```.*?```", "", text, flags=re.DOTALL)
    # Rimuovi immagini e link
    text = re.sub(r"!\[.*?\]\(.*?\)", "", text)
    text = re.sub(r"\[.*?\]\(.*?\)", "", text)
    # Rimuovi tabelle (righe che iniziano con |)
    text_lines = [line for line in text.split("\n") if not line.strip().startswith("|")]
    text = "\n".join(text_lines)
    # Rimuovi heading markers
    text = re.sub(r"^#+\s+", "", text, flags=re.MULTILINE)
    # Rimuovi blockquote markers
    text = re.sub(r"^>\s+", "", text, flags=re.MULTILINE)
    # Rimuovi separatori
    text = re.sub(r"^---+\s*$", "", text, flags=re.MULTILINE)
    # Collassa righe vuote eccessive
    text = re.sub(r"\n{3,}", "\n\n", text)

    sentences = _split_sentences(text)

    # V1 Fallback: documento troppo corto
    if len(sentences) < 3:
        logger.debug("V1 fallback: < 3 frasi, uso primo paragrafo")
        if sentences:
            return [sentences[0]]
        return ["*(documento senza contenuto testuale sufficiente)*"]

    if len(sentences) <= top_n:
        logger.debug(f"V1 fallback: {len(sentences)} frasi <= {top_n}, restituisco tutte")
        return sentences

    # V2: TextRank con TF-IDF + cosine similarity
    from sklearn.feature_extraction.text import TfidfVectorizer
    from sklearn.metrics.pairwise import cosine_similarity

    try:
        vectorizer = TfidfVectorizer(stop_words="english", max_features=5000)
        tfidf_matrix = vectorizer.fit_transform(sentences)
        similarity_matrix = cosine_similarity(tfidf_matrix)

        # Score = sum of similarities (PageRank semplificato, senza iterazione)
        # Sottrae 1 per escludere la self-similarity sulla diagonale
        scores = similarity_matrix.sum(axis=1) - 1

        # Top N per score, poi riordina per posizione originale
        ranked_indices = scores.argsort()[::-1][:top_n]
        ranked_indices_sorted = sorted(ranked_indices)

        top_sentences = [sentences[i] for i in ranked_indices_sorted]
        return top_sentences
    except Exception as exc:
        logger.warning(f"TextRank V2 fallito ({exc}), fallback a V1")
        if sentences:
            return [sentences[0]]
        return ["*(errore nella generazione del riassunto)*"]


# ---------------------------------------------------------------------------
# 4. Entity extraction
# ---------------------------------------------------------------------------


def extract_document_entities(body: str) -> list[dict[str, Any]]:
    """Estrae entità dal body del documento.

    Riutilizza ``entity_extractor.extract_entities()`` di
    ``tools/knowledge_base/`` che implementa un pipeline a 2 livelli
    (dizionario + pattern regex).

    Args:
        body: Testo Markdown del documento.

    Returns:
        Lista di entità con chiavi ``name``, ``type``, ``confidence``.
        Limitata a 15 entità per non appesantire la pagina.
    """
    # Prepara il testo: rimuovi solo code fence e frontmatter residuo
    text = re.sub(r"```.*?```", "", body, flags=re.DOTALL)
    text = re.sub(r"---.*?---", "", text, flags=re.DOTALL)

    raw_entities = extract_entities(text)

    # Normalizza in formato standard: name, type, confidence
    entities: list[dict[str, Any]] = []
    seen: set[str] = set()
    for ent in raw_entities:
        name: str = ent.get("entity_text", "")
        if not name or name.lower() in seen:
            continue
        seen.add(name.lower())
        # Confidence decresce con source_level
        confidence_map: dict[int, float] = {1: 0.9, 2: 0.6}
        entities.append(
            {
                "name": name,
                "type": ent.get("entity_type", "UNKNOWN"),
                "confidence": confidence_map.get(ent.get("source_level", 2), 0.5),
            }
        )

    return entities[:15]


def _entities_to_markdown(entities: list[dict[str, Any]]) -> str:
    """Converte la lista di entità in una tabella Markdown."""
    if not entities:
        return "*(nessuna entità rilevata)*"
    lines: list[str] = [
        "| Entità | Tipo | Confidenza |",
        "|--------|------|-----------|",
    ]
    for ent in entities:
        conf = f"{ent.get('confidence', 0.5):.0%}"
        lines.append(f"| {ent['name']} | {ent['type']} | {conf} |")
    return "\n".join(lines)


# ---------------------------------------------------------------------------
# 5. Wiki page builder
# ---------------------------------------------------------------------------


def _extract_tags(frontmatter_data: dict[str, Any], slug: str) -> list[str]:
    """Estrae tags dal frontmatter del documento.

    Combina i tags esistenti (se presenti) con 'wiki' e 'research'.

    Args:
        frontmatter_data: Dict del frontmatter del documento.
        slug: Slug del documento (non elaborato direttamente).

    Returns:
        Lista di tag deduplicata e ordinata.
    """
    tags: set[str] = {"wiki", "research"}

    existing_tags = frontmatter_data.get("tags", [])
    if isinstance(existing_tags, list):
        for t in existing_tags:
            if isinstance(t, str):
                tags.add(t.lower())

    return sorted(tags)


def build_wiki_page(metadata: dict[str, Any]) -> str:
    """Costruisce il Markdown completo di una pagina wiki.

    Args:
        metadata: Dict con le chiavi necessarie:
            - ``title``: Titolo del documento
            - ``slug``: Slug del documento
            - ``body``: Body del documento
            - ``source_pdf``: Nome del PDF originale (opzionale)
            - ``frontmatter``: Frontmatter originale del documento (opzionale)
            - ``summary_sentences``: Lista di frasi riassuntive
            - ``heading_tree``: Heading tree list
            - ``entities``: Entity list
            - ``date``: Data per il wiki (default: oggi)
            - ``author``: Autore (opzionale)
            - ``num_pages``: Numero pagine (opzionale)
            - ``num_images``: Numero immagini (opzionale)
            - ``converted_at``: Data conversione (opzionale)

    Returns:
        Stringa Markdown completa per la pagina wiki.
    """
    title: str = metadata.get("title", metadata.get("slug", "Untitled"))
    slug: str = metadata.get("slug", "unknown")
    source_pdf: str = metadata.get("source_pdf", "")
    fm: dict[str, Any] = metadata.get("frontmatter", {})

    # Data: usa quella fornita o oggi
    wiki_date: str = metadata.get("date", datetime.now().strftime("%Y-%m-%d"))

    # Tags
    tags = _extract_tags(fm, slug)
    tags_yaml = yaml.dump(tags, default_flow_style=True).strip()

    # Riassunto
    summary_sentences: list[str] = metadata.get("summary_sentences", [])
    if summary_sentences:
        summary = " ".join(summary_sentences)
    else:
        summary = "*(riassunto non disponibile)*"

    # Heading tree
    heading_tree: list[dict[str, Any]] = metadata.get("heading_tree", [])
    heading_md = _heading_tree_to_markdown(heading_tree)

    # Entità
    entities: list[dict[str, Any]] = metadata.get("entities", [])
    entities_md = _entities_to_markdown(entities)

    # Tags inline
    tags_str = ", ".join(f"#{t}" for t in tags)

    # Tabella metadati
    meta_rows: list[str] = []
    meta_rows.append(f"| **Titolo** | {title} |")
    if metadata.get("author"):
        meta_rows.append(f"| **Autore** | {metadata['author']} |")
    if source_pdf:
        meta_rows.append(f"| **Fonte** | {source_pdf} |")
    if metadata.get("num_pages") is not None:
        meta_rows.append(f"| **Pagine** | {metadata['num_pages']} |")
    if metadata.get("num_images") is not None:
        meta_rows.append(f"| **Immagini** | {metadata['num_images']} |")
    if metadata.get("converted_at"):
        meta_rows.append(f"| **Convertito** | {metadata['converted_at']} |")
    meta_rows.append(f"| **Slug** | `{slug}` |")
    meta_rows.append(f"| **Data Wiki** | {wiki_date} |")

    meta_table = "\n".join(meta_rows)

    return f"""---
title: "{title}"
tags: {tags_yaml}
cssclasses: [wiki-research]
date: {wiki_date}
source: {source_pdf}
doc_slug: {slug}
status: auto-generated
---

# {title}

> **Riassunto**: {summary}

## Metadati

| Campo | Valore |
|-------|--------|
{meta_table}

## Struttura del Documento

{heading_md}

## Parole Chiave

{tags_str}

## Entità Rilevanti

{entities_md}

## Collegamenti

- Fonte originale: [[{slug}]]

---
> Pagina generata automaticamente da Chimera Auto-Summarizer Fase 2.3
"""


# ---------------------------------------------------------------------------
# 6. Write wiki page
# ---------------------------------------------------------------------------


def write_wiki_page(markdown: str, slug: str, force: bool = False) -> str | None:
    """Scrive la pagina wiki su disco.

    Path: ``Library/Wiki/research/YYYY/MM/<slug>.md``.
    La directory viene creata se non esiste.

    Args:
        markdown: Contenuto Markdown della pagina.
        slug: Slug del documento (usato come nome file).
        force: Se True, sovrascrive pagina esistente.
               Se False, salta se il file esiste già.

    Returns:
        Path relativo della wiki page creata, oppure None se saltato.
    """
    today = datetime.now()
    year = today.strftime("%Y")
    month = today.strftime("%m")

    target_dir = WIKI_RESEARCH_BASE / year / month
    target_dir.mkdir(parents=True, exist_ok=True)

    target_path = target_dir / f"{slug}.md"

    if target_path.exists() and not force:
        logger.info(f"Wiki page già esistente (usa --force per sovrascrivere): {target_path}")
        return None

    target_path.write_text(markdown, encoding="utf-8")
    logger.info(f"Wiki page creata: {target_path}")

    # Restituisci path relativo al progetto
    return str(target_path.relative_to(PROJECT_ROOT))


# ---------------------------------------------------------------------------
# 7. Index & Log updates
# ---------------------------------------------------------------------------


def update_index(slug: str, title: str, wiki_path: str) -> None:
    """Aggiorna ``Wiki/index.md`` aggiungendo una riga nella tabella Research.

    Aggiunge la riga solo se non è già presente (evita duplicati).
    Se la tabella non esiste ancora (c'è solo placeholder), la crea.

    Args:
        slug: Slug del documento.
        title: Titolo del documento.
        wiki_path: Path relativo della wiki page.
    """
    if not WIKI_INDEX_PATH.exists():
        logger.warning(f"Index non trovato: {WIKI_INDEX_PATH}")
        return

    content = WIKI_INDEX_PATH.read_text(encoding="utf-8")

    # Controlla se già presente
    if f"[[{slug}]]" in content:
        logger.debug(f"Index già aggiornato per {slug}")
        return

    # Costruisce il wikilink dal path relativo
    # Es: "Library/Wiki/research/2026/05/slug.md" → "research/2026/05/slug"
    link = wiki_path.replace(".md", "")
    # Rimuovi il prefisso "Library/Wiki/" se presente
    link = link.removeprefix("Library/Wiki/")
    wiki_date = datetime.now().strftime("%Y-%m-%d")

    # Cerca la sezione ## Research
    research_match = re.search(
        r"(## Research\n+)(.*?)(?=\n## |\Z)",
        content,
        re.DOTALL,
    )

    if not research_match:
        logger.warning(f"Sezione Research non trovata in {WIKI_INDEX_PATH}")
        return

    header = research_match.group(1)
    body_section = research_match.group(2).strip()

    table_header = (
        "| Pagina | Summary | Ultimo aggiornamento |\n|--------|---------|---------------------|"
    )
    new_row = f"| [[{link}|{title}]] | {title} | {wiki_date} |"

    # Se il corpo è vuoto o ha solo placeholder
    if not body_section or "(nessuna" in body_section:
        new_section = f"{header}{table_header}\n| {new_row.lstrip('| ')}\n"
    else:
        # Verifica se la tabella esiste già
        if body_section.startswith("| Pagina |"):
            # Ha già una tabella — aggiungi riga
            new_body = body_section
            if not body_section.endswith(new_row):
                new_body = body_section.rstrip() + "\n" + new_row
            new_section = f"{header}{new_body}\n"
        else:
            # Ha altro contenuto — aggiungi tabella dopo
            new_section = f"{header}{table_header}\n{new_row}\n\n{body_section}\n"

    content = content[: research_match.start()] + new_section + content[research_match.end() :]
    WIKI_INDEX_PATH.write_text(content, encoding="utf-8")
    logger.info(f"Index aggiornato: {slug} → {link}")


def update_log(slug: str, title: str) -> None:
    """Aggiorna ``Wiki/log.md`` con una entry cronologica.

    Args:
        slug: Slug del documento.
        title: Titolo del documento.
    """
    if not WIKI_LOG_PATH.exists():
        logger.warning(f"Log non trovato: {WIKI_LOG_PATH}")
        return

    content = WIKI_LOG_PATH.read_text(encoding="utf-8")

    # Controlla se già presente (cerca slug sia come basename che in wikilink)
    if f"[[{slug}]]" in content or f"/{slug}]]" in content:
        logger.debug(f"Log già aggiornato per {slug}")
        return

    today = datetime.now().strftime("%Y-%m-%d")
    month_path = datetime.now().strftime("%Y/%m")

    entry = (
        f"\n## [{today}] research | Pagina wiki generata per: {title}\n"
        f"- Creata [[research/{month_path}/{slug}]] da conversione PDF\n"
        f"- Aggiornato index.md con riga nella tabella Research\n"
    )

    content += entry
    WIKI_LOG_PATH.write_text(content, encoding="utf-8")
    logger.info(f"Log aggiornato: {slug}")


# ---------------------------------------------------------------------------
# 8. Funzione principale
# ---------------------------------------------------------------------------


def generate_wiki_page(
    doc_path: str | Path,
    force: bool = False,
    dry_run: bool = False,
) -> dict[str, Any]:
    """Genera una pagina wiki per un documento convertito.

    Pipeline completa:

    1. Legge il documento (frontmatter + body).
    2. Costruisce l'albero degli heading.
    3. Esegue TextRank (V2) o fallback (V1) per il riassunto.
    4. Estrae entità con ``entity_extractor``.
    5. Costruisce la pagina wiki Markdown.
    6. Scrive su disco (se non dry_run).
    7. Aggiorna ``index.md`` e ``log.md`` (se non dry_run).

    Args:
        doc_path: Path al file .md del documento convertito.
        force: Se True, sovrascrive wiki page esistente.
        dry_run: Se True, mostra output senza scrivere.

    Returns:
        Dict con risultato: ``{slug, title, wiki_path, status}``.
        ``status`` può essere ``"created"``, ``"skipped"``, ``"dry_run"``,
        ``"error"``.
    """
    path = Path(doc_path).resolve()
    slug = path.stem

    try:
        # 1. Lettura documento
        fm, body = read_document(path)
        title = fm.get("title") or path.stem
        logger.info(f"Processando: {title} ({slug})")

        # 2. Heading tree
        heading_tree = extract_heading_tree(body)

        # 3. Scoring frasi
        summary_sentences = score_sentences(body, top_n=5)

        # 4. Entity extraction
        entities = extract_document_entities(body)

        # 5. Build metadata
        source_pdf: str = str(fm.get("source_pdf") or fm.get("source", ""))
        converted_at: str = str(fm.get("converted_at") or fm.get("date", ""))
        date_val = fm.get("date")
        if isinstance(date_val, datetime):
            wiki_date = date_val.strftime("%Y-%m-%d")
        elif isinstance(date_val, str):
            wiki_date = date_val[:10]
        else:
            wiki_date = datetime.now().strftime("%Y-%m-%d")

        metadata: dict[str, Any] = {
            "title": title,
            "slug": slug,
            "body": body,
            "source_pdf": source_pdf,
            "frontmatter": fm,
            "summary_sentences": summary_sentences,
            "heading_tree": heading_tree,
            "entities": entities,
            "date": wiki_date,
            "author": str(fm.get("author", "")),
            "num_pages": fm.get("num_pages"),
            "num_images": fm.get("num_images"),
            "converted_at": converted_at,
        }

        # 6. Build wiki markdown
        wiki_md = build_wiki_page(metadata)

        if dry_run:
            preview = wiki_md[:600]
            logger.info(f"[DRY-RUN] Wiki page per '{slug}':\n{preview}")
            wiki_path_str = f"Library/Wiki/research/{datetime.now().strftime('%Y/%m')}/{slug}.md"
            return {
                "slug": slug,
                "title": title,
                "wiki_path": wiki_path_str,
                "status": "dry_run",
            }

        # 7. Write wiki page
        wiki_path = write_wiki_page(wiki_md, slug, force=force)
        if wiki_path is None:
            return {
                "slug": slug,
                "title": title,
                "wiki_path": (
                    f"Library/Wiki/research/{datetime.now().strftime('%Y/%m')}/{slug}.md"
                ),
                "status": "skipped",
            }

        # 8. Update index and log
        update_index(slug, title, wiki_path)
        update_log(slug, title)

        return {
            "slug": slug,
            "title": title,
            "wiki_path": wiki_path,
            "status": "created",
        }

    except Exception as exc:
        logger.error(f"Auto-summarizer fallito per {slug}: {exc}")
        return {
            "slug": slug,
            "title": path.stem,
            "wiki_path": "",
            "status": "error",
            "error": str(exc),
        }


def generate_all_wiki_pages(
    force: bool = False,
    dry_run: bool = False,
) -> list[dict[str, Any]]:
    """Genera pagine wiki per tutti i documenti convertiti.

    Args:
        force: Se True, sovrascrive pagine esistenti.
        dry_run: Se True, mostra output senza scrivere.

    Returns:
        Lista di risultati (uno per documento).
    """
    documents_dir = DOCUMENTS_DIR
    if not documents_dir.exists():
        logger.warning(f"Directory documenti non trovata: {documents_dir}")
        return []

    md_files = sorted(documents_dir.glob("*.md"))
    results: list[dict[str, Any]] = []

    for md_file in md_files:
        result = generate_wiki_page(md_file, force=force, dry_run=dry_run)
        results.append(result)

    return results
