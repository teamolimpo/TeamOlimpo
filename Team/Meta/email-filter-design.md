---
title: email_processor — Disegno filtro intelligente
status: draft
date: 2026-05-19
version: 0.1
autori: Poros, Stefano (user)
strumenti: Library/tools/email_processor/
stato: da implementare
---

# Filtro Intelligente per email_processor

## 1. Problema

Il vault email contiene **~70% di rumore** (alert Zabbix, Patrol Read, newsletter, report automatici) su 592 email/settimana. Le email importate singolarmente sono:
- Per lo più **identiche tra loro** (stesso errore Zabbix ripetuto ogni 10 minuti)
- **Senza valore informativo** per l'utente
- **Costo computazionale** inutile per Eunomia (deve leggerle tutte per scoprire che sono rumore)

## 2. Architettura — 3 Layer

```
┌─────────────────────────────────────────────────────────────┐
│                    LAYER 1 — DISCOVERY                       │
│           tool per analizzare e classificare pattern         │
│           Output: filter_rules.yaml (generato/aggiornato)    │
└──────────────────────────┬──────────────────────────────────┘
                           │
                           ▼
┌─────────────────────────────────────────────────────────────┐
│                    LAYER 2 — RUNTIME                         │
│           filter.py: carica YAML, classifica email,          │
│           decide discard/aggregate/keep                      │
└──────────────────────────┬──────────────────────────────────┘
                           │
                           ▼
┌─────────────────────────────────────────────────────────────┐
│                    LAYER 3 — FEEDBACK                        │
│           Eunomia + utente: raffinamento continuo            │
│           Azioni utente → nuove regole YAML                  │
└─────────────────────────────────────────────────────────────┘
```

---

## 3. Layer 1 — Discovery Tool

### 3.1 Scopo
Analizzare un set di email (esistenti o in arrivo) e **proporre pattern** all'utente per la classificazione.

### 3.2 Comando CLI
```bash
uv run python -m tools.email_processor discover
uv run python -m tools.email_processor discover --days 7
uv run python -m tools.email_processor discover --path vaults/email/Inbox/emails/
```

### 3.3 Algoritmo
1. Scansiona tutte le note Markdown (o file .eml)
2. Per ogni email, estrae:
   - Subject (normalizzato: lowercase, rimuovi [EXTERNAL], data/ora variabili)
   - From (dominio, nome mittente)
   - Message-ID
3. **Raggruppa** per pattern:
   - Subject simili → cluster
   - Sender identico → gruppo
4. Per ogni gruppo, calcola:
   - Conteggio occorrenze
   - Range date
   - Mittenti coinvolti
   - Variabilità del subject (es. cambia solo timestamp → stesso pattern)
5. Mostra output interattivo

### 3.4 Output discovery

```
$ uv run python -m tools.email_processor discover --days 7

📊 EMAIL DISCOVERY — Periodo: 2026-05-12 → 2026-05-19
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
  Totale file: 592 | Messaggi unici: 195

🔍 PATTERN TROVATI:

#  Pattern                                         Count  Azione Attuale
── ─────────────────────────────────────────────── ───── ───────────────
 1  "Problem: * in errore" (Zabbix alerts)           82  [NON ASSEGNATA]
 2  "Patrol Read * started/completed" (RAID)         16  [NON ASSEGNATA]
 3  "ALERT RECAP ON *"                               12  [NON ASSEGNATA]
 4  "FIS *" (technical work)                         11  [NON ASSEGNATA]
 5  "BACKUP FAILED/NOT RESPONDING/ACTIVITY"           5  [NON ASSEGNATA]
 6  "Emerson Daily Digest"                            5  [NON ASSEGNATA]
 7  "Predictive failure * Disk *"                     4  [NON ASSEGNATA]
 8  "McAfee AV report *"                              3  [NON ASSEGNATA]
 9  "BACKUP REPORT: *"                                3  [NON ASSEGNATA]
10  "Safety *"                                        3  [NON ASSEGNATA]
11  "ESPP *"                                          1  [NON ASSEGNATA]
12  ... altri ...

💡 Suggerimenti:
  • I pattern 1-2-3-6-8-9 sono probabilmente RUMORE (automazioni)
  • Il pattern 4 è probabilmente LAVORO (manutenzione FIS)

  Vuoi assegnare azioni? (usa discover --interactive)
```

### 3.5 Modalità interattiva

```bash
uv run python -m tools.email_processor discover --interactive
```

Mostra ogni pattern con menu:
```
Pattern #1: "Problem: * in errore" (82 email da zabbixsrv@fisvi.com)
  [t] TENERE — importa normalmente
  [s] SCARTA — non importare mai
  [a] AGGREGA — compatta in riepilogo giornaliero
  [f] CHIEDIMI DOPO — flagga per revisione
  [d] DETTAGLI — mostra 3 esempi
  [k] SALTA — non decidere ora
  >
```

Alla fine genera `filter_rules.yaml`.

### 3.6 Generatore YAML

Il comando `discover --generate` produce il file YAML completo sulla base delle decisioni prese.

---

## 4. Layer 2 — Runtime Filter Engine

### 4.1 File: `Library/tools/email_processor/filter.py`

Componenti:

```
filter.py
├── class RuleEngine
│   ├── load_rules(path)         → carica YAML
│   ├── classify(email_data)     → restituisce ClassificationResult
│   └── match_rule(email, rule)  → True/False per singola regola
│
├── class ClassificationResult
│   ├── action: str              → "discard" | "aggregate" | "keep"
│   ├── rule_id: str             → regola che ha matchato
│   ├── label: str | None        → etichetta (opzionale)
│   ├── aggregate_to: str | None → path aggregato
│   └── flag: str | None         → "unchecked" se fallback
│
└── operatori di match
    ├── match_contains(text, patterns)
    ├── match_starts_with(text, patterns)
    ├── match_regex(text, pattern)
    ├── match_not_contains(text, patterns)
    ├── match_and(conditions)        → tutte vere
    └── match_or(conditions)         → almeno una vera
```

### 4.2 Formato YAML (dettaglio)

```yaml
version: 1
rules:

  # ── DISCARD ──
  - id: "patrol-read"
    name: "Patrol Read RAID operations"
    action: discard
    match:
      subject:
        contains: ["Patrol Read", "The Patrol Read"]
    reason: "RAID self-test — zero informational value"

  # ── AGGREGATE ──
  - id: "zabbix-problem"
    name: "Zabbix monitoring alerts"
    action: aggregate
    aggregate_to: "_review/daily/zabbix-{date}.md"
    match:
      subject:
        contains: ["Problem:"]
      from:
        contains: ["zabbixsrv"]
    field_extract:
      device:
        pattern: "Problem:\\s*(.+?)(?:\\sin|$)"
        default: "unknown"
      severity:
        pattern: "in errore"
        value: "error"

  # ── KEEP ──
  - id: "fis-technical"
    name: "FIS technical work"
    action: keep
    label: "fis-work"
    match:
      subject:
        contains: ["FIS"]
      from:
        not_contains: ["zabbixsrv", "backup"]
    priority: 50

  # ── FALLBACK (implicito, non serve nel YAML) ──
```

### 4.3 Campi match supportati

| Campo | Operatori | Esempio |
|-------|-----------|---------|
| `subject` | `contains`, `starts_with`, `ends_with`, `contains_regex`, `not_contains` | `contains: ["BACKUP FAILED"]` |
| `from` | `contains`, `not_contains`, `contains_regex` | `contains: ["@fisvi.com"]` |
| `body` | `contains`, `contains_regex` | `contains: ["urgente"]` |
| `to` | `contains` | `contains: ["stefano"]` |
| Combinazioni | `and` / `or` implicito | Più campi = AND; stessi campo = OR |

### 4.4 Funzionamento `classify()`

```python
def classify(email_data: dict) -> ClassificationResult:
    """
    Ordina regole per priorità decrescente.
    Per ogni regola: se matcha, restituisce l'azione.
    Se nessuna regola matcha: restituisce keep + flag:unchecked.
    """
    for rule in self.sorted_rules:
        if self.match_rule(email_data, rule):
            return ClassificationResult(
                action=rule["action"],
                rule_id=rule["id"],
                label=rule.get("label"),
                aggregate_to=rule.get("aggregate_to"),
                flag=rule.get("flag"),
            )
    # Fallback
    return ClassificationResult(
        action="keep",
        rule_id="__fallback__",
        flag="unchecked",
    )
```

### 4.5 Integrazione in `cli.py`

Modifica di `_run_import()`:

```python
def _run_import(vault_root, email_dir, limit=None):
    # ... (parsing esistente) ...

    # NUOVO: carica rules engine
    filter_engine = RuleEngine()
    filter_engine.load_rules(Path(__file__).parent / "filter_rules.yaml")
    aggregator = Aggregator(vault_root)

    for idx, eml_path in enumerate(eml_files):
        data = _parse_eml(eml_path)

        # NUOVO: classifica l'email
        result = filter_engine.classify(data)

        if result.action == "discard":
            logger.info(f"DISCARD: {eml_path.name} ({result.rule_id})")
            skipped_count += 1
            continue

        if result.action == "aggregate":
            aggregator.add_entry(result.aggregate_to, data, eml_path)
            skipped_count += 1
            continue

        # keep: import normale (con eventuale flag)
        # ... (codice esistente) ...
        if result.flag:
            data["flag"] = result.flag
        # ... scrivi nota ...
```

---

## 5. Layer 3 — Feedback Loop

### 5.1 Trigger di feedback

| Trigger | Azione | Risultato |
|---------|--------|-----------|
| Utente cancella nota | Eunomia rileva | Suggerisci regola DISCARD per quel pattern |
| Nota flagged resta `unchecked` per >7gg | Auto-suggest | "Questa nota non è mai stata letta: vuoi creare regola DISCARD?" |
| Eunomia processa e classifica | Arricchimento | Se Eunomia trova pattern ricorrenti, suggerisce regole |
| Nuovo `discover` | Manuale | "Da marzo sono comparsi N nuovi pattern" |

### 5.2 Comando feedback

```bash
# Analizza le note flagged e suggerisce regole
uv run python -m tools.email_processor feedback

# Mostra statistiche: quante note flagged, quanti pattern non coperti
uv run python -m tools.email_processor feedback --stats

# Applica suggerimenti automaticamente (dopo approvazione)
uv run python -m tools.email_processor feedback --apply
```

---

## 6. Aggregator

### 6.1 File: `Library/tools/email_processor/aggregator.py`

```python
class Aggregator:
    def __init__(self, vault_root: Path):
        self.vault_root = vault_root

    def add_entry(self, template_path: str, email_data: dict, source: Path):
        """
        Aggiunge una riga al file di riepilogo giornaliero.
        template_path: "_review/daily/zabbix-{date}.md"
        """
        # 1. Risolve {date} → data odierna
        # 2. Determina se file esiste già
        # 3. Se esiste: carica, deduplica (stesso device/errore), aggiorna conteggio
        # 4. Se non esiste: crea con header
        pass

    def get_daily_path(self, template_path: str) -> Path:
        """Risolve template path con data corrente."""
        date_str = datetime.now().strftime("%Y-%m-%d")
        path_str = template_path.replace("{date}", date_str)
        return self.vault_root / path_str
```

### 6.2 Formato file aggregato

File `_review/daily/zabbix-2026-05-19.md`:

```markdown
# Riepilogo Zabbix — 2026-05-19

## Nuovi problemi (7)
| Device | Problema | Prima segnalazione | Oggi |
|--------|----------|--------------------|------|
| MM_Z1_ZSERVZ1 | in errore | 2026-05-12 | 24 alert |
| MM_Z2_ZSERVZ2 | in errore | 2026-05-13 | 12 alert |
| IT_MM-W19-DV-CYB01 | restarted | 2026-05-19 | 3 alert |
| MM-Z1_CTRL90 | Performance Index=1 | 2026-05-15 | 6 alert |

## Problemi risolti (2)
| Device | Problema | Durata |
|--------|----------|--------|
| MM_Z3_SW-S11S-DVZ3-01 | in errore | 2 giorni |
| TE-AX0P-HST14 | backup not responding | 3 giorni |

## Statistiche
- Totale alert oggi: 73 (da 15 device)
- Di cui nuovi: 2
- Di cui risolti: 2
- Più rumoroso: MM_Z1_ZSERVZ1 (24 alert)
```

---

## 7. Regole predefinite (basate sull'analisi reale)

### DISCARD
| Regola | Pattern | Motivazione |
|--------|---------|-------------|
| Patrol Read | `"Patrol Read"` in subject | Self-test RAID, info zero |
| Login/Logout | `"logged in using"`, `"session for"`, `"logged off"` in subject | Log di accesso |
| Daily Digest | `"Daily Digest"`, `"Emerson Daily"` in subject | Newsletter |
| Flashnews | `"Flashnews"`, `"NICE TO KNOW"` in subject | Newsletter HR |
| Spam Quarantine | `"ProofPoint Spam Quarantine"` in subject | Notifica spam |
| McAfee AV Report | `"McAfee AV"` in subject | Report automatico |
| Backup Weekly Report | `"BACKUP REPORT:"`, `"REPORT DI BACKUP"`, `"Rubrik Report"` in subject | Report automatico |
| SharePoint News | `"News you might have missed"` | Notifica automatica |
| CRM Restored | `"SERVICE RESTORED"` in subject | Già risolto |
| UNIFY | `"UNIFY"` in subject subject | Notifica sistema |

### AGGREGATE
| Regola | Pattern | File destinazione |
|--------|---------|-------------------|
| Zabbix Problem | `"Problem:"` in subject + `zabbixsrv` in from | `_review/daily/zabbix-{date}.md` |
| Backup Failed | `"BACKUP FAILED"`, `"BACKUP IS NOT RESPONDING"`, `"ACTIVITY IS NOT RESPONDING"`, `"L'ATTIVITÀ NON RISPONDE"`, `"BACKUP manuali non eseguiti"` in subject | `_review/daily/backup-{date}.md` |
| Disk Predictive | `"predictive failure"`, `"disk media error"` in subject | `_review/daily/hw-warnings-{date}.md` |
| Alert Recap | `"ALERT RECAP"` in subject | `_review/daily/zabbix-{date}.md` |
| CyberArk | `"CyberArk"` in subject | `_review/daily/security-{date}.md` |


### KEEP
| Regola | Pattern | Label |
|--------|---------|-------|
| FIS Technical | `"FIS"` in subject + parole chiave tecniche (da definire) | `fis-work` |
| GSC Meetings | `"GSC"`, `"minutes:"` in subject | `meetings` |
| Safety/CEO | `"Safety Day"`, `"safety metrics"`, `"Company Update"`, `"All Employee Meeting"`, `"From the Desk of"` in subject | `company` |
| HR/Actions | `"ESPP"`, `"730"`, `"should know"`, `"timesheet"`, `"giustificativi"`, `"form trasferte"`, `"expense"` in subject | `admin` |
| Sales/License | `"Sales Order"`, `"Acronis"`, `"CTS open calls"` in subject | `commerciale` |

---

## 8. Implementazione — Roadmap

### Fase 1 — Discovery Tool (Layer 1)
- [ ] `Library/tools/email_processor/discovery.py` — analisi pattern
- [ ] `discover` comando CLI
- [ ] Output tabellare dei pattern trovati
- [ ] Generazione YAML da pattern

### Fase 2 — Runtime Engine (Layer 2)
- [ ] `Library/tools/email_processor/filter.py` — RuleEngine
- [ ] `Library/tools/email_processor/filter_rules.yaml` — regole iniziali
- [ ] `Library/tools/email_processor/aggregator.py` — Aggregator
- [ ] Integrazione in `cli.py` (`_run_import`)

### Fase 3 — Feedback (Layer 3)
- [ ] `feedback` comando CLI
- [ ] Rilevamento note flagged non lette
- [ ] Suggerimenti automatici di regole
- [ ] Aggiornamento YAML da feedback

### Fase 4 — Raffinamento
- [ ] Test su dataset reale (592 email)
- [ ] Validazione: confronto "prima/dopo" filtro
- [ ] Iterazione sulle regole con utente

---

## 9. Criteri di successo

| Metrica | Obiettivo |
|---------|-----------|
| Riduzione file importati | Da 592/sett → <100/sett |
| Zero falsi negativi | Nessuna email utile persa |
| Zero falsi positivi KEEP | Tutte le KEEP sono effettivamente utili |
| Copertura regole | >90% email classificate (non fallback) |
| Aggregati leggibili | Riepiloghi giornalieri interpretabili in 10s |

---

## 10. Rischi

| Rischio | Mitigazione |
|---------|-------------|
| Nuovo tipo di email importante non visto | Fallback keep + flag:unchecked |
| Regola troppo aggressiva (scarta cose utili) | Discovery periodico + feedback loop |
| YAML cresce troppo | Revisione periodica, merge pattern simili |
| Aggregati duplicano stessi dati | Deduplica per device + conteggio, non riga per riga |

---

*Documento generato il 2026-05-19 — da trasformare in specifica implementativa per Efesto*
