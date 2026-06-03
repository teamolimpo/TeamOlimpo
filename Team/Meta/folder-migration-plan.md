---
title: "Folder Migration Plan — lib/Fucina/ → Team/"
tags: [meta, migration, folder-structure]
aliases: [folder-migration-plan, migration-plan]
---

# Folder Migration Plan — `lib/Fucina/` → `Team/`

> Piano di migrazione per spostare il contenuto di `lib/Fucina/`
> nelle nuove destinazioni in `Team/`.
>
> **Stato**: 📋 Pianificato (non eseguito)
> **Design doc**: `Team/Meta/folder-structure.md`
> **Checklist esecutiva**: sotto

---

## Fase 0 — Preparazione

### 0.1 Verifica stato iniziale

- [ ] `lib/Fucina/` esiste ed è raggiungibile via symlink
- [ ] `Team/Handoff/` NON esiste ancora
- [ ] `Team/Fucina/` NON esiste ancora
- [ ] `Team/Poros/` esiste già
- [ ] `.gitignore` non contiene `Team/Poros/` (rimosso — ora tracciato)
- [ ] `.gitignore` non contiene ancora `Team/Fucina/` (da aggiungere)

### 0.2 Backup

- [ ] `git status` pulito (nessuna modifica non committata)
- [ ] `git log --oneline -5` per riferimento
- [ ] `lib/Fucina/` è dentro il symlink → backup automatico del repo Library
- [ ] Opzionale: snapshot manuale di `lib/Fucina/Handoff/` (tar o cp -a)

---

## Fase 1 — Config & .gitignore

### 1.1 Aggiornare `.gitignore`

Rimuovere la riga `Team/Poros/` (ora deve essere tracciato). Aggiungere:

```gitignore
Team/Fucina/
```

**Attenzione**: `Team/Handoff/` e `Team/Poros/` NON vanno in .gitignore.

### 1.2 Aggiornare `tools/config.yaml`

| Chiave | Valore vecchio | Valore nuovo |
|--------|---------------|--------------|
| `handoff.handoff_root` | `lib/Fucina/Handoff` | `Team/Handoff` |
| `knowledge_base.search_paths[2]` | `lib/Fucina/Handoff/` | `Team/Handoff/` |

---

## Fase 2 — Creazione directory

- [ ] `mkdir -p Team/Handoff`
- [ ] `mkdir -p Team/Fucina/repos`
- [ ] `mkdir -p Team/Fucina/analyses`

---

## Fase 3 — Spostamento file (mv)

### 3.1 Handoff → `Team/Handoff/`

```bash
# Struttura principale YYYY/MM/
mv lib/Fucina/Handoff/2024   Team/Handoff/2024
mv lib/Fucina/Handoff/2026   Team/Handoff/2026

# Altri
mv lib/Fucina/Handoff/Legacy     Team/Handoff/Legacy
mv lib/Fucina/Handoff/tucson     Team/Handoff/tucson
mv lib/Fucina/Handoff/scripts    Team/Handoff/scripts
mv lib/Fucina/Handoff/templates  Team/Handoff/templates
mv lib/Fucina/Handoff/Registro.md Team/Handoff/Registro.md

# File sparsi nella root (se esistono)
```

- [ ] Verificare count: `find Team/Handoff -name '*.md' | wc -l` → deve dare 370

### 3.2 Poros → `Team/Poros/`

```bash
mv lib/Fucina/Poros/taskmanager state Team/Poros/taskmanager state
mv lib/Fucina/Poros/.taskmanager state.lock Team/Poros/.taskmanager state.lock
```

- [ ] `Team/Poros/` ora contiene `Scratchpad.md` + `taskmanager state` + lock file

### 3.4 Repo → `Team/Fucina/repos/`

```bash
mv lib/Fucina/repos/* Team/Fucina/repos/
```

- [ ] Verificare presenza di: `oh-my-openagent/`, `ruflo/`, `superpowers/`

### 3.5 Analyses → `Team/Fucina/analyses/`

```bash
mv lib/Fucina/*.md Team/Fucina/analyses/
```

- [ ] Verificare: `chunk-retrieval-synthesis.md`, `claude-context-chunker-analysis.md`, `memvid-smartframes-analysis.md`, `openhuman-chunker-analysis.md`

### 3.6 Pulizia

- [ ] `lib/Fucina/` dovrebbe essere vuota
- [ ] `rmdir lib/Fucina/Handoff` (se vuota)
- [ ] `rmdir lib/Fucina/Poros` (se vuota)
- [ ] `rmdir lib/Fucina/repos` (se vuota)
- [ ] `rmdir lib/Fucina` (se vuota)
- [ ] **NOTA**: `lib/Fucina/` è dentro il symlink → la directory viene eliminata sul target `/home/stra/lib/Fucina/`

---

## Fase 4 — Verifica link e riferimenti interni

### 4.1 Link tra handoff

Gli handoff possono referenziarsi tra loro. I path relativi dentro `lib/Fucina/Handoff/` cambiano in `Team/Handoff/`.

- [ ] `rg -l 'lib/Fucina/Handoff' Team/Handoff/` — mostra file che referenziano il vecchio path
- [ ] Per ogni match, valutare se aggiornare (i link interni tra handoff possono essere relativi)

### 4.2 Link da documenti

- [ ] `rg -l 'lib/Fucina/' lib/documents/` — eventuali link da documenti
- [ ] `rg -l 'lib/Fucina/' Library/deliverables/` — eventuali link da deliverables

> **Nota**: I documenti e deliverables potrebbero referenziare handoff specifici. Valutare se aggiornare o lasciare (i path in Library non sono più raggiungibili dopo la migrazione).

---

## Fase 5 — Aggiornamento documentazione

### 5.1 Documenti con molti riferimenti (alta priorità)

| File | Ref count | Azione |
|------|-----------|--------|
| `Team/Meta/handoff-register-guida.md` | 23 | Sostituzione massiva `lib/Fucina/Handoff` → `Team/Handoff` |
| `Team/Quarantine/Convenzioni-Scratchpad.md` | 13 | Sostituzione massiva |

Azione: `rg 'lib/Fucina/Handoff' --files-with-matches Team/Meta/handoff-register-guida.md Team/Quarantine/Convenzioni-Scratchpad.md`

### 5.2 Altri documenti

- [ ] `Team/Meta/agent-template-bozza.md` — 3 refs
- [ ] `Team/Meta/opencode-permissions-spec.md` — 2 refs
- [ ] `Team/Meta/opencode-agents-guida.md` — 2 refs
- [ ] `Team/Meta/strumenti-indice.md` — 1 ref
- [ ] `Team/Meta/deviation-log-guida.md` — 1 ref
- [ ] `Team/Meta/adq-checklist.md` — 1 ref
- [ ] `Team/Meta/acm-report-template.md` — 3 refs
- [ ] `Team/Meta/automation_video_ia-guida.md` — 3 refs
- [x] `Team/Meta/consulto-guida.md` → eliminato (rinominato in `tools/llm/guida.md`)
- [ ] `Team/Meta/tools/llm/guida.md` — 4 refs
- [ ] `Team/Meta/tools/handoff/guide.md` — 2 refs
- [ ] `Team/Prompts/_indice.md` — 4 refs
- [ ] `Team/Prompts/team/valutazione-ricerca.md` — 2 refs
- [ ] `Team/Prompts/team/valutazione-profilo.md` — 2 refs
- [ ] `Team/Quarantine/hot.md` — 1 ref
- [ ] `Team/Quarantine/preflight-checklist-poros.md` — 1 ref
- [ ] `Team/Quarantine/2026-05-04_task-ricorrente-manutenzione-scratchpad.md` — 8 refs

> **Strategia**: Sostituzione massiva con `sed` o `rg --replace` per `lib/Fucina/Handoff` → `Team/Handoff`. Pochi casi hanno `lib/Fucina/` senza `Handoff` (es. riferimenti a `lib/Fucina/Poros/`) — questi vanno uno per uno.

---

## Fase 6 — Aggiornamento tool Python

### 6.1 Path in config (già aggiornato in Fase 1.2)

- [ ] `tools/config.yaml` → `handoff_root: Team/Handoff`

### 6.2 Path in docstring e commenti

- [ ] `tools/handoff/server.py` — riga ~124: docstring del tool `handoff_create`
- [ ] `tools/handoff/cli.py` — commenti e help text

- [ ] `tools/preflight_check/cli.py` — path handoff
- [ ] `tools/taskmanager/state.py` — se referenzia lib/Fucina
- [ ] `tools/taskmanager/migration.py` — se referenzia lib/Fucina

> **Nota**: Solo docstring e commenti. La logica dei tool Python usa `config.yaml` per i path, quindi non dovrebbe essere necessario modificarne la logica.

---

## Fase 7 — Test & verifica finale

### 7.1 Test handoff tool

- [ ] `uv run python -m tools.handoff main --help` — funziona
- [ ] Creare handoff di test → finisce in `Team/Handoff/YYYY/MM/`
- [ ] `handoff_list` mostra path corretti

### 7.2 Test knowledge_search

- [ ] `knowledge_search(query="test", scope="all")` include `Team/Handoff/` nei risultati
- [ ] Path restituiti sono relativi

### 7.3 Git status

- [ ] `git status` mostra:
  - `Team/Handoff/` → nuovi file tracciati
  - `Team/Fucina/` → ignorato
  - `Team/Poros/` → tracciato (se ci sono modifiche)
  - `lib/Fucina/` → non più presente (nel symlink, non in git)
- [ ] `git add Team/Handoff/` e commit

### 7.4 Smoke test

- [ ] Chiedere a Poros: "mostrami la struttura delle cartelle" → path corretti
- [ ] Generare un handoff fittizio → percorso corretto
- [ ] Cercare un handoff con knowledge_search → risultato con path relativo

---

## Riepilogo tempi stimati

| Fase | Durata | Dipende da |
|------|--------|-----------|
| Fase 0 — Preparazione | 10 min | — |
| Fase 1 — Config & .gitignore | 5 min | Fase 0 |
| Fase 2 — Creazione directory | 5 min | Fase 0 |
| Fase 3 — Spostamento file | 15 min | Fase 2 |
| Fase 4 — Verifica link | 20 min | Fase 3 |
| Fase 5 — Documentazione | 30 min | Fase 3 |
| Fase 6 — Tool Python | 15 min | Fase 3 |
| Fase 7 — Test & verifica | 20 min | Fase 1-6 |
| **Totale** | **~2 ore** | |

---

> **Nota**: Questo piano è solo documentazione. Non eseguire senza approvazione dell'utente.
> Vedi `Team/Meta/folder-structure.md` per il design che motiva queste scelte.
