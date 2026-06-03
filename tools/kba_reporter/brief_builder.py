"""Costruisce il brief WIP con stato analisi per ogni KBA."""

from pathlib import Path
from datetime import date, timedelta

import yaml
from loguru import logger

from tools.kba_reporter.config import CATALOG_DIR, ANALYSIS_MAX_AGE_DAYS


def _kba_to_slug(kba_number: str) -> str:
    return kba_number.strip().lower().replace(" ", "-")


def _extract_section(body: str, section: str) -> str:
    """Estrae il testo di una sezione ## dal body Markdown. Ritorna stringa vuota se assente."""
    import re

    pattern = rf"^## {re.escape(section)}\s*\n(.*?)(?=^## |\Z)"
    m = re.search(pattern, body, re.MULTILINE | re.DOTALL)
    if m:
        return m.group(1).strip()
    return ""


def _read_catalog_meta(slug: str) -> dict:
    path = CATALOG_DIR / f"{slug}.md"
    if not path.exists():
        return {"found": False}
    text = path.read_text(encoding="utf-8")
    # Estrai frontmatter YAML
    if text.startswith("---"):
        parts = text.split("---", 2)
        if len(parts) >= 3:
            try:
                meta = yaml.safe_load(parts[1]) or {}
                body = parts[2]
                return {
                    "found": True,
                    "analyzed_at": str(meta.get("analyzed_at", "")),
                    "source": str(meta.get("source", "")),
                    "risk_score": meta.get("risk_score", ""),
                    "risk_level": str(meta.get("risk_level", "")),
                    "workaround": bool(meta.get("workaround_available", False)),
                    "fix_reference": str(meta.get("fix_reference", "")),
                    "sintesi": _extract_section(body, "Sintesi"),
                    "workaround_text": _extract_section(body, "Workaround"),
                    "raccomandazione": _extract_section(body, "Raccomandazione"),
                    "note": _extract_section(body, "Note"),
                }
            except Exception:
                pass
    return {"found": True, "analyzed_at": "", "source": ""}


def build_wip_brief(wip_rows: list[dict], max_age_days: int = ANALYSIS_MAX_AGE_DAYS) -> list[dict]:
    """
    Deduplica le righe WIP per KBA Number, verifica lo stato nel catalogo
    e restituisce una lista ordinata con stato ANALIZZA / MANCANTE / SKIP.
    """
    cutoff = date.today() - timedelta(days=max_age_days)

    # Deduplica per KBA Number, aggrega siti
    seen: dict[str, dict] = {}
    for row in wip_rows:
        kba = row["kba_number"]
        if kba not in seen:
            seen[kba] = {**row, "sites": set()}
        seen[kba]["sites"].add(row["site"].split(" - ")[0].strip())

    result = []
    for kba, data in seen.items():
        slug = _kba_to_slug(kba)
        meta = _read_catalog_meta(slug)

        if not meta["found"]:
            stato = "MANCANTE"
        else:
            analyzed_at = meta["analyzed_at"]
            try:
                analysis_date = date.fromisoformat(analyzed_at)
                stato = "SKIP" if analysis_date >= cutoff else "ANALIZZA"
            except Exception:
                stato = "ANALIZZA"

        result.append(
            {
                "kba_number": kba,
                "title": data["title"],
                "sites": sorted(data["sites"]),
                "risk_level": meta.get("risk_level") or data["risk_level"],
                "risk_score": meta.get("risk_score", ""),
                "stato": stato,
                "analyzed_at": meta.get("analyzed_at", ""),
                "source": meta.get("source", ""),
                "sintesi": meta.get("sintesi", ""),
                "workaround_text": meta.get("workaround_text", ""),
                "raccomandazione": meta.get("raccomandazione", ""),
                "note": meta.get("note", ""),
                "fix_reference": meta.get("fix_reference", ""),
            }
        )

    result.sort(key=lambda x: (x["stato"] == "SKIP", x["kba_number"]))
    logger.info(
        f"Brief WIP: {len(result)} KBA, "
        f"{sum(1 for r in result if r['stato'] != 'SKIP')} da analizzare"
    )
    return result
