---
title: Indice degli Strumenti del Team Olimpo
aliases: [strumenti, tools, script]
tags: [meta, strumenti, indice]
---

# Strumenti del Team Olimpo — Indice

Riepilogo di tutti gli script e moduli Python disponibili nel repository. Per ogni strumento è indicato il percorso, il responsabile di riferimento e un link alla guida dettagliata.

---

## Strumenti attivi

| Strumento | Percorso | Cosa fa | Responsabile | Guida |
|-----------|----------|---------|--------------|-------|
| **kba_pipeline** | `tools/kba/pipeline/` | **Orchestratore principale** — pipeline completa PDF → Markdown → catalogo → Excel arricchito | Efesto | [[tools/kba/pipeline/guida]] |
| **pdf_converter** | `tools/pdf_converter/` | Converte PDF in Markdown con estrazione immagini, post-processing e indicizzazione SQLite | Efesto | [[pdf-converter-guida]] |
| **consulto** | `tools/consulto/` | CLI per consulti rapidi a AI di terze parti (xAI/Grok e Google/Gemini) | Efesto | [[consulto-guida]] |
| **kba_indexer** | `tools/kba/indexer/` | Indicizza batch MD nel catalogo KBA con parsing JSON e riscrittura index.yaml | Efesto | [[tools/kba/indexer/guida]] |
| **kba_reporter** | `tools/kba/reporter/` | Genera brief WIP e lista patch (vecchio flusso su User Notes) | Efesto/Hermes | [[tools/kba/reporter/guida]] |
| **kba_merger** | `tools/kba/merger/` | Merge export DeltaV, enrichment + CSS lookup, gap analysis ricorsiva, Suggested Note + Stefano's Notes | Efesto | [[tools/kba/merger/guida]] |
| **kba_fermata** | `tools/kba/fermata/` | Genera Excel 4 sheet attività in fermata da KBA con {DEFER} in Stefano's Notes | Efesto | [[tools/kba/fermata/guida]] |
| **kba_meeting** | `tools/kba/meeting/` | Genera documento meeting cliente da KBA con {WIP} in Stefano's Notes via Dike/Grok | Efesto | [[tools/kba/meeting/guida]] |
| **handoff_register** | `tools/handoff_register/` | Archiviazione file handoff completati e rigenerazione indice Registro.md | Efesto | [[handoff-register-guida]] |

---

## kba_pipeline

**Tipo**: modulo Python con CLI
**Versione**: 0.1.0
**Dipendenze principali**: `openpyxl`, `loguru`, `rich`, `pyyaml`, `openai`, `google-genai`, `xai-sdk`

**Orchestratore principale del flusso KBA.** Esegue in sequenza: conversione PDF, analisi AI, verifica dipendenze documentali, merge + enrichment Excel. Punto di ingresso unico per l'intero flusso operativo.

**Uso tipico**:

```powershell
# Flusso completo
uv run python -m tools.kba_pipeline run Inbox/KBA.xlsx

# Saltare la conversione (PDF già convertiti)
uv run python -m tools.kba_pipeline run Inbox/KBA.xlsx --skip-convert

# Ri-analizzare con modello aggiornato (solo record stale)
uv run python -m tools.kba_pipeline run Inbox/KBA.xlsx --skip-convert --force-analyze --model-analyze grok-4.20-0309-reasoning

# Merge rapido senza AI
uv run python -m tools.kba_pipeline run Inbox/KBA.xlsx --skip-convert --skip-analyze --no-ai-merge
```

→ Guida completa: [[tools/kba/pipeline/guida]]

---

## consulto

**Tipo**: modulo Python con CLI
**Versione**: 0.4.0
**Dipendenze principali**: `openai`, `google-genai`, `xai-sdk`, `python-dotenv`, `loguru`

Permette di interrogare LLM di terze parti (Grok e Gemini) da riga di comando per consulti rapidi, second opinion, elaborazioni batch e audit esterni. Output pipeable su stdout, errori su stderr.

**Modalità di utilizzo**:

| Modalità | Comando | Descrizione breve |
|----------|---------|-------------------|
| **Singola** | `uv run python -m tools.consulto "prompt"` | Consulto singolo su Grok |
| **Singola** | `uv run python -m tools.consulto --provider gemini "prompt"` | Consulto su Gemini |
| **Singola** | `uv run python -m tools.consulto --model <modello> "prompt"` | Override modello |
| **Singola** | `uv run python -m tools.consulto --stdin < file.txt` | Legge prompt da file |
| **Singola** | `uv run python -m tools.consulto -v "prompt"` | Output verbose (token ↑↓ separati, tempo, costo) |
| **Multi-agent** | `uv run python -m tools.consulto --model grok-4.20-multi-agent-0309 --agent-count 4 "prompt"` | Multi-agent xAI (4 o 16 agenti) |
| **Models** | `uv run python -m tools.consulto models` | Lista modelli disponibili e prezzi |
| **Models** | `uv run python -m tools.consulto models --provider grok` | Lista modelli di un provider |
| **Batch** | `uv run python -m tools.consulto --prompt template.md --input "docs/*.md" --output <dir>` | Elabora più file con template |
| **Interattivo** | `uv run python -m tools.consulto` | Avvia il menu interattivo |
| **Interattivo** | `uv run python -m tools.consulto -i` | Avvia il menu interattivo (esplicito) |

→ Guida completa: [[consulto-guida]]

---

## pdf_converter

**Tipo**: modulo Python con CLI
**Versione**: 0.1.0
**Dipendenze principali**: `pymupdf`, `pymupdf4llm`, `pydantic`, `loguru`, `rich`

Converte i PDF presenti in `Inbox/` in file Markdown compatibili con il vault Obsidian, salva le immagini estratte in `lib/assets/images/`, e indicizza ogni documento in un database SQLite per la ricerca full-text.

**Comandi disponibili**:

| Comando | Descrizione breve |
|---------|-------------------|
| `init` | Inizializza il database e le cartelle |
| `convert <PDF>` | Converte un singolo file PDF |
| `convert-all` | Converte tutti i PDF nuovi nella inbox |
| `search <query>` | Ricerca full-text nei documenti indicizzati |
| `list` | Elenca i documenti nel database |
| `stats` | Statistiche aggregate sui documenti |

→ Guida completa: [[pdf-converter-guida]]

---

## kba_indexer

**Tipo**: modulo Python con CLI
**Versione**: 0.1.0
**Dipendenze principali**: `pyyaml`, `loguru`, `rich`

Indicizza i file batch MD prodotti da `consulto` nel catalogo KBA centralizzato. Parsa il JSON dall'output IA, scrive record MD nel formato di Dike, e riscrive l'indice YAML con statistiche aggregate di rischio.

**Comandi disponibili**:

| Comando | Descrizione breve |
|---------|-------------------|
| `index` | Parsa file batch MD e li indicizza nel catalogo |
| `list` | Elenca i record del catalogo con ordinamento e limitazione |
| `stats` | Mostra statistiche aggregate (total, distribuzione per livello, score min/max/avg) |

**Flag globali**:

| Flag | Descrizione |
|------|-------------|
| `--verbose / -v` | Output debug dettagliato su stderr |

→ Guida completa: [[tools/kba/indexer/guida]]

---

## kba_merger

**Tipo**: modulo Python con CLI
**Versione**: 0.2.0
**Dipendenze principali**: `openpyxl`, `loguru`, `rich`, `pyyaml`, `tools.consulto`, `tools.kba_reporter`

Gestisce l'export Excel DeltaV di Knowledge Base Articles: merge righe duplicate, enrichment dal catalogo (con CSS lookup per Suggested Note), gap analysis base e ricorsiva, apprendimento da revisioni umane.

**Comandi disponibili**:

| Comando | Descrizione breve |
|---------|-------------------|
| `merge` | Merge + enrichment → Excel con Suggested Note e Stefano's Notes |
| `gap` | Gap check KBA: classifica ogni KBA (ok / da_analizzare / da_convertire) |
| `learn` | Legge Excel revisionato e aggiorna il prontuario KBA |

**Flag globali**:

| Flag | Descrizione |
|------|-------------|
| `--verbose / -v` | Output debug dettagliato su stderr |

**Flag specifici per `merge`**:

| Flag | Descrizione |
|------|-------------|
| `--output / -o` | Path esplicito del file di output |
| `--no-enrich` | Disabilita enrichment dal catalogo (merge puro) |
| `--recommend` | Attiva raccomandazioni AI per ogni KBA |
| `--provider` | Provider LLM (grok, gemini) — default: grok |
| `--model` | Override modello LLM |

**Flag specifici per `gap`**:

| Flag | Descrizione |
|------|-------------|
| `--recursive / -r` | Espande il check alle KBA referenziate da fix_reference (BFS) |

**Flag specifici per `learn`**:

| Flag | Descrizione |
|------|-------------|
| `--provider` | Provider LLM per rigenerare rules.md (opzionale) |
| `--model` | Override modello LLM |

→ Guida completa: [[tools/kba/merger/guida]]

---

## kba_fermata

**Tipo**: modulo Python con CLI
**Dipendenze principali**: `openpyxl`, `loguru`, `rich`, `tools.kba_reporter`

Genera l'Excel delle attività in fermata (patch da installare) a partire dal file `KBA_Merged`.
Legge **Stefano's Notes** per classificare le KBA, filtra quelle con `{DEFER}`, estrae i file CSS
compatibili per sito e produce un Excel con 4 sheet.

**Uso**:
```powershell
uv run python -m tools.kba_fermata "Library/deliverables/KBA_Merged_xxx.xlsx"
```

**STOP automatico** se Stefano's Notes ha righe vuote.

→ Guida completa: [[tools/kba/fermata/guida]]

---

## kba_meeting

**Tipo**: modulo Python con CLI
**Dipendenze principali**: `openpyxl`, `loguru`, `rich`, `tools.kba_reporter`, `tools.consulto`

Genera il documento per il meeting cliente da KBA con `{WIP}` in Stefano's Notes.
Chiama Grok con il prompt Dike (`Team/Prompts/kba/report-meeting.md`) e produce
un Markdown in italiano colloquiale.

**Uso**:
```powershell
uv run python -m tools.kba_meeting "Library/deliverables/KBA_Merged_xxx.xlsx"
uv run python -m tools.kba_meeting "Library/deliverables/KBA_Merged_xxx.xlsx" --provider gemini
```

**STOP automatico** se Stefano's Notes ha righe vuote.

→ Guida completa: [[tools/kba/meeting/guida]]

---

## handoff_register

**Tipo**: modulo Python con CLI
**Versione**: 0.1.0
**Dipendenze principali**: `pyyaml`, `loguru`, `rich`

Automatizza la gestione del sistema handoff del Team Olimpo: sposta i file con `stato: completato` da `Team/Handoff/` a `Team/Handoff/Archivio/` e rigenera dinamicamente il `Registro.md` con l'indice centralizzato.

**Comandi disponibili**:

| Comando | Descrizione breve |
|---------|-------------------|
| `sync` | Archivia i file completati + rigenera Registro (operazione completa) |
| `registro` | Solo rigenerazione Registro.md (read-only, no spostamenti) |
| `archivia` | Solo spostamento file completati (no rigenerazione Registro) |

**Flag globali**:

| Flag | Descrizione |
|------|-------------|
| `--verbose / -v` | Output debug dettagliato su stderr |

→ Guida completa: [[handoff-register-guida]]

---

## Standard CLI — Typer

Tutti i tool usano **Typer** come libreria CLI (non argparse). Il skeleton per nuovi tool è in `tools/_template/`:

```
tools/_template/
├── __init__.py    # __version__ = "0.1.0"
├── __main__.py    # entry point: app()
└── cli.py         # app = typer.Typer(); @app.command(); ...
```

Per creare un nuovo tool: copia `tools/_template/`, rinomina la cartella, implementa la logica in `cli.py`.

---

## Aggiungere uno strumento a questo indice

Quando Efesto crea un nuovo script o modulo, Clio aggiunge una riga a questa tabella e crea il file di guida dettagliata corrispondente in `Team/Meta/`.
