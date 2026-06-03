from pathlib import Path

from tools.common.paths import project_root

PROJECT_ROOT = project_root()
INBOX_DIR = PROJECT_ROOT / "Team" / "Inbox"
OWNERS_INBOX_DIR = PROJECT_ROOT / "lib" / "deliverables"
HANDOFF_DIR = PROJECT_ROOT / "lib" / "Handoff"
CATALOG_DIR = PROJECT_ROOT / "lib" / "data" / "kba_catalog" / "records"
DOCUMENTS_DIR = PROJECT_ROOT / "lib" / "documents"
LOG_FILE = PROJECT_ROOT / "lib" / "data" / "kba_reporter.log"

DELTAV_VERSIONS = {
    "Lonigo": "v14LTS",
    "Montecchio": "v15LTS",
    "Termoli": "v15LTS",
}
VERSION_PATTERNS = {
    "v14LTS": ["v14LTS_", "DeltaV_1431_"],
    "v15LTS": ["v15LTS_", "DeltaV_15LTS_"],
}
RI_PATTERNS = ["DeltaV_RI_"]
UNIVERSAL_PATTERNS = ["HyperV", "Dell ", "Intel_", "DVS"]

NODE_TYPES = {
    "workstation": [
        "OWS",
        "OTS",
        "ENG",
        "OPC",
        "APP",
        "DVINST",
        "MAN",
        "PRO",
        "OPE",
        "SRC",
        "ZSERV",
        "BEH",
        "BEX",
    ],
    "server": ["DC0", "DVHPH", "vrtx", "HST"],
    "controller": ["CTRL", "CTLR"],
}

DEFER_KEYWORDS = [
    "{DEFER}",
    "deferred",
    "next stop",
    "planned maintenance",
    "next plant stop",
    "next service interval",
    "next production shutdown",
    "next shutdown",
    "fermata",
    "To be considered as planned maintenance",
    "can be considered as part of standard maintenance",
    "Included in the scheduled FIS maintenance plan",
]
WIP_KEYWORDS = [
    "{WIP}",
    "{FLAG}",
    "to check",
    "TO CHECK",
    "To Check",
    "to discuss",
    "being evaluated",
    "under investigation",
    "da valutare",
    "da attenzionare",
    "very low impact",
    "Check with FIS",
]
DONE_NA_KEYWORDS = ["{DONE}", "{NA}", "{ACK}"]

ANALYSIS_MAX_AGE_DAYS = 14
GROK_MODEL = "grok-4.20-0309-reasoning"
