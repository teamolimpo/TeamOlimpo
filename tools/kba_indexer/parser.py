"""
Parser per i file batch prodotti da tools.consulto.

Ogni file ha:
- Frontmatter YAML con metadati del test (provider, model, kba, test_date, ...)
- Body con il JSON dell'analisi AI racchiuso in ```json ... ```

Il parser estrae il JSON, mappa i campi al formato del record Dike
e restituisce un dizionario pronto per writer.py.
"""

from __future__ import annotations

import json
import re
from datetime import date
from pathlib import Path
from typing import Any

import yaml
from loguru import logger

from tools.kba_indexer.config import DOCUMENTS_DIR

# Regex per estrarre il blocco JSON dal body Markdown
_JSON_BLOCK_RE = re.compile(r"```json\s*([\s\S]*?)\s*```", re.MULTILINE)

# Regex per estrarre il frontmatter YAML (tra i primi ---)
_FRONTMATTER_RE = re.compile(r"\A---\s*\n([\s\S]*?)\n---\s*\n", re.MULTILINE)


def _extract_frontmatter(text: str) -> dict[str, Any]:
    """
    Estrae e parsa il frontmatter YAML da un file Markdown.

    Args:
        text: Contenuto completo del file MD.

    Returns:
        Dizionario con i campi del frontmatter, o {} se assente.
    """
    match = _FRONTMATTER_RE.match(text)
    if not match:
        return {}
    try:
        result = yaml.safe_load(match.group(1))
        return result if isinstance(result, dict) else {}
    except yaml.YAMLError as exc:
        logger.warning(f"Frontmatter YAML non valido: {exc}")
        return {}


def _sanitize_json(raw: str) -> str:
    """
    Applica correzioni minime al JSON grezzo prodotto da LLM.

    Problemi noti:
    - ``"adjustment": +1`` — JSON non ammette il segno + unario sui numeri.
      Soluzione: rimuove il + che precede un numero dopo ':' o ','

    Args:
        raw: Stringa JSON grezza.

    Returns:
        Stringa JSON con le correzioni applicate.
    """
    # Rimuove il segno + unario in contesti numerici (es. +1, +0.5)
    # Pattern: segno + preceduto da separatore JSON (:, ,, [) + whitespace
    sanitized = re.sub(r"([:,\[]\s*)\+(\d)", r"\1\2", raw)
    return sanitized


def _extract_json_block(text: str) -> dict[str, Any]:
    """
    Estrae e parsa il primo blocco ```json ... ``` dal body.

    Applica sanitizzazione automatica per correggere output LLM non-standard
    (es. segni + unari nei numeri).

    Args:
        text: Contenuto del body Markdown (senza frontmatter).

    Returns:
        Dizionario con i dati JSON.

    Raises:
        ValueError: Se nessun blocco JSON viene trovato.
        json.JSONDecodeError: Se il JSON e' malformato anche dopo sanitizzazione.
    """
    match = _JSON_BLOCK_RE.search(text)
    if not match:
        raise ValueError("Nessun blocco ```json``` trovato nel file")
    raw = match.group(1).strip()
    sanitized = _sanitize_json(raw)
    return json.loads(sanitized)


def _kba_id_to_slug(kba_id: str) -> str:
    """
    Converte un KBA ID nel formato slug file.

    Esempi:
        "NK-2400-0150" -> "nk-2400-0150"

    Args:
        kba_id: Identificatore KBA in maiuscolo (es. "NK-2400-0150").

    Returns:
        Slug in minuscolo.
    """
    return kba_id.strip().lower()


def _read_document_title(slug: str) -> str:
    """
    Legge il titolo dal frontmatter del documento Markdown convertito.

    Cerca il file lib/documents/<slug>.md e ne estrae il campo 'title'.

    Args:
        slug: Slug del documento (es. "nk-2400-0150").

    Returns:
        Titolo estratto, o stringa vuota se il file non esiste o non ha titolo.
    """
    doc_path = DOCUMENTS_DIR / f"{slug}.md"
    if not doc_path.exists():
        logger.debug(f"Documento sorgente non trovato: {doc_path}")
        return ""
    try:
        content = doc_path.read_text(encoding="utf-8")
        fm = _extract_frontmatter(content)
        return str(fm.get("title", "")) or ""
    except OSError as exc:
        logger.warning(f"Impossibile leggere {doc_path}: {exc}")
        return ""


def _derive_tags(problem_type: str, slug: str) -> list[str]:
    """
    Deriva i tag del record a partire dal tipo di problema e dallo slug.

    Args:
        problem_type: Valore del campo problem_type nel JSON (es. "security_vulnerability").
        slug: Slug del documento (es. "nk-2400-0150").

    Returns:
        Lista di tag normalizzati.
    """
    tags: list[str] = []

    # Tag dal problem_type (es. "security_vulnerability" -> "security")
    if problem_type:
        primary = problem_type.split("_")[0]
        if primary:
            tags.append(primary)

    # Tag dallo slug: estrai la prima parola alfabetica dopo il codice numerico
    # es. "nk-2400-0150" non ha parole descrittive — usiamo solo il tipo
    # Per slug con parole significative (es. "nk-workstation-recovery") le estraiamo
    parts = slug.split("-")
    for part in parts:
        if part.isalpha() and len(part) > 2 and part not in tags:
            tags.append(part)

    return tags


def _derive_impact_domains(red_flags: list[str]) -> list[str]:
    """
    Deriva i domini di impatto a partire dai red_flags del JSON.

    Euristica best-effort: cerca parole chiave nei flag.

    Args:
        red_flags: Lista di stringhe descrittive dei rischi.

    Returns:
        Lista di domini (subset di: availability, integrity, confidentiality).
    """
    domains: set[str] = set()
    keywords_map = {
        "availability": ["availab", "uptime", "downtime", "disruption", "outage", "crash"],
        "integrity": ["integr", "corrupt", "tamper", "modif", "unauthorized"],
        "confidentiality": ["confidenti", "data leak", "exfiltrat", "disclosure", "sensitiv"],
    }
    combined = " ".join(red_flags).lower()
    for domain, keywords in keywords_map.items():
        if any(kw in combined for kw in keywords):
            domains.add(domain)
    return sorted(domains)


def _parse_json_batch(file_path: Path) -> tuple[str, str, dict[str, Any]]:
    """
    Parsa un file batch in formato .json o .txt (output diretto di tools.consulto).

    Il nome file segue il pattern <slug>-<provider>.json, es. nk-2400-0150-grok.json.
    Il contenuto e' JSON puro (senza frontmatter ne' code block).

    Args:
        file_path: Path al file .json o .txt.

    Returns:
        Tupla (kba_id, provider, ai_data).
    """
    # Estrae slug e provider dal nome file: <slug>-<provider>.json
    # Il provider e' l'ultima parte dopo l'ultimo trattino
    stem = file_path.stem  # es. "nk-2400-0150-grok"
    last_dash = stem.rfind("-")
    if last_dash == -1:
        raise ValueError(
            f"Nome file non riconoscibile (atteso <slug>-<provider>.json): {file_path.name}"
        )

    slug = stem[:last_dash]  # es. "nk-2400-0150"
    provider = stem[last_dash + 1 :]  # es. "grok"

    # Deriva kba_id dallo slug (se segue pattern AA-NNNN-NNNN)
    kba_match = re.match(r"^[a-z]{2}-\d{4}-\d{4}$", slug)
    kba_id = slug.upper() if kba_match else slug

    content = file_path.read_text(encoding="utf-8")

    # Gestisce sia JSON puro che JSON avvolto in ```json...``` (formato legacy .txt)
    json_block = re.search(r"```json\s*([\s\S]*?)\s*```", content)
    raw = json_block.group(1).strip() if json_block else content.strip()

    sanitized = _sanitize_json(raw)
    try:
        ai_data = json.loads(sanitized)
    except json.JSONDecodeError:
        # "Extra data": il provider ha aggiunto testo dopo il JSON.
        # raw_decode() legge il primo oggetto valido e ignora il resto.
        decoder = json.JSONDecoder()
        ai_data, _ = decoder.raw_decode(sanitized.lstrip())

    return kba_id, provider, ai_data


def parse_batch_file(file_path: Path) -> dict[str, Any]:
    """
    Parsa un file batch e restituisce un dizionario con tutti i campi
    necessari per scrivere un record nel catalogo KBA.

    Supporta due formati:
    - .txt: JSON grezzo prodotto da tools.consulto (nome file: <slug>-<provider>.txt)
    - .md: Markdown con frontmatter YAML + blocco ```json``` (formato legacy)

    Args:
        file_path: Path assoluto al file batch.

    Returns:
        Dizionario con i campi del record.

    Raises:
        ValueError: Se il file non contiene dati validi.
        json.JSONDecodeError: Se il JSON e' malformato.
        OSError: Se il file non e' leggibile.
    """
    if file_path.suffix.lower() in {".json", ".txt"}:
        kba_id, provider, ai_data = _parse_json_batch(file_path)
        slug = _kba_id_to_slug(kba_id)
        model = "unknown"
    else:
        content = file_path.read_text(encoding="utf-8")

        frontmatter = _extract_frontmatter(content)
        if not frontmatter:
            raise ValueError(f"Frontmatter YAML mancante o non valido in {file_path.name}")

        kba_raw = frontmatter.get("kba")
        if not kba_raw:
            raise ValueError(f"Campo 'kba' mancante nel frontmatter di {file_path.name}")

        kba_id = str(kba_raw).strip()
        slug = _kba_id_to_slug(kba_id)
        provider = str(frontmatter.get("provider", "unknown")).strip()
        model = str(frontmatter.get("model", "unknown")).strip()

        ai_data = _extract_json_block(content)

    title = _read_document_title(slug)
    today = date.today().isoformat()

    problem_type = str(ai_data.get("problem_type", ""))
    tags = _derive_tags(problem_type, slug)

    red_flags: list[str] = ai_data.get("red_flags", [])
    impact_domains = _derive_impact_domains(red_flags)

    # Normalizza fix_reference: rimuove prefissi descrittivi se presenti
    # es. "Knowledge Base Article NK-2400-0160" -> "NK-2400-0160"
    fix_ref_raw = str(ai_data.get("fix_reference", ""))
    # Cerca pattern NK-XXXX-XXXX o simili nell'eventuale testo libero
    fix_ref_match = re.search(r"[A-Z]{2,}-\d{4}-\d{4}", fix_ref_raw)
    fix_reference = fix_ref_match.group(0) if fix_ref_match else fix_ref_raw

    return {
        # Identificazione
        "kba_id": kba_id,
        "title": title,
        "source_file": f"lib/documents/{slug}.md",
        "analyzed_at": today,
        # Classificazione
        "emerson_category": str(ai_data.get("emerson_category", "")),
        "risk_score": ai_data.get("final_risk_score", ai_data.get("risk_score", 0.0)),
        "risk_level": str(ai_data.get("risk_level", "")),
        # Scoring dettagliato
        "severity": ai_data.get("severity_score", 0),
        "occurrence": ai_data.get("occurrence_score", 0),
        "detectability": ai_data.get("detectability_score", 0),
        # Classificazione del problema
        "problem_type": problem_type,
        "architecture_level": ai_data.get("architecture_level", 0),
        "impact_domains": impact_domains,
        # Componenti
        "affected_products": ai_data.get("affected_products", []),
        "affected_versions": [],
        # Mitigazioni
        "workaround_available": bool(ai_data.get("workaround_available", False)),
        "workaround_complexity": str(ai_data.get("workaround_complexity", "")),
        "fix_available": bool(ai_data.get("fix_available", False)),
        "fix_reference": fix_reference,
        "fix_versions": [str(v) for v in ai_data.get("fix_versions", []) if v],
        # Metadati
        "date_published": "",
        "author": "",
        "tags": tags,
        # Confidence
        "confidence": str(ai_data.get("confidence_level", "")),
        "confidence_note": str(ai_data.get("confidence_note", "")),
        # Tracciabilita' batch
        "source": f"batch-{provider}",
        "analyzed_by_provider": provider,
        "analyzed_by_model": model,
        # Campi per il body MD (non finiscono nel frontmatter)
        "_body": {
            "kba_problem_summary": str(ai_data.get("kba_problem_summary", "")),
            "severity_justification": str(ai_data.get("severity_justification", "")),
            "occurrence_justification": str(ai_data.get("occurrence_justification", "")),
            "detectability_justification": str(ai_data.get("detectability_justification", "")),
            "risk_score_calculation": str(ai_data.get("risk_score_calculation", "")),
            "modifiers_applied": ai_data.get("modifiers_applied", []),
            "workaround_description": str(ai_data.get("workaround_description", "")),
            "operational_recommendation": str(ai_data.get("operational_recommendation", "")),
            "notes": str(ai_data.get("notes", "")),
            "divergence_from_emerson": bool(ai_data.get("divergence_from_emerson", False)),
            "divergence_explanation": str(ai_data.get("divergence_explanation", "")),
        },
    }
