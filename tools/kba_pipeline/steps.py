"""
Funzioni step della pipeline KBA.

Ogni step e' una funzione autonoma che importa direttamente dai tool base.
Nessun subprocess: tutto via import Python.

Step 1 — Conversione PDF -> Markdown
Step 2 — Analisi AI dei documenti nuovi/aggiornati
Step 3 — Verifica dipendenze documentali
Step 4 — Merge + enrichment e produzione Excel finale
"""

from __future__ import annotations

from datetime import date
from pathlib import Path
from typing import Any

import openpyxl
from loguru import logger

from tools.kba_pipeline.config import (
    BATCH_DIR,
    DOCUMENTS_DIR,
    PROMPT_ANALYZE,
    PROJECT_ROOT,
    RECORDS_DIR,
)


# ---------------------------------------------------------------------------
# Utilita' interne
# ---------------------------------------------------------------------------


def _read_deltav_excel(path: Path) -> tuple[list[str], list[dict[str, Any]]]:
    """
    Legge il file Excel DeltaV e restituisce headers + righe come dizionari.

    Args:
        path: Path al file .xlsx di input.

    Returns:
        Tupla (headers, rows).

    Raises:
        ValueError: Se il file non ha un foglio attivo o e' vuoto.
        OSError: Se il file non e' leggibile.
    """
    wb = openpyxl.load_workbook(path, read_only=True, data_only=True)
    ws = wb.active
    if ws is None:
        raise ValueError(f"Nessun foglio attivo nel file: {path.name}")

    rows_iter = ws.iter_rows(values_only=True)

    try:
        raw_headers = next(rows_iter)
    except StopIteration:
        raise ValueError(f"File vuoto: {path.name}")

    headers = [str(h).strip() if h is not None else "" for h in raw_headers]

    rows: list[dict[str, Any]] = []
    for raw_row in rows_iter:
        if all(v is None or str(v).strip() == "" for v in raw_row):
            continue
        row_dict: dict[str, Any] = {}
        for col_idx, header in enumerate(headers):
            value = raw_row[col_idx] if col_idx < len(raw_row) else None
            row_dict[header] = value
        rows.append(row_dict)

    wb.close()
    return headers, rows


def _extract_frontmatter_date(text: str, field: str) -> str:
    """
    Estrae un campo data dal frontmatter YAML di un file Markdown.

    Cerca il pattern 'field: YYYY-MM-DD' nel frontmatter senza
    dipendere da yaml.safe_load (evita import pesante in funzione utilitaria).

    Args:
        text: Contenuto del file Markdown.
        field: Nome del campo da estrarre (es. 'converted_at', 'analyzed_at').

    Returns:
        Stringa data in formato ISO, o '' se non trovata.
    """
    import re

    pattern = re.compile(
        rf"^{re.escape(field)}:\s*(['\"]?)(\d{{4}}-\d{{2}}-\d{{2}})\1\s*$",
        re.MULTILINE,
    )
    match = pattern.search(text)
    if match:
        return match.group(2)
    return ""


# ---------------------------------------------------------------------------
# Step 1 — Conversione PDF
# ---------------------------------------------------------------------------


def step1_convert(inbox: Path, force: bool, dry_run: bool) -> dict[str, int]:
    """
    Converte i PDF presenti nella cartella inbox in Markdown.

    Importa direttamente da tools.pdf_converter senza subprocess.
    In dry_run conta i PDF candidati senza convertire.
    Mostra una barra di progresso Rich durante la conversione.

    Args:
        inbox: Cartella sorgente contenente i file PDF.
        force: Se True, riconverte PDF gia' presenti nel database.
        dry_run: Se True, conta senza eseguire.

    Returns:
        Dizionario {'converted': int, 'skipped': int, 'errors': int}.
    """
    from tools.pdf_converter.indexer import DocumentIndexer
    from tools.pdf_converter.converter import convert_pdf
    from tools.pdf_converter.post_processor import post_process
    from tools.pdf_converter.utils import slugify

    result: dict[str, int] = {"converted": 0, "skipped": 0, "errors": 0}

    if not inbox.exists():
        logger.warning(f"Cartella inbox non trovata: {inbox}")
        return result

    pdf_files = sorted(inbox.glob("*.pdf"))

    if not pdf_files:
        logger.info(f"Nessun PDF trovato in: {inbox}")
        return result

    indexer = DocumentIndexer()
    indexer.init_db()

    # Determina la lista da convertire
    if not force:
        to_convert = [p for p in pdf_files if not indexer.is_already_converted(slugify(p.stem))]
        result["skipped"] = len(pdf_files) - len(to_convert)
    else:
        to_convert = pdf_files

    logger.info(
        f"Step 1: {len(to_convert)} PDF da convertire, {result['skipped']} saltati"
        + (" (dry-run)" if dry_run else "")
    )

    if dry_run:
        result["converted"] = len(to_convert)
        return result

    from rich.console import Console
    from rich.progress import BarColumn, Progress, SpinnerColumn, TaskProgressColumn, TextColumn

    _console = Console(highlight=False)

    with Progress(
        SpinnerColumn(),
        TextColumn("[progress.description]{task.description}"),
        BarColumn(),
        TaskProgressColumn(),
        console=_console,
    ) as progress:
        task = progress.add_task("      Conversione...", total=len(to_convert))

        for pdf_path in to_convert:
            slug = slugify(pdf_path.stem)
            progress.update(task, description=f"      [cyan]{slug[:50]}[/cyan]")
            logger.debug(f"Conversione: {pdf_path.name}")

            try:
                conv_result = convert_pdf(pdf_path)
                if conv_result.success:
                    conv_result = post_process(conv_result)
                indexer.index_document(conv_result)

                if conv_result.success:
                    result["converted"] += 1
                    logger.info(f"Convertito: {pdf_path.name}")
                elif conv_result.status == "skipped":
                    result["skipped"] += 1
                else:
                    result["errors"] += 1
                    logger.error(f"Fallito: {pdf_path.name} — {conv_result.error_message}")
            except Exception as exc:
                result["errors"] += 1
                logger.error(f"Errore conversione '{pdf_path.name}': {exc}")

            progress.advance(task)

    return result


# ---------------------------------------------------------------------------
# Step 2 — Analisi AI
# ---------------------------------------------------------------------------


def step2_analyze(
    provider_name: str,
    model: str,
    dry_run: bool,
    on_progress: Any | None = None,
    force_analyze: bool = False,
) -> dict[str, int]:
    """
    Trova i documenti Markdown nuovi o aggiornati e li analizza con AI.

    Criteri di selezione (normale):
    - Nuovi: presenti in DOCUMENTS_DIR ma senza record corrispondente in RECORDS_DIR.
    - Aggiornati: record presente ma converted_at nel documento e' successivo
      ad analyzed_at nel record.

    Con force_analyze=True: ri-analizza tutti i documenti che hanno gia' un record
    (oltre ai nuovi senza record).

    Per ogni candidato (se non dry_run):
    1. Legge il contenuto del documento.
    2. Carica il prompt da PROMPT_ANALYZE e sostituisce {{kba_text}}.
    3. Chiama il provider AI e ottiene la risposta.
    4. Scrive il file batch in BATCH_DIR.
    5. Parsa il batch e scrive il record nel catalogo.

    Dopo tutti i candidati, chiama rebuild_index() una sola volta.

    Args:
        provider_name: Nome del provider LLM (es. 'grok').
        model: Identificatore del modello LLM.
        dry_run: Se True, conta candidati senza analizzare.
        force_analyze: Se True, ri-analizza tutti i record esistenti.

    Returns:
        Dizionario {'analyzed': int, 'skipped': int, 'errors': int, 'total_catalog': int}.
    """
    from tools.consulto.batch import extract_prompt_section
    from tools.consulto.config import get_api_key
    from tools.consulto.providers import PROVIDERS
    from tools.kba_indexer.parser import parse_batch_file
    from tools.kba_indexer.writer import rebuild_index, write_record

    result: dict[str, int] = {"analyzed": 0, "skipped": 0, "errors": 0, "total_catalog": 0}

    if not DOCUMENTS_DIR.exists():
        logger.warning(f"DOCUMENTS_DIR non trovata: {DOCUMENTS_DIR}")
        result["total_catalog"] = rebuild_index()
        return result

    # --- Trova candidati nuovi (nessun record) ---
    nuovi: list[Path] = [
        p for p in DOCUMENTS_DIR.glob("*.md") if not (RECORDS_DIR / p.name).exists()
    ]

    if force_analyze:
        # Ri-analizza solo i documenti il cui record è stato prodotto con un modello diverso
        aggiornati = []
        skipped_same_model = 0
        for p in DOCUMENTS_DIR.glob("*.md"):
            record_path = RECORDS_DIR / p.name
            if not record_path.exists():
                continue  # già nei nuovi
            try:
                rec_text = record_path.read_text(encoding="utf-8")
                import re as _re

                fm_match = _re.search(r"\A---\s*\n([\s\S]*?)\n---", rec_text)
                if fm_match:
                    import yaml as _yaml

                    fm = _yaml.safe_load(fm_match.group(1)) or {}
                    rec_model = str(fm.get("analyzed_by_model", "unknown"))
                else:
                    rec_model = "unknown"
            except Exception:
                rec_model = "unknown"

            if rec_model != model:
                aggiornati.append(p)
            else:
                skipped_same_model += 1

        logger.info(
            f"Step 2 (force-analyze): {len(nuovi)} nuovi, "
            f"{len(aggiornati)} da ri-analizzare (modello diverso), "
            f"{skipped_same_model} già con {model} (saltati)"
        )
    else:
        # --- Trova candidati aggiornati (converted_at > analyzed_at) ---
        aggiornati = []
        for p in DOCUMENTS_DIR.glob("*.md"):
            record_path = RECORDS_DIR / p.name
            if not record_path.exists():
                continue  # gia' nei nuovi o non e' un documento KBA
            try:
                doc_text = p.read_text(encoding="utf-8")
                rec_text = record_path.read_text(encoding="utf-8")
            except OSError as exc:
                logger.warning(f"Impossibile leggere {p.name} o il suo record: {exc}")
                continue

            converted_str = _extract_frontmatter_date(doc_text, "converted_at")
            analyzed_str = _extract_frontmatter_date(rec_text, "analyzed_at")

            if not converted_str or not analyzed_str:
                continue

            if converted_str > analyzed_str:  # confronto ISO lexicografico
                aggiornati.append(p)

        logger.info(
            f"Step 2: {len(nuovi)} nuovi, {len(aggiornati)} aggiornati"
            + (" (dry-run)" if dry_run else "")
        )

    candidati = nuovi + aggiornati

    result["skipped"] = len(list(DOCUMENTS_DIR.glob("*.md"))) - len(candidati)

    if dry_run:
        result["analyzed"] = len(candidati)
        result["total_catalog"] = len(list(RECORDS_DIR.glob("*.md"))) if RECORDS_DIR.exists() else 0
        return result

    if not candidati:
        result["total_catalog"] = rebuild_index()
        return result

    # --- Carica prompt ---
    if not PROMPT_ANALYZE.exists():
        logger.error(f"File prompt non trovato: {PROMPT_ANALYZE}")
        result["errors"] = len(candidati)
        result["total_catalog"] = rebuild_index()
        return result

    try:
        prompt_template_text = PROMPT_ANALYZE.read_text(encoding="utf-8")
        prompt_template = extract_prompt_section(prompt_template_text)
    except (OSError, ValueError) as exc:
        logger.error(f"Impossibile caricare prompt: {exc}")
        result["errors"] = len(candidati)
        result["total_catalog"] = rebuild_index()
        return result

    # --- Inizializza provider AI ---
    try:
        api_key = get_api_key(provider_name)
        provider_cls = PROVIDERS.get(provider_name)
        if provider_cls is None:
            raise ValueError(f"Provider '{provider_name}' non trovato in PROVIDERS")
        provider = provider_cls(api_key)
    except (KeyError, ValueError, SystemExit) as exc:
        logger.error(f"Impossibile inizializzare provider '{provider_name}': {exc}")
        result["errors"] = len(candidati)
        result["total_catalog"] = rebuild_index()
        return result

    BATCH_DIR.mkdir(parents=True, exist_ok=True)

    today = date.today().isoformat()

    # --- Processa ogni candidato ---
    for doc_path in candidati:
        slug = doc_path.stem
        logger.debug(f"Analisi: {slug}")

        try:
            doc_content = doc_path.read_text(encoding="utf-8")
        except OSError as exc:
            logger.warning(f"Impossibile leggere {doc_path.name}: {exc}")
            result["errors"] += 1
            continue

        # Sostituisce il placeholder nel prompt
        prompt = prompt_template.replace("{{kba_text}}", doc_content)

        i = candidati.index(doc_path) + 1
        total = len(candidati)

        # Chiamata AI con timer live
        if on_progress:
            on_progress(i, total, slug, "start", None, None)

        response = None
        ai_exc = None
        try:
            import threading as _threading
            import time as _time
            from rich.console import Console as _RichConsole
            from rich.live import Live as _Live

            _result_box: list = [None]
            _exc_box: list = [None]

            def _ai_call():
                try:
                    _result_box[0] = provider.chat(prompt=prompt, model=model)
                except Exception as e:
                    _exc_box[0] = e

            _t = _threading.Thread(target=_ai_call, daemon=True)
            _t0 = _time.monotonic()
            _t.start()

            _con = _RichConsole(highlight=False, stderr=False)
            with _Live(console=_con, refresh_per_second=4, transient=True) as _live:
                while _t.is_alive():
                    _elapsed = _time.monotonic() - _t0
                    _live.update(
                        f"      [[dim]{i}/{total}[/dim]] [cyan]{slug}[/cyan]  "
                        f"[dim]⏳ {_elapsed:.1f}s...[/dim]"
                    )
                    _time.sleep(0.1)

            _t.join()
            if _exc_box[0] is not None:
                raise _exc_box[0]
            response = _result_box[0]

        except Exception as exc:
            logger.warning(f"Errore AI per '{slug}': {exc} — saltato")
            result["errors"] += 1
            if on_progress:
                on_progress(i, total, slug, "error", None, str(exc))
            continue

        # Scrivi file batch
        batch_path = BATCH_DIR / f"{slug}.md"
        batch_content = (
            f"---\n"
            f"kba: {slug}\n"
            f"provider: {provider_name}\n"
            f"model: {model}\n"
            f"analyzed_at: {today}\n"
            f"---\n\n"
            f"{response.text}\n"
        )

        try:
            batch_path.write_text(batch_content, encoding="utf-8")
        except OSError as exc:
            logger.warning(f"Impossibile scrivere batch '{batch_path.name}': {exc} — saltato")
            result["errors"] += 1
            if on_progress:
                on_progress(i, total, slug, "error", None, str(exc))
            continue

        # Parsa e scrive record
        try:
            record = parse_batch_file(batch_path)
            write_record(record)
            result["analyzed"] += 1
            logger.info(f"Record scritto per: {slug}")
            if on_progress:
                on_progress(i, total, slug, "ok", response, None)
        except Exception as exc:
            logger.warning(f"Errore parsing/scrittura record per '{slug}': {exc} — saltato")
            result["errors"] += 1
            if on_progress:
                on_progress(i, total, slug, "error", None, str(exc))

    # Ricostruisce l'indice una sola volta alla fine
    result["total_catalog"] = rebuild_index()
    return result


# ---------------------------------------------------------------------------
# Step 3 — Verifica dipendenze
# ---------------------------------------------------------------------------


def step3_resolve(excel_path: Path) -> dict[str, Any]:
    """
    Legge le KBA dal file Excel DeltaV e verifica le dipendenze documentali.

    Naviga i fix_reference tramite kba_resolver e restituisce lo stato
    complessivo delle dipendenze.

    Args:
        excel_path: Path al file .xlsx di input DeltaV.

    Returns:
        Dizionario {'ok': bool, 'missing': list[str], 'present': list[str]}.

    Raises:
        ValueError: Se il file Excel non e' leggibile o non contiene KBA.
        OSError: Se il file non e' accessibile.
    """
    from tools.kba_resolver.resolver import resolve_dependencies

    _, rows = _read_deltav_excel(excel_path)

    # Estrae KBA Number unici, ordine preservato
    kba_ids: list[str] = []
    seen: set[str] = set()
    for row in rows:
        kba = str(row.get("KBA Number") or "").strip().upper()
        if kba and kba not in seen:
            seen.add(kba)
            kba_ids.append(kba)

    if not kba_ids:
        logger.warning("Nessuna KBA trovata nel file Excel")
        return {"ok": True, "missing": [], "present": []}

    dep_result = resolve_dependencies(kba_ids)

    missing_list = sorted(dep_result["missing"])
    present_list = sorted(dep_result["present"])

    ok = len(missing_list) == 0

    logger.info(
        f"Step 3: {len(kba_ids)} KBA, "
        f"{len(present_list)} dipendenze presenti, "
        f"{len(missing_list)} mancanti"
    )

    return {
        "ok": ok,
        "missing": missing_list,
        "present": present_list,
    }


# ---------------------------------------------------------------------------
# Step 4 — Merge + Enrichment
# ---------------------------------------------------------------------------


def step4_merge(
    excel_path: Path,
    use_ai: bool,
    provider_name: str,
    model: str,
    dry_run: bool,
    on_progress: Any | None = None,
) -> dict[str, Any]:
    """
    Esegue il merge delle righe DeltaV, l'enrichment con i dati del catalogo
    KBA e produce il file Excel finale.

    Args:
        excel_path: Path al file .xlsx di input DeltaV.
        use_ai: Se True, usa l'AI per l'enrichment dei casi ambigui.
        provider_name: Nome del provider LLM.
        model: Identificatore del modello LLM.
        dry_run: Se True, esegue merge senza scrivere il file di output.

    Returns:
        Dizionario {'input_rows': int, 'merged_rows': int, 'output_path': str}.

    Raises:
        ValueError: Se il file Excel non e' valido.
        OSError: Se il file non e' accessibile.
    """
    from tools.kba_merger.merger import merge_rows
    from tools.kba_merger.enricher import enrich_rows
    from tools.kba_merger.writer import write_merge_excel

    headers, rows = _read_deltav_excel(excel_path)

    input_rows = len(rows)
    logger.info(f"Step 4: {input_rows} righe di input lette da {excel_path.name}")

    merged = merge_rows(rows, headers)
    logger.info(f"Step 4: merge completato, {len(merged)} righe risultanti")

    if dry_run:
        return {
            "input_rows": input_rows,
            "merged_rows": len(merged),
            "output_path": "(dry-run, nessun file scritto)",
        }

    enriched, in_catalog, total_unique = enrich_rows(
        merged,
        use_ai=use_ai,
        provider_name=provider_name,
        model=model,
        on_progress=on_progress,
    )
    logger.info(
        f"Step 4: enrichment completato — {in_catalog}/{total_unique} KBA uniche in catalogo"
    )

    output_path = write_merge_excel(enriched)
    logger.info(f"Step 4: Excel scritto in {output_path}")

    return {
        "input_rows": input_rows,
        "merged_rows": len(merged),
        "in_catalog": in_catalog,
        "total_unique": total_unique,
        "output_path": str(output_path),
    }
