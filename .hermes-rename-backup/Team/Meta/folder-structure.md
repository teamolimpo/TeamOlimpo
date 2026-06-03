---
title: "Folder Structure — Design & Conventions"
tags: [meta, design, folder-structure, conventions]
aliases: [folder-structure, struttura-cartelle]
---

# Folder Structure — Design & Conventions

> Design document per la struttura delle cartelle del repository Team Olimpo.
> Definisce cosa va dove, perché, e le regole per mantenerlo coerente.

---

## Indice

1. [Problema](#1-problema)
2. [Principi](#2-principi)
3. [Architettura](#3-architettura)
4. [Struttura Target](#4-struttura-target)
5. [Mappa delle Migrazioni](#5-mappa-delle-migrazioni)
6. [Regole](#6-regole)
7. [Storico Decisioni](#7-storico-decisioni)

---

## 1. Problema

### 1.1 Sintomi

- **`knowledge_search` restituisce path assoluti** — i risultati includono `/home/stra/lib/...` invece di `lib/...`
- **Repo clonati fuori workspace** — a volte finiscono in `/tmp/` invece che in una cartella dedicata
- **Confusione su dove mettere i file** — handoff, scratchpad, analisi, repo: tutto finito in `lib/Fucina/`
- **Link rotti** — documenti e tool referenziano `lib/Fucina/...` che è dentro un symlink

### 1.2 Root cause

Il repository ha due aree fondamentali:

| Area | Path reale | Descrizione |
|------|-----------|-------------|
| **Workspace** | `/home/stra/TeamOlimpo/` | Repository git principale |
| **Library** | `/home/stra/lib/` (symlink → `TeamOlimpo/Library`) | Dati privati, git separato, backup automatico |

`lib/Fucina/` è nato durante il repo split (maggio 2026) per ospitare file operativi (handoff, scratchpad, repo, analisi). Ma "Fucina" è un concetto operativo — non ha senso in una libreria/biblioteca. È un ossimoro.

Inoltre, il symlink causa problemi tecnici: quando i tool risolvono `lib/` col `.resolve()`, ottengono `/home/stra/lib/...` che non è sotto il project root, rompendo `relative_to()` e producendo path assoluti.

---

## 2. Principi

| # | Principio | Spiegazione |
|---|-----------|-------------|
| 1 | **Library = dati puri** | Wiki, documents, deliverables, assets — contenuti che hanno valore come archivio. Git separato, backup automatico. |
| 2 | **Team = operatività** | Codice, configurazione, SOPs, working file, output intermedi — tutto ciò che il team produce e consuma. Git principale. |
| 3 | **Fucina = working dir** | `Team/Fucina/` è lo spazio per file temporanei e lavori in corso. Gitignorato. |
| 4 | **Handoff tracciato** | Gli handoff hanno valore storico e arricchiscono ricerche future. Devono essere versionati. |
| 5 | **Path sempre relativi** | Nessun tool deve restituire o salvare path assoluti. Tutto è relativo al project root. |

---

## 3. Architettura

```
TeamOlimpo/                          ← git principale
│
├── Team/                            ← Operatività del team
│   ├── Handoff/                     ← Output agenti
│   ├── Hermes/                      ← Scratchpad, stato operativo
│   ├── Fucina/                      ← Working file temporanei, GITIGNORATO
│   │   ├── repos/                   ←   Repo clonati per analisi
│   │   ├── analyses/                ←   Note di analisi temporanee
│   │   └── KBA/                     ←   Working file KBA
│   ├── Members/                     ← Identità agenti
│   ├── Meta/                        ← Documentazione sistema
│   ├── Prompts/                     ← Prompt library
│   ├── SOPs/                        ← Procedure operative
│   └── Quarantine/                  ← Cose in sospeso
│
├── tools/                           ← Strumenti Python
├── .opencode/                       ← Config agenti
├── opencode.json                    ← Config OpenCode
├── AGENTS.md                        ← Questo file
│
├── Inbox/                           ← PDF in ingresso
│
└── lib/ → /home/stra/lib/   ← SYMLINK — dati privati (git separato)
    ├── Wiki/                        ← Knowledge wiki
    ├── documents/                   ← Documenti convertiti
    ├── deliverables/                ← Output finali per utente
    ├── data/                        ← DB, indici
    ├── assets/                      ← Immagini, media
    └── emails/                      ← Vault email
```

### Perché Handoff sta in `Team/` e non in `lib/`

- Gli handoff sono **output intermedi** di lavorazioni, non documenti finali
- Hanno **valore storico** → tracciati da git (eccezione dentro `Team/`)
- Sono **consultati dal team** durante le sessioni di lavoro, non consultati come archivio
- Una volta referenziati nel wiki perdono il path come dipendenza (si usa il frontmatter)

### Perché Fucina sta in `Team/` e non in `lib/`

- "Fucina" = forge, officina → concetto operativo
- Contiene **solo file temporanei** che vengono consumati e buttati
- **720M** di repo clonati + analisi non devono intasare la Library (che ha backup)
- Gitignorato → nessun rischio di commit accidentali

---

## 4. Struttura Target

### `Team/Handoff/`

```
Team/Handoff/
├── YYYY/
│   └── MM/
│       └── YYYY-MM-DD_HHMM_agent_type_slug.md
├── kba_batch/              ← Batch di analisi KBA (file .md/.json)
├── kba_batch2/             ← Secondo batch
├── Legacy/                 ← Handoff pre-standardizzazione
├── tucson/                 ← Progetto Tucson
├── scripts/                ← Script associati
├── templates/              ← Template handoff
└── Registro.md             ← Indice centralizzato (auto-generato)
```

> Nota: `kba_batch/`, `Legacy/`, `tucson/` sono fluttuazioni storiche. Al momento restano così; in futuro si può decidere di normalizzare.

### `Team/Fucina/`

```
Team/Fucina/
├── repos/                  ← Repo clonati per analisi
│   ├── oh-my-openagent/
│   ├── ruflo/
│   └── superpowers/
├── analyses/               ← Note di analisi temporanee
│   ├── chunk-retrieval-synthesis.md
│   ├── claude-context-chunker-analysis.md
│   ├── memvid-smartframes-analysis.md
│   └── openhuman-chunker-analysis.md
├── KBA/                    ← Working file KBA
│   ├── kba-flusso-umano.md
│   ├── kba-workflow.md
│   ├── kba-vecchi/
│   ├── prompts-kba/
│   └── tools-kba/
└── .gitkeep
```

### `Team/Hermes/`

```
Team/Hermes/
├── Scratchpad.md         ← Spazio di lavoro operativo
└── taskmanager state (obsolete)            ← Stato persistente (migrato da lib/Fucina/Hermes/)
```
```

---

## 5. Mappa delle Migrazioni

### 5.1 Path mapping

| Da | A | Tipo |
|----|---|------|
| `lib/Fucina/Handoff/` | `Team/Handoff/` | 📦 Spostamento fisico |
| `lib/Fucina/Hermes/` | `Team/Hermes/` | 📦 Spostamento fisico |
| `lib/Fucina/KBA/` | `Team/Fucina/KBA/` | 📦 Spostamento fisico |
| `lib/Fucina/repos/` | `Team/Fucina/repos/` | 📦 Spostamento fisico |
| `lib/Fucina/*.md` | `Team/Fucina/analyses/` | 📦 Spostamento fisico |
| `lib/Fucina/` | *(eliminata)* | 🗑️ Eliminazione |

### 5.2 Config changes

| File | Modifica |
|------|----------|
| `tools/config.yaml` → `handoff_root` | `lib/Fucina/Handoff` → `Team/Handoff` |
| `tools/config.yaml` → `search_paths` | `lib/Fucina/Handoff/` → `Team/Handoff/` |
| `.gitignore` | Aggiungere `Team/Fucina/` |
| `AGENTS.md` | Aggiornare sezione `## Folder Structure` + path Hermes output |

### 5.3 Tool changes

| Tool | Path da aggiornare |
|------|-------------------|
| `tools/handoff/server.py` | Commento/docstring (riga 124) |
| `tools/handoff/cli.py` | Commenti interni |
| `tools/handoff-register-guida.md` | Molteplici riferimenti `lib/Fucina/Handoff` → `Team/Handoff` |
| `tools/preflight_check/cli.py` | Se referenzia `lib/Fucina/` |
| `tools/kba_indexer/__init__.py` | `lib/Fucina/Handoff/kba_batch/` → `Team/Handoff/kba_batch/` |
| `tools/kba_reporter/cli.py` | Idem |
| `tools/extract_kba_excel.py` | Idem |

### 5.4 Documentation changes

Oltre a `AGENTS.md`, i seguenti file in `Team/` contengono riferimenti a `lib/Fucina/` e vanno aggiornati:

| File | Priorità |
|------|----------|
| `Team/Meta/handoff-register-guida.md` | Alta (23 refs) |
| `Team/Quarantine/Convenzioni-Scratchpad.md` | Alta (13 refs) |
| `Team/Meta/agent-template-bozza.md` | Media |
| `Team/Meta/opencode-permissions-spec.md` | Media |
| `Team/Meta/opencode-agents-guida.md` | Media |
| `Team/Meta/strumenti-indice.md` | Bassa |
| `Team/Meta/deviation-log-guida.md` | Bassa |
| `Team/Meta/adq-checklist.md` | Bassa |
| `Team/Meta/acm-report-template.md` | Bassa |
| `Team/Meta/automation_video_ia-guida.md` | Bassa |
| `Team/Meta/consulto-guida.md` | Bassa |
| `Team/Meta/tools/llm/guida.md` | Bassa |
| `Team/Meta/tools/handoff/guide.md` | Bassa |
| `Team/Prompts/_indice.md` | Bassa |
| `Team/Prompts/team/valutazione-ricerca.md` | Bassa |
| `Team/Prompts/team/valutazione-profilo.md` | Bassa |
| `Team/Quarantine/hot.md` | Bassa |
| `Team/Quarantine/preflight-checklist-hermes.md` | Bassa |
| `Team/Quarantine/2026-05-04_task-ricorrente-manutenzione-scratchpad.md` | Bassa |

---

## 6. Regole

### Regola 1: Path relativi sempre

Tutti i path nei documenti, tool, e output devono essere **relativi al project root** (`/home/stra/TeamOlimpo/`). Mai assoluti.

### Regola 2: Non creare Fucina in Library

`lib/Fucina/` non deve esistere. Se serve spazio per file operativi, usare `Team/Fucina/`.

### Regola 3: Repo clonati in Team/Fucina/repos/

Tutti i repository clonati per analisi vanno in `Team/Fucina/repos/`. Mai in `/tmp/` o altrove.

### Regola 4: Default = tracciato

Tutto in `Team/` è tracciato da git per default. Solo `Team/Fucina/` è esplicitamente gitignorato perché contiene file temporanei e repo clonati.

### Regola 5: Library solo dati puri

`lib/` contiene esclusivamente:
- `Wiki/` — conoscenza
- `documents/` — documenti convertiti  
- `deliverables/` — output finali
- `data/` — database e indici
- `assets/` — immagini e media
- `emails/` — vault email

Niente working file, niente repo, niente scratchpad.

---

## 7. Storico Decisioni

### ADR-001: Eliminazione di lib/Fucina/

**Data**: 2026-05-22
**Decisione**: Spostare tutto il contenuto di `lib/Fucina/` in `Team/Handoff/` e `Team/Fucina/`. Eliminare `lib/Fucina/`.
**Motivazione**: Fucina è concetto operativo, non da biblioteca. Il symlink causa path assoluti nei tool.
**Conseguenze**: 
- `Team/Handoff/` diventa tracciato da git
- `Team/Fucina/` nasce come area gitignorata per working file
- `tools/config.yaml` aggiornato con nuovo `handoff_root`
- Tutti i riferimenti a `lib/Fucina/` nei documenti vanno aggiornati

### Riferimenti storici

- Precedente repo split (2026-05): `Team/Handoff/` → `lib/Fucina/Handoff/` (ora invertito)
- Vedi `Team/Quarantine/prompt-fix-broken-refs.md` per lo storico della migrazione precedente
