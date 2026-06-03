"""
Logica di risoluzione dipendenze documentali KBA.

Naviga ricorsivamente i fix_reference di ogni KBA fornita in input
e produce una mappa delle dipendenze con stato di presenza in lib/documents/.
"""

from __future__ import annotations

import re
from collections import deque

import yaml
from loguru import logger

from tools.kba_resolver.config import DOCUMENTS_DIR, RECORDS_DIR

# Pattern per estrarre ID KBA da stringhe libere (es. fix_reference)
_KBA_ID_RE = re.compile(r"\b([A-Z]{2}-\d{4}-\d{4})\b")


def _get_status(slug: str) -> str:
    """
    Determina lo stato di presenza di una KBA in lib/documents/.

    Args:
        slug: Identificatore KBA in lowercase (es. 'nk-1000-0109').

    Returns:
        'present' se il documento MD esiste, 'missing' altrimenti.
    """
    doc_path = DOCUMENTS_DIR / f"{slug}.md"
    return "present" if doc_path.exists() else "missing"


def _read_fix_references(slug: str) -> list[str]:
    """
    Legge il campo fix_reference dal frontmatter YAML del record catalogo.
    Estrae tutti gli ID KBA presenti nel valore (formato XX-NNNN-NNNN).

    Args:
        slug: Slug KBA in lowercase.

    Returns:
        Lista di ID KBA referenziati (uppercase, deduplicati, ordine preservato).
        Lista vuota se il record non esiste o fix_reference e' assente/vuoto.
    """
    record_path = RECORDS_DIR / f"{slug}.md"
    if not record_path.exists():
        logger.debug(f"Record non trovato in catalogo: {slug}")
        return []
    try:
        text = record_path.read_text(encoding="utf-8")
        if not text.startswith("---"):
            return []
        parts = text.split("---", 2)
        if len(parts) < 3:
            return []
        meta = yaml.safe_load(parts[1]) or {}
        fix_ref = str(meta.get("fix_reference") or "")
        refs = list(dict.fromkeys(m.upper() for m in _KBA_ID_RE.findall(fix_ref)))
        logger.debug(f"fix_reference {slug}: {refs}")
        return refs
    except Exception as exc:
        logger.warning(f"Errore lettura fix_reference per {slug}: {exc}")
        return []


def resolve_dependencies(
    kba_ids: list[str],
    max_depth: int = 3,
) -> dict:
    """
    Esegue una BFS sui fix_reference a partire dalle KBA fornite in input.

    Per ogni KBA input legge i fix_reference dal record catalogo e,
    ricorsivamente fino a max_depth livelli, costruisce la mappa delle
    dipendenze dirette di ogni nodo.

    Args:
        kba_ids: Lista di ID KBA uppercase (es. ['NK-2400-0150', ...]).
        max_depth: Profondita' massima di navigazione BFS (default 3).

    Returns:
        Dizionario con chiavi:
          - 'tree': dict {kba_id: list[str]} — dipendenze dirette di ogni nodo
                    (solo i nodi raggiunti durante la BFS, incluse le KBA input)
          - 'all_deps': set[str] — tutti gli slug referenziati (le dipendenze,
                        non le KBA input stesse)
          - 'present': set[str] — slug in all_deps presenti in lib/documents/
          - 'missing': set[str] — slug in all_deps assenti in lib/documents/
    """
    # tree mappa ogni nodo visitato alle proprie dipendenze dirette
    tree: dict[str, list[str]] = {}
    # all_deps raccoglie tutti gli slug referenziati (non le KBA input)
    all_deps: set[str] = set()

    # BFS: ogni elemento e' (kba_id_uppercase, depth)
    visited: set[str] = set(kba_ids)
    queue: deque[tuple[str, int]] = deque((kba, 0) for kba in kba_ids)

    while queue:
        current, depth = queue.popleft()
        slug = current.lower()
        refs = _read_fix_references(slug)
        # Rimuovi autoreferenze (KBA che punta a se stessa)
        refs = [r for r in refs if r != current]
        tree[current] = refs

        if depth >= max_depth:
            # Registriamo le dipendenze ma non espandiamo oltre
            for ref in refs:
                all_deps.add(ref.lower())
            continue

        for ref in refs:
            ref_slug = ref.lower()
            all_deps.add(ref_slug)
            if ref not in visited:
                visited.add(ref)
                queue.append((ref, depth + 1))

    # Rimuovi dalle all_deps le KBA input stesse (vogliamo solo le referenziate)
    input_slugs = {k.lower() for k in kba_ids}
    all_deps -= input_slugs

    present: set[str] = set()
    missing: set[str] = set()
    for slug in all_deps:
        if _get_status(slug) == "present":
            present.add(slug)
        else:
            missing.add(slug)

    return {
        "tree": tree,
        "all_deps": all_deps,
        "present": present,
        "missing": missing,
    }
