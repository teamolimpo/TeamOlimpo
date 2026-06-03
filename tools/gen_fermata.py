import csv, re, yaml
from pathlib import Path
from collections import defaultdict

from tools.common.paths import project_root

BASE = project_root()
CATALOG = BASE / "lib/data/kba_catalog/records"

DEFER_KEYWORDS = [
    "{DEFER}",
    "deferred",
    "next stop",
    "planned maintenance",
    "next plant stop",
    "next service interval",
    "next production shutdown",
]

SITE_ORDER = ["Lonigo", "Montecchio", "Termoli"]

GROUP_TITLES = {
    "security": "Aggiornamenti sicurezza (Microsoft/OS)",
    "firmware_io": "Aggiornamento firmware I/O e controller",
    "firmware_ctrl": "Aggiornamento firmware controller",
    "software_deltav": "Aggiornamento software DeltaV",
    "other": "Altri interventi",
}

KBA_DESCRIPTIONS = {
    "AK-1300-0005": "Installare patch di sicurezza Microsoft per workstation e server DeltaV",
    "AK-1200-0033": "Applicare aggiornamenti sicurezza per infrastruttura di virtualizzazione DeltaV",
    "AP-0900-0040": "Applicare aggiornamento servizio upgrade DeltaV (Offline/Online Upgrade Service)",
    "NK-2000-0562": "Aggiornare Smart Firewall e workstation DeltaV (ref. NK-2000-0562)",
    "NK-2200-0472": "Aggiornare Dell OpenManage Server Administrator all'ultima versione supportata",
    "NK-2400-0150": "Aggiornare OS Recovery Media workstation DeltaV (T5860XL/T5820/T5810)",
    "NK-2000-0458": "Applicare patch sicurezza per workstation DeltaV e hardware virtualizzazione",
    "NK-2000-0460": "Aggiornare firmware Wyse thin client e Teradici zero client",
    "NK-2200-0460": "Installare hotfix correttivo per funzione Re-send Last Known Good Download su controller",
    "NK-2500-0045": "Aggiornare software DeltaV alla versione che risolve il problema noto (ref. NK-2500-0045)",
    "NK-2500-0639": "Aggiornare DeltaV Virtual Studio e DVBR alla versione raccomandata",
    "NK-2400-0177": "Aggiornare DeltaV Virtual Studio DVS v4.3.3 con fix correttivo",
    "NK-2400-0467": "Aggiornare software DeltaV workstation alla versione corretta (ref. NK-2400-0467)",
    "NK-2000-0197": "Aggiornare firmware schede AI/AO HART alla versione raccomandata",
    "NK-2500-0022": "Installare fix per ripristino funzione Re-send Last Known Good Download su controller",
    "NK-2300-0038": "Aggiornare bundle firmware Zone 2 Remote IO e WIOC per risolvere standby controller instabile",
    "NK-2400-0329": "Aggiornare firmware CIOC ridondante alla versione raccomandata (ref. NK-2400-0329)",
    "NK-2400-0257": "Aggiornare bundle firmware controller PK alla versione raccomandata",
    "NK-2300-0470": "Aggiornare bundle firmware controller PK e MX (ref. NK-2300-0470)",
    "NK-2300-0472": "Aggiornare bundle firmware controller PK e MX (ref. NK-2300-0472)",
    "NK-2300-0357": "Monitorare e applicare fix DeltaV workstation su ZSERVZ1 (ref. NK-2300-0357)",
    "NK-2300-0351": "Aggiornare bundle firmware controller PK su ZSERVZ1 (ref. NK-2300-0351)",
    "NK-2300-0474": "Aggiornare software DeltaV workstation inter-zona su ZSERVZ1 (ref. NK-2300-0474)",
    "NK-2300-0102": "Aggiornare software DeltaV workstation terminale su ZSERVZ1 (ref. NK-2300-0102)",
    "NK-2200-0236": "Applicare workaround per problema I/O controller su RIO-ALLPORT (ref. NK-2200-0236)",
    "NK-1700-0089": "Applicare configurazione raccomandata per hardware virtualizzazione DVS v3.3.x",
}


def parse_record(path):
    text = path.read_text(encoding="utf-8")
    m = re.match(r"^---\s*\n(.*?)\n---\s*\n", text, re.DOTALL)
    fm = {}
    if m:
        yaml_text = "\n".join(l for l in m.group(1).split("\n") if not l.strip().startswith("#"))
        try:
            fm = yaml.safe_load(yaml_text) or {}
        except Exception:
            pass

    def get_section(name):
        pat = r"## " + re.escape(name) + r"\s*\n(.*?)(?=\n## |\Z)"
        sm = re.search(pat, text, re.DOTALL)
        return sm.group(1).strip() if sm else ""

    fm["_workaround_text"] = get_section("Workaround")
    fm["_sintesi"] = get_section("Sintesi")
    fm["_recommendation"] = get_section("Raccomandazione").strip()
    return fm


def classify_group(ptype, emcat, title, affected_products):
    prod_str = " ".join(str(p) for p in (affected_products or [])).lower()
    if ptype == "security_vulnerability":
        return "security"
    if ptype == "bug_software":
        io_keywords = [
            "i/o",
            "cioc",
            "eioc",
            "wioc",
            "rio",
            "scanner",
            "wireless i/o",
            "zone 2",
            "controller",
        ]
        if any(kw in prod_str for kw in io_keywords):
            return "firmware_io"
        ws_keywords = ["workstation", "workstation software", "deltav software", "iddc", "deltav"]
        if any(kw in prod_str for kw in ws_keywords):
            return "software_deltav"
        return "other"
    return "other"


def workaround_short(text):
    if not text or "nessun workaround" in text.lower():
        return None
    first = re.split(r"[.;]\s", text)[0].strip()
    if len(first) > 80:
        first = first[:77] + "..."
    return first


def build_merged_items(entries):
    by_kba = defaultdict(list)
    for e in entries:
        by_kba[e["kba"]].append(e)

    by_desc = defaultdict(lambda: {"kbas": [], "nodes": [], "workaround": None})
    for kba, elist in by_kba.items():
        desc = elist[0]["desc"]
        all_nodes = []
        for e in elist:
            all_nodes.extend(e["nodes"])
        wa = elist[0]["workaround"]
        by_desc[desc]["kbas"].append(kba)
        by_desc[desc]["nodes"].extend(all_nodes)
        if wa and not by_desc[desc]["workaround"]:
            by_desc[desc]["workaround"] = wa

    result = []
    for desc, data in by_desc.items():
        result.append(
            {
                "desc": desc,
                "kbas": data["kbas"],
                "nodes": sorted(set(data["nodes"])),
                "workaround": data["workaround"],
            }
        )
    return result


# Load CSV
rows = []
with open(BASE / "Inbox/KBA_Merged_010426_101532.csv", newline="", encoding="utf-8-sig") as f:
    reader = csv.DictReader(f)
    for row in reader:
        rows.append(row)

# Filter
filtered = []
for row in rows:
    notes = row.get("User Notes", "").lower()
    if any(kw.lower() in notes for kw in DEFER_KEYWORDS):
        filtered.append(row)

# Check missing catalog records
unique_kbas = list(dict.fromkeys(r["KBA Number"] for r in filtered))
missing_catalog = [k for k in unique_kbas if not (CATALOG / (k.lower() + ".md")).exists()]

# Load catalog data
catalog_data = {}
for row in filtered:
    kba = row["KBA Number"]
    if kba in catalog_data:
        continue
    path = CATALOG / (kba.lower() + ".md")
    if path.exists():
        catalog_data[kba] = parse_record(path)
    else:
        catalog_data[kba] = {}

# Build groups
groups = defaultdict(lambda: defaultdict(list))

for row in filtered:
    kba = row["KBA Number"]
    site = row["Site"].strip()
    nodes_raw = row["Node Name / Node Assignment"].replace("\n", ",").strip()
    nodes = [n.strip() for n in re.split(r"[,\n]+", nodes_raw) if n.strip()]
    title = row["Title"]
    ptype = row["Problem Type"]
    emcat = row["Emerson Category"]
    cd = catalog_data.get(kba, {})
    affected = cd.get("affected_products", []) or []
    grp = classify_group(ptype, emcat, title, affected)
    wa = cd.get("workaround_available", False)
    wt = cd.get("_workaround_text", "")
    ws = workaround_short(wt) if wa else None
    desc = KBA_DESCRIPTIONS.get(kba, f"Applicare fix correttivo (ref. {kba})")
    groups[grp][site].append(
        {
            "kba": kba,
            "nodes": nodes,
            "desc": desc,
            "workaround": ws,
        }
    )

# Generate Markdown
lines = []
lines.append("# Attivita' in fermata — Aprile 2026")
lines.append("")

group_order = ["security", "firmware_io", "firmware_ctrl", "software_deltav", "other"]
stats = defaultdict(lambda: defaultdict(int))

for grp in group_order:
    site_data = groups[grp]
    if not site_data:
        continue
    lines.append("---")
    lines.append("")
    lines.append("## " + GROUP_TITLES[grp])
    lines.append("")

    for site in SITE_ORDER:
        entries = site_data.get(site, [])
        if not entries:
            continue
        lines.append("### " + site)
        merged = build_merged_items(entries)
        for item in merged:
            nodes_str = ", ".join(item["nodes"]) if item["nodes"] else "_nodi non specificati_"
            kba_refs = ", ".join(item["kbas"])
            desc = item["desc"]
            if len(item["kbas"]) > 1:
                desc = re.sub(r"\s*\(ref\. [A-Z]+-\d+-\d+\)", "", desc).strip()
                desc = desc + " (" + kba_refs + ")"
            wa = item["workaround"]
            line = "- [ ] **" + nodes_str + "** — " + desc
            if wa:
                line += " (workaround: " + wa + ")"
            lines.append(line)
            stats[site][grp] += 1
        lines.append("")

lines.append("---")

output = "\n".join(lines)
out_path = BASE / "Library/deliverables/attivita-fermata-010426.md"
out_path.parent.mkdir(exist_ok=True)
out_path.write_text(output, encoding="utf-8")
print("Written: " + str(out_path))

print("\n=== STATISTICHE PER SITO ===")
grand_total = defaultdict(int)
for site in SITE_ORDER:
    total = sum(stats[site].values())
    grand_total[site] = total
    print("\n" + site + ": " + str(total) + " voci totali")
    for grp in group_order:
        if stats[site][grp]:
            print("  " + GROUP_TITLES[grp] + ": " + str(stats[site][grp]))

print("\n=== KBA SENZA RECORD CATALOGO ===")
if missing_catalog:
    for k in missing_catalog:
        print("  MISSING: " + k)
else:
    print("  Nessuna KBA mancante.")
