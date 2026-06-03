"""Costruisce la lista patch per fermata a partire dalle righe DEFER."""

import re
from pathlib import Path
from collections import defaultdict

from loguru import logger

from tools.kba_reporter.config import (
    DOCUMENTS_DIR,
    DELTAV_VERSIONS,
    VERSION_PATTERNS,
    RI_PATTERNS,
    UNIVERSAL_PATTERNS,
    NODE_TYPES,
)

# Regex per estrarre nomi file installabili dal testo Markdown
FILE_REGEX = re.compile(
    r"\b("
    r"DeltaV_[\w.]+(?:_CSS|\.zip)?"
    r"|v1[45][A-Za-z0-9]+_64bit_\w+\.zip"
    r"|HyperV\w+\.zip"
    r"|Intel_\w+\.zip"
    r"|DVS\w+"
    r"|Dell\s+OpenManage\s+\S+\s+\d+"
    r"|KB\d{6,}"
    r")\b",
    re.IGNORECASE,
)


def _kba_to_slug(kba_number: str) -> str:
    return kba_number.strip().lower().replace(" ", "-")


def _classify_node(node: str) -> str:
    nu = node.upper()
    for ntype, prefixes in NODE_TYPES.items():
        if any(nu.startswith(p) or p in nu for p in prefixes):
            return ntype
    return "workstation"  # default


def _is_compatible(filename: str, version: str) -> bool:
    """True se il file è compatibile con la versione DeltaV del sito."""
    patterns = VERSION_PATTERNS.get(version, [])
    # Release-independent: sempre ok
    if any(p in filename for p in RI_PATTERNS):
        return True
    # Universal (HyperV, Dell, Intel, DVS): sempre ok
    if any(p.lower() in filename.lower() for p in UNIVERSAL_PATTERNS):
        return True
    # Versione-specifica: deve matchare il pattern del sito
    for p in patterns:
        if filename.startswith(p) or p.lower() in filename.lower():
            # Esclude file dell'altra versione
            other_patterns = [
                pp for v, pps in VERSION_PATTERNS.items() if v != version for pp in pps
            ]
            if any(filename.startswith(op) for op in other_patterns):
                return False
            return True
    # Se il file non ha pattern versione, è universale
    if not any(filename.startswith(p) for v in VERSION_PATTERNS.values() for p in v):
        return True
    return False


def _deduplicate_files(files: set[str]) -> set[str]:
    """Per ogni base bundle, tieni solo la versione numerica più alta."""
    pattern = re.compile(r"^(.+?)_(\d{1,3})_CSS$")
    grouped: dict[str, list[tuple[int, str]]] = defaultdict(list)
    non_versioned: set[str] = set()
    for f in files:
        m = pattern.match(f)
        if m:
            grouped[m.group(1)].append((int(m.group(2)), f))
        else:
            non_versioned.add(f)
    result = set(non_versioned)
    for base, versions in grouped.items():
        _, best = max(versions, key=lambda x: x[0])
        result.add(best)
    return result


def _collapse_ms_patches(files: set[str]) -> set[str]:
    """Collassa varianti OS (Win10/S2016/S2022) in unica voce _ALL_."""
    os_pattern = re.compile(
        r"(v\d+[A-Za-z0-9]+_64bit_)(Windows10LTSC_\w+|Windows10|S2016|S2022)(_\w+\.zip)"
    )
    result: set[str] = set()
    collapsed: dict[str, str] = {}
    for f in files:
        m = os_pattern.match(f)
        if m:
            base = m.group(1)
            suffix = m.group(3)
            key = base + "ALL" + suffix
            if "ALL" in f:
                collapsed[key] = f
            else:
                collapsed.setdefault(key, f)
        else:
            result.add(f)
    result.update(collapsed.values())
    return result


def _extract_files_from_doc(slug: str) -> list[str]:
    doc_path = DOCUMENTS_DIR / f"{slug}.md"
    if not doc_path.exists():
        logger.warning(f"Documento non trovato: {doc_path.name}")
        return []
    text = doc_path.read_text(encoding="utf-8")
    found = FILE_REGEX.findall(text)
    return list(set(found))


def build_patch_list(defer_rows: list[dict]) -> dict:
    """
    Costruisce la struttura patch per sito a partire dalle righe DEFER.

    Ritorna:
    {
      "Lonigo": {
        "workstation_ms": {"v14LTS_64bit_ALL_Oct2024.zip": ["N1","N2"]},
        "server_ms":      {"HyperV2022Host_ALL_Feb2026.zip": ["S1"]},
        "firmware":       {"DeltaV_1431_CTRL_Q_15_CSS": {"type":"controller","nodes":["C1"]}},
      }, ...
    }
    """
    # Raggruppa per sito
    by_site: dict[str, list[dict]] = defaultdict(list)
    for row in defer_rows:
        site = row["site"].split(" - ")[0].strip()  # "Lonigo - Produzione" → "Lonigo"
        by_site[site].append(row)

    result = {}
    for site, rows in by_site.items():
        version = DELTAV_VERSIONS.get(site, "v15LTS")

        ws_ms: dict[str, set[str]] = defaultdict(set)
        srv_ms: dict[str, set[str]] = defaultdict(set)
        firmware: dict[str, dict] = {}

        for row in rows:
            slug = _kba_to_slug(row["kba_number"])
            # Una cella può contenere più nodi separati da newline
            raw_nodes = [n.strip() for n in row["node"].split("\n") if n.strip()]
            files_for_kba = _extract_files_from_doc(slug)
            compatible = _deduplicate_files(
                _collapse_ms_patches({f for f in files_for_kba if _is_compatible(f, version)})
            )

            for f in compatible:
                is_ri = any(p in f for p in RI_PATTERNS)
                is_srv = any(p.lower() in f.lower() for p in ["HyperV", "Intel_", "DVS"])
                is_ctrl = any(x in f for x in ["_CTRL_", "_EIOC_", "_WIOC_", "_RIOZ"])

                if not raw_nodes:
                    # Nessun nodo esplicito: firmware RI va senza lista nodi
                    if is_ri or is_ctrl:
                        if f not in firmware:
                            firmware[f] = {
                                "type": "controller" if is_ctrl else "io",
                                "nodes": set(),
                            }
                    continue

                for node in raw_nodes:
                    node_type = _classify_node(node)
                    if is_srv:
                        if node_type == "server":
                            srv_ms[f].add(node)
                    elif is_ri or is_ctrl:
                        if f not in firmware:
                            firmware[f] = {
                                "type": "controller" if is_ctrl else "io",
                                "nodes": set(),
                            }
                        if node_type == "controller":
                            firmware[f]["nodes"].add(node)
                    elif "64bit" in f or "_WS_" in f:
                        ws_ms[f].add(node)
                    else:
                        ws_ms[f].add(node)

        result[site] = {
            "workstation_ms": {f: sorted(nodes) for f, nodes in ws_ms.items()},
            "server_ms": {f: sorted(nodes) for f, nodes in srv_ms.items()},
            "firmware": {
                f: {"type": v["type"], "nodes": sorted(v["nodes"])} for f, v in firmware.items()
            },
        }
        logger.info(
            f"{site}: {len(ws_ms)} file WS, {len(srv_ms)} file SRV, {len(firmware)} firmware"
        )

    return result
