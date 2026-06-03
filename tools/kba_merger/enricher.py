"""
Enrichment delle righe merged con dati dal catalogo KBA locale.

Per ogni KBA Number cerca il record corrispondente in:
  lib/data/kba_catalog/records/<slug>.md

Legge il frontmatter YAML e popola le colonne di risk enrichment.
Se il record non esiste, le colonne restano vuote senza errore.

Per la colonna Suggested Note viene usata una logica ibrida:
- Fast path Python deterministico per i casi chiari (tag gia' presenti,
  keyword DEFER/WIP inequivocabili, raccomandazione catalogo nota).
- Fallback AI per i casi ambigui (KBA non in catalogo, raccomandazione
  non standard, nota recente senza keyword riconoscibili).
"""

from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any

import yaml
from loguru import logger

from tools.kba_merger.config import DOCUMENTS_DIR, INDEX_FILE, RECORDS_DIR
from tools.kba_reporter.config import (
    DELTAV_VERSIONS,
    VERSION_PATTERNS,
    RI_PATTERNS,
    UNIVERSAL_PATTERNS,
)
from tools.kba_reporter.patch_builder import (
    _extract_files_from_doc,
    _is_compatible,
    _deduplicate_files,
)

# Pattern per estrarre ID KBA da fix_reference
_KBA_REF_RE = re.compile(r"\b([A-Z]{2}-\d{4}-\d{4})\b")

# Pattern per estrarre blocco ```json ... ```
_JSON_BLOCK_RE = re.compile(r"```json\s*([\s\S]*?)\s*```", re.IGNORECASE)

# Path prontuario regole
_RULES_PATH: Path = RECORDS_DIR.parent.parent / "kba_prontuario" / "rules.md"

# Path prompt
_PROMPT_PATH: Path = DOCUMENTS_DIR.parent / "Prompts" / "kba" / "raccomandazione-azione.md"

# Marcatori che indicano nota già gestita — non suggerire nulla
_HANDLED_TAGS = ("{DONE}", "{DEFER}", "{WIP}", "{NA}", "{FLAG}", "{ACK}")

# Parole chiave in testo libero che implicano DEFER
_DEFER_TEXT = [
    "NEXT STOP",
    "NEXT SHUTDOWN",
    "PLANNED MAINTENANCE",
    "NEXT SERVICE INTERVAL",
    "PATCH DA INSTALLARE",
    "WILL BE APPLIED",
    "TO NEXT STOP",
    "NEXT PLANT STOP",
    "PRODUCTION SHUTDOWN",
    "PATCHING STAGE",
    "TO BE INSTALLED",
    "NEXT PLANNED",
    "PROSSIMA FERMATA",
    "FERMATA",
    "PROSSIMO FERMO",
]

# Parole chiave in testo libero che implicano WIP
_WIP_TEXT = [
    "TO CHECK",
    "TO EVALUATE",
    "VALUTARE",
    "TO BE ANALYZED",
    "ANALYSIS TO BE",
    "UNDER INVESTIGATION",
    "TO BE CHECKED",
    "VERIFICARE",
    "TO BE SCHEDULED",
    "TO BE DISCUSSED",
    "DA ANALIZZARE",
    "DA VERIFICARE",
]

# Valori raccomandazione che il fast-path Python sa gestire
_KNOWN_RECOS = frozenset(
    {
        "applicare_patch",
        "applicare_fix",
        "applicare_workaround",
        "nessuna_azione",
        "monitorare",
        "installare_patch",
    }
)


def _load_catalog_ids() -> set[str]:
    """
    Carica l'insieme degli ID presenti in index.yaml (confronto case-insensitive).

    Returns:
        Set di slug lowercase degli ID nel catalogo.
    """
    if not INDEX_FILE.exists():
        logger.warning(f"index.yaml non trovato: {INDEX_FILE}")
        return set()

    try:
        data: dict[str, Any] = yaml.safe_load(INDEX_FILE.read_text(encoding="utf-8")) or {}
    except yaml.YAMLError as exc:
        logger.error(f"Errore lettura index.yaml: {exc}")
        return set()

    entries: list[dict[str, Any]] = data.get("entries", [])
    return {str(e.get("id", "")).lower() for e in entries if e.get("id")}


def _parse_frontmatter(record_path: Path) -> dict[str, Any] | None:
    """
    Legge il frontmatter YAML da un file record MD.

    Args:
        record_path: Path al file .md del record KBA.

    Returns:
        Dizionario frontmatter, o None se non parsabile.
    """
    try:
        content = record_path.read_text(encoding="utf-8")
    except OSError as exc:
        logger.warning(f"Impossibile leggere {record_path.name}: {exc}")
        return None

    fm_match = re.match(r"\A---\s*\n([\s\S]*?)\n---\s*\n", content, re.MULTILINE)
    if not fm_match:
        logger.warning(f"Frontmatter mancante: {record_path.name}")
        return None

    try:
        fm = yaml.safe_load(fm_match.group(1))
    except yaml.YAMLError as exc:
        logger.warning(f"YAML non valido in {record_path.name}: {exc}")
        return None

    return fm if isinstance(fm, dict) else None


def _build_workaround_cell(fm: dict[str, Any]) -> str:
    """
    Costruisce il valore della colonna Workaround dal frontmatter.

    Es: 'Si (medium)' o 'No'

    Args:
        fm: Frontmatter del record.

    Returns:
        Stringa formattata.
    """
    available = fm.get("workaround_available")
    if not available:
        return "No"
    avail_str = str(available).lower().strip()
    if avail_str in ("true", "yes", "si", "1"):
        complexity = str(fm.get("workaround_complexity") or "").strip()
        if complexity:
            return f"Si ({complexity})"
        return "Si"
    return "No"


def _extract_raccomandazione(content: str) -> str:
    """Estrae il testo della sezione ## Raccomandazione dal body del record MD."""
    parts = content.split("---", 2)
    body = parts[2] if len(parts) >= 3 else content
    m = re.search(r"^## Raccomandazione\s*\n(.+?)(?=^## |\Z)", body, re.MULTILINE | re.DOTALL)
    if m:
        return m.group(1).strip()
    return ""


def _extract_recent_note_text(user_notes: str) -> str:
    """
    Estrae il testo della nota più recente (prima riga [Autore, data]: testo).
    Se non trova il pattern ritorna la prima riga non vuota.
    """
    if not user_notes:
        return ""
    for line in user_notes.strip().split("\n"):
        m = re.match(r"\[.*?,\s*\d+.*?\]:\s*(.*)", line.strip())
        if m:
            return m.group(1).strip()
    return user_notes.strip().split("\n")[0].strip()


def _lookup_css_files(fix_reference: str, site: str) -> list[str]:
    """
    Dato un valore fix_reference e un sito, restituisce la lista dei file CSS
    compatibili estratti dal documento della KBA di riferimento.

    Args:
        fix_reference: Stringa fix_reference dal frontmatter.
        site: Nome sito (es. "Lonigo", "Montecchio", "Termoli").

    Returns:
        Lista ordinata di nomi file CSS compatibili (senza .zip).
    """
    if not fix_reference:
        return []

    m = _KBA_REF_RE.search(fix_reference)
    if not m:
        return []

    ref_slug = m.group(1).lower()
    version = DELTAV_VERSIONS.get(site, "")
    if not version:
        return []

    raw_files = _extract_files_from_doc(ref_slug)
    if not raw_files:
        return []

    # Esclude KB Microsoft (utili al reporter ma non alla colonna Suggested Notes)
    _KB_RE = re.compile(r"^KB\d{6,}$", re.IGNORECASE)
    css_files = {f for f in raw_files if not _KB_RE.match(f)}

    compatible = _deduplicate_files({f for f in css_files if _is_compatible(f, version)})

    result = sorted(f.replace(".zip", "") for f in compatible)
    logger.debug(f"CSS lookup {fix_reference} @ {site}: {result}")
    return result


def _build_suggested_note_python(
    user_notes: str,
    in_catalog: bool,
    raccomandazione: str,
    fix_reference: str = "",
    site: str = "",
    fix_versions: list[str] | None = None,
) -> str:
    """
    Fast path deterministico per la colonna Suggested Note.

    Copre i casi con segnali chiari; ritorna None per i casi ambigui
    che devono passare all'AI.

    Priorità:
    1. Nota più recente ha già un {TAG} corretto → "" (non toccare)
    2. Nota più recente ha tag malformato → "" (già gestita)
    3. Testo libero → DEFER inequivocabile
    4. Testo libero → WIP inequivocabile
    5. Nota recente con contenuto ma storico ha {TAG} → ""
    6. Fallback da catalogo con raccomandazione nota
    7. Ritorna None se il caso è ambiguo (passa all'AI)

    Args:
        user_notes: Testo note utente.
        in_catalog: True se la KBA è nel catalogo.
        raccomandazione: Testo raccomandazione dal record MD.
        fix_reference: Riferimento fix dal frontmatter.
        site: Nome sito per lookup versione DeltaV.
        fix_versions: Lista versioni DeltaV per cui il fix è disponibile (dal record).
                      Lista vuota = universale o non specificato.

    Returns:
        Stringa suggerimento, "" per "non toccare", o None per "caso ambiguo → AI".
    """
    # Verifica anticipata: fix_reference esiste ma non per la versione di questo sito
    if fix_reference and fix_versions:
        site_version = DELTAV_VERSIONS.get(site, "")
        if site_version and site_version not in fix_versions:
            versions_str = ", ".join(fix_versions)
            return f"{{DEFER}} No fix available for {site_version} — solution available for {versions_str} only. Monitor for updates."

    recent = _extract_recent_note_text(user_notes)
    recent_upper = recent.upper()

    # 1. Testo libero nella nota più recente → DEFER inequivocabile
    if recent and any(k in recent_upper for k in _DEFER_TEXT):
        css = _lookup_css_files(fix_reference, site)
        if css:
            return "{DEFER} Scheduled for next service interval. Install: " + ", ".join(css)
        return "{DEFER} Scheduled for next service interval."

    # 2. Testo libero nella nota più recente → WIP inequivocabile
    if recent and any(k in recent_upper for k in _WIP_TEXT):
        return "{WIP} Under investigation."

    # 3. Nota recente con testo generico → caso ambiguo (AI decide)
    if recent:
        return None  # type: ignore[return-value]

    # 4. Fallback da catalogo con raccomandazione nota
    if in_catalog:
        reco = raccomandazione.lower().strip()
        if reco in ("applicare_patch", "applicare_fix", "installare_patch"):
            css = _lookup_css_files(fix_reference, site)
            if css:
                return "{DEFER} Scheduled for next service interval. Install: " + ", ".join(css)
            return "{DEFER} Scheduled for next service interval."
        if reco == "applicare_workaround":
            return "{WIP} To be discussed with FIS at next review."
        if reco in ("nessuna_azione", "monitorare"):
            return "{NA} No solution available from vendor — monitoring only."
        if reco:
            # Raccomandazione presente ma non standard → caso ambiguo
            return None  # type: ignore[return-value]

    # 5. KBA non in catalogo o raccomandazione assente → caso ambiguo
    return None  # type: ignore[return-value]


def _load_prompt_template() -> str:
    """
    Carica il template del prompt dalla sezione ## Prompt del file MD.

    Returns:
        Testo della sezione ## Prompt.

    Raises:
        FileNotFoundError: Se il file prompt non esiste.
        ValueError: Se la sezione ## Prompt non è trovata.
    """
    if not _PROMPT_PATH.exists():
        raise FileNotFoundError(f"Prompt template non trovato: {_PROMPT_PATH}")
    content = _PROMPT_PATH.read_text(encoding="utf-8")
    match = re.search(r"^## Prompt\s*\n([\s\S]*?)(?=\n## |\Z)", content, re.MULTILINE)
    if not match:
        raise ValueError(f"Sezione '## Prompt' non trovata in: {_PROMPT_PATH}")
    return match.group(1).strip()


def _load_rules_context() -> str:
    """
    Carica il testo delle regole prontuario da rules.md se esiste.

    Returns:
        Contenuto del file rules.md, oppure stringa vuota.
    """
    if not _RULES_PATH.exists():
        return ""
    try:
        return _RULES_PATH.read_text(encoding="utf-8")
    except OSError as exc:
        logger.warning(f"Impossibile leggere rules.md: {exc}")
        return ""


def _load_kba_body(slug: str) -> str:
    """
    Carica il contenuto del documento MD associato a una KBA.

    Args:
        slug: ID KBA lowercase (es. "nk-2400-0150").

    Returns:
        Contenuto del documento, o stringa vuota se non trovato.
    """
    doc_path = DOCUMENTS_DIR / f"{slug}.md"
    if doc_path.exists():
        try:
            return doc_path.read_text(encoding="utf-8")
        except OSError as exc:
            logger.warning(f"Impossibile leggere documento {slug}.md: {exc}")
    return ""


def _load_referenced_bodies(fix_reference: str) -> dict[str, str]:
    """
    Carica i body MD delle KBA referenziate nel fix_reference.

    Args:
        fix_reference: Valore fix_reference dal frontmatter.

    Returns:
        Dizionario {kba_id: contenuto_md}.
    """
    result: dict[str, str] = {}
    if not fix_reference:
        return result
    for m in _KBA_REF_RE.finditer(fix_reference):
        ref_id = m.group(1)
        body = _load_kba_body(ref_id.lower())
        if body:
            result[ref_id] = body
    return result


def _build_suggested_note_ai(
    kba_number: str,
    title: str,
    risk_level: str,
    workaround: str,
    fix_available: str,
    user_notes: str,
    site: str,
    deltav_version: str,
    kba_body: str,
    referenced_bodies: dict[str, str],
    provider: Any,
    model: str | None,
    prompt_template: str,
    rules_context: str,
) -> tuple[str, Any]:
    """
    Chiama l'AI per suggerire il tag per la colonna Suggested Note.

    Returns:
        Tupla (suggerimento, response) — response è None in caso di errore.
    """
    kba_metadata = (
        f"KBA ID: {kba_number}\n"
        f"Titolo: {title}\n"
        f"Risk Level: {risk_level}\n"
        f"Workaround: {workaround}\n"
        f"Fix Available: {fix_available}\n"
        f"Sito: {site}\n"
        f"Versione DeltaV: {deltav_version}\n"
        f"Note storiche:\n{user_notes if user_notes else '(nessuna nota)'}"
    )

    if referenced_bodies:
        parts = []
        for ref_id, body in referenced_bodies.items():
            parts.append(f"=== {ref_id} ===\n{body[:3000]}")
        referenced_bodies_text = "\n\n".join(parts)
    else:
        referenced_bodies_text = "(nessun documento correlato disponibile)"

    prompt = prompt_template.replace("{{kba_metadata}}", kba_metadata)
    prompt = prompt.replace(
        "{{kba_body}}", kba_body[:4000] if kba_body else "(documento non disponibile)"
    )
    prompt = prompt.replace("{{referenced_bodies}}", referenced_bodies_text)
    prompt = prompt.replace("{{rules_context}}", rules_context if rules_context else "")

    try:
        response = provider.chat(prompt=prompt, model=model)
        raw_text: str = response.text
    except Exception as exc:
        logger.warning(f"Errore chiamata AI per {kba_number}: {exc}")
        return "", None

    # Parsing JSON risposta
    json_block = _JSON_BLOCK_RE.search(raw_text)
    raw = json_block.group(1).strip() if json_block else raw_text.strip()

    try:
        data = json.loads(raw)
    except json.JSONDecodeError:
        try:
            decoder = json.JSONDecoder()
            data, _ = decoder.raw_decode(raw.lstrip())
        except (json.JSONDecodeError, ValueError) as exc:
            logger.warning(f"Parsing JSON AI fallito per {kba_number}: {exc} | raw={raw[:200]!r}")
            return "", response

    if not isinstance(data, dict):
        logger.warning(f"Risposta AI non è un dict per {kba_number}: {type(data)}")
        return "", response

    tag = str(data.get("tag") or "").strip().upper()
    note = str(data.get("note") or "").strip()

    valid_tags = {"DEFER", "WIP", "NA"}
    if tag not in valid_tags:
        logger.warning(f"Tag AI non valido per {kba_number}: {tag!r}")
        return "", response

    result = f"{{{tag}}} {note}" if note else f"{{{tag}}}"
    logger.debug(f"AI suggestion per {kba_number}: {result!r}")
    return result, response


def _build_fix_cell(fm: dict[str, Any]) -> str:
    """
    Costruisce il valore della colonna Fix Available dal frontmatter.

    Es: 'Si -> NK-2400-0160' o 'No'

    Args:
        fm: Frontmatter del record.

    Returns:
        Stringa formattata.
    """
    available = fm.get("fix_available")
    if not available:
        return "No"
    avail_str = str(available).lower().strip()
    if avail_str in ("true", "yes", "si", "1"):
        reference = str(fm.get("fix_reference") or "").strip()
        if reference:
            return f"Si -> {reference}"
        return "Si"
    return "No"


def enrich_rows(
    rows: list[dict[str, Any]],
    use_ai: bool = True,
    provider_name: str = "grok",
    model: str | None = "grok-4-1-fast-reasoning",
    on_progress: Any | None = None,
) -> tuple[list[dict[str, Any]], int, int]:
    """
    Arricchisce le righe merged con i dati del catalogo KBA.

    Per ogni riga:
    - Carica dati risk dal catalogo (fast path deterministico sempre attivo).
    - Per Suggested Note usa logica ibrida:
      * Fast path Python per i casi chiari.
      * Chiamata AI (se use_ai=True) per i casi ambigui.

    Args:
        rows: Lista di dizionari merged (output di merger.merge_rows).
        use_ai: Se True, chiama l'AI per i casi ambigui.
        provider_name: Nome provider LLM (default "grok").
        model: Override modello LLM (None = default del provider).

    Returns:
        Tupla (rows_enriched, in_catalog_count, total_unique_kbas).
    """
    catalog_ids = _load_catalog_ids()

    # Setup AI se richiesto
    provider_instance: Any = None
    prompt_template: str = ""
    rules_context: str = ""

    if use_ai:
        try:
            from tools.consulto.config import get_api_key
            from tools.consulto.providers import PROVIDERS

            api_key = get_api_key(provider_name)
            provider_cls = PROVIDERS.get(provider_name)
            if provider_cls is None:
                logger.warning(
                    f"Provider AI '{provider_name}' non trovato — disabilito AI enrichment"
                )
                use_ai = False
            else:
                provider_instance = provider_cls(api_key)
                prompt_template = _load_prompt_template()
                rules_context = _load_rules_context()
                logger.debug(f"AI enrichment attivo: provider={provider_name}, model={model}")
        except (FileNotFoundError, ValueError) as exc:
            logger.warning(f"Impossibile caricare prompt AI: {exc} — disabilito AI enrichment")
            use_ai = False
        except SystemExit:
            logger.warning("API key AI non disponibile — disabilito AI enrichment")
            use_ai = False

    found_in_catalog: set[str] = set()
    total_unique = len({r["KBA Number"] for r in rows})
    total_rows = len(rows)
    enriched: list[dict[str, Any]] = []
    _cnt_python_filled = 0
    _cnt_ai = 0
    _cnt_fallback = 0

    for _row_idx, row in enumerate(rows, 1):
        kba_number = str(row.get("KBA Number") or "").strip()
        slug = kba_number.lower()

        risk_score: Any = ""
        risk_level: str = ""
        problem_type: str = ""
        workaround: str = ""
        fix_available: str = ""
        emerson_category: str = ""
        raccomandazione: str = ""
        fix_ref_str: str = ""
        fix_versions_list: list[str] = []
        in_catalog: bool = False
        fm: dict[str, Any] | None = None

        if slug in catalog_ids:
            record_path = RECORDS_DIR / f"{slug}.md"
            try:
                content = record_path.read_text(encoding="utf-8")
            except OSError as exc:
                logger.warning(f"Impossibile leggere {record_path.name}: {exc}")
                content = ""

            if content:
                fm = _parse_frontmatter(record_path)
                if fm is not None:
                    in_catalog = True
                    found_in_catalog.add(slug)
                    raw_score = fm.get("risk_score")
                    risk_score = float(raw_score) if raw_score is not None else ""
                    risk_level = str(fm.get("risk_level") or "").strip()
                    problem_type = str(fm.get("problem_type") or "").strip()
                    workaround = _build_workaround_cell(fm)
                    fix_available = _build_fix_cell(fm)
                    emerson_category = str(fm.get("emerson_category") or "").strip()
                    raccomandazione = _extract_raccomandazione(content)
                    fix_ref_str = str(fm.get("fix_reference") or "").strip()
                    fix_versions_list: list[str] = [
                        str(v) for v in (fm.get("fix_versions") or []) if v
                    ]
                    logger.debug(
                        f"Enriched {kba_number}: {risk_level} ({risk_score}), reco={raccomandazione!r}"
                    )
                else:
                    logger.warning(f"Record presente in indice ma non leggibile: {kba_number}")
        else:
            logger.debug(f"KBA non in catalogo (normale): {kba_number}")

        user_notes = str(row.get("User Notes") or "")
        site_str = str(row.get("Site") or "").split(" - ")[0].strip()

        # Logica ibrida per Suggested Note
        suggested_note: str = ""

        # Fast path Python
        python_result = _build_suggested_note_python(
            user_notes,
            in_catalog,
            raccomandazione,
            fix_reference=fix_ref_str,
            site=site_str,
            fix_versions=fix_versions_list,
        )

        if python_result is not None:
            suggested_note = python_result
            _cnt_python_filled += 1
            logger.debug(f"{kba_number}: python → {python_result[:60]!r}")
            if on_progress:
                on_progress(_row_idx, total_rows, kba_number, "python", None, None)
        elif use_ai and provider_instance is not None:
            _cnt_ai += 1
            deltav_version = DELTAV_VERSIONS.get(site_str, "")
            kba_body = _load_kba_body(slug)
            referenced_bodies = _load_referenced_bodies(fix_ref_str)

            # Chiamata AI con live timer
            import threading as _threading
            import time as _time
            from rich.console import Console as _RichConsole
            from rich.live import Live as _Live

            _suggestion_box: list = [None]
            _response_box: list = [None]
            _exc_box: list = [None]

            def _ai_enrich():
                try:
                    s, r = _build_suggested_note_ai(
                        kba_number=kba_number,
                        title=str(row.get("Title") or "").strip(),
                        risk_level=risk_level,
                        workaround=workaround,
                        fix_available=fix_available,
                        user_notes=user_notes,
                        site=site_str,
                        deltav_version=deltav_version,
                        kba_body=kba_body,
                        referenced_bodies=referenced_bodies,
                        provider=provider_instance,
                        model=model,
                        prompt_template=prompt_template,
                        rules_context=rules_context,
                    )
                    _suggestion_box[0] = s
                    _response_box[0] = r
                except Exception as e:
                    _exc_box[0] = e

            _t = _threading.Thread(target=_ai_enrich, daemon=True)
            _t0 = _time.monotonic()
            _t.start()

            _con = _RichConsole(highlight=False, stderr=False)
            with _Live(console=_con, refresh_per_second=4, transient=True) as _live:
                while _t.is_alive():
                    _elapsed = _time.monotonic() - _t0
                    _live.update(
                        f"      [[dim]{_row_idx}/{total_rows}[/dim]] "
                        f"[cyan]{kba_number}[/cyan]  [dim]⏳ {_elapsed:.1f}s...[/dim]"
                    )
                    _time.sleep(0.1)
            _t.join()

            if _exc_box[0]:
                logger.warning(f"Errore AI per {kba_number}: {_exc_box[0]}")
                suggested_note = ""
                if on_progress:
                    on_progress(
                        _row_idx, total_rows, kba_number, "ai_error", None, str(_exc_box[0])
                    )
            else:
                suggested_note = _suggestion_box[0] or ""
                ai_response = _response_box[0]
                logger.debug(f"{kba_number}: AI → {suggested_note[:60]!r}")
                if on_progress:
                    on_progress(_row_idx, total_rows, kba_number, "ai", ai_response, None)
        else:
            _cnt_fallback += 1
            suggested_note = "{WIP} Under investigation."
            logger.debug(f"{kba_number}: fallback (use_ai=False, caso ambiguo)")
            if on_progress:
                on_progress(_row_idx, total_rows, kba_number, "fallback", None, None)

        enriched.append(
            {
                **row,
                "Risk Score": risk_score,
                "Risk Level": risk_level,
                "Problem Type": problem_type,
                "Workaround": workaround,
                "Fix Available": fix_available,
                "Emerson Category": emerson_category,
                "FIS Notes": "",
                "Suggested Notes": suggested_note,
            }
        )

    logger.info(
        f"Suggested Notes — python:{_cnt_python_filled}, AI:{_cnt_ai}, fallback:{_cnt_fallback}"
    )
    return enriched, len(found_in_catalog), total_unique
