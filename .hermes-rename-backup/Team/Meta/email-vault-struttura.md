---
title: email_processor — Specifica struttura vault
tags: [meta, design, email]
status: done
tool_version: 0.4.0
---

# Specifica struttura vault email

> **Stato**: ✅ Implementato in `tools/email_processor/cli.py` (T-EMAIL-V2-001 + T-EMAIL-ATTACH-001), tool `v0.4.0`
> **Base**: `Team/Meta/email-processor-design.md`
> **Brainstorming**: 2026-05-19

---

## 1. Problema

La struttura attuale `Inbox/emails/YYYY/MM/` accumula centinaia di file nella stessa cartella. A maggio 2026 ci sono **849 file** in `2026/05/` — illeggibile per navigazione diretta, impossibile da esplorare senza cerca/testo.

Aggiunto: il body ripete `Da:`, `Data:`, `A:` già presenti nel frontmatter — triplicazione inutile.

---

## 2. Proposta: `YYYY/MM/DD/` con nome file snello

### Struttura

```
Inbox/emails/
├── 2026/
│   ├── 04/
│   │   ├── 01/
│   │   │   ├── fw-sms-automailer-nk-2600.md
│   │   │   └── ...
│   │   └── ...
│   └── 05/
│       └── 18/
│           ├── emerson-daily-digest.md
│           ├── mcafee-av-report.md
│           └── ...
├── attachments/
│   └── YYYY/MM/
│       └── allegato.pdf
```

### Naming file

```
{subject-slug-50}.md
```

- **Niente prefisso data** — la data è nel path e nel frontmatter
- Slug più lungo (50 char) per leggibilità
- Hash collisione solo se necessario (molto più raro con cartella giorno)

### Frontmatter

Invariato rispetto al design attuale:
```yaml
---
message_id: "<id>"
date: 2026-05-18
from: "Nome <email>"
to:
  - "Altro <email>"
cc: []
subject: "[EXTERNAL] Oggetto"
priority: normal
status: new
labels: []
attachments: []
source: "nomefile.eml"
---
```

### Corpo della nota — architettura a due fasi

La nota finale ha due "stati" che corrispondono a due fasi distinte del tool:

#### Fase 1 — `import` (deterministico, senza AI)

```
# [EXTERNAL] Oggetto

[full body text/plain raw]
```

- **Niente** `**Da:**`, `**Data:**`, `**A:**` — già nel frontmatter
- **Niente** `## Contenuto` — il body è già il contenuto
- Piatto, veloce, zero interpretazione

#### Fase 2 — `process` (AI, arricchimento)

Il comando `process` trasforma la nota in:

```
# [EXTERNAL] Oggetto

## In breve
[riassunto 2-3 righe — cosa c'è di nuovo in questa email,
per chi lavora in contesto Emerson: anche il minimo cambio
di stato rispetto alla precedente]

## Azioni / Decisioni
- [ ] Fare X (assegnato a: ...)
- [x] Fatto Y

## Nuovo contenuto
[porzione dell'email effettivamente nuova — esclude il
thread forwardato/risposte inline precedenti]

---
## Thread completo
[full body raw originale, identico a fase 1]
```

- `process` è idempotente: eseguirlo due volte dà lo stesso risultato
- `process` non tocca il frontmatter (se non per aggiornare `status: new → processed`)
- Il `## Thread completo` è **esattamente** il body della fase 1, preservato

### Gestione catene di reply (FW/Re)

Il problema principale del body raw: email forwardate/risposte in catena che accumulano tutto lo storico inline.

**Soluzione**: in fase `process`, l'AI identifica e isola il contenuto *nuovo* (sopra il primo separatore tipo `---Original Message---`, `From:`, `> `, o pattern di risposta). Il resto finisce in `## Thread completo`.

Niente deduplica spinta, niente link tra messaggi — solo separazione netta tra "cosa è nuovo" e "cosa è storico".

---

## 3. Vantaggi

- **Navigabilità**: apri un giorno e vedi solo le email di quel giorno (decine, non centinaia)
- **Nome file pulito**: niente date nel nome, slug più lungo e leggibile
- **Ridondanza eliminata**: data/mittente/destinatari non ripetuti nel body
- **Daily note naturale**: la cartella `18/` può contenere `18.md` come daily note
- **Collisioni rare**: due email con lo stesso subject lo stesso giorno sono rare

## 4. Svantaggi

- **Tante cartelle**: ~365/anno invece di 12. Visivamente più rumoroso in Obsidian
- **Vista mensile persa**: per vedere tutto maggio devi navigare 31 cartelle
- **Migrazione**: ~850 note esistenti da rinominare (o lasciare indietro)
- **Tool da modificare**: `_resolve_note_path()`, `_build_message_id_cache()`, generazione body

## 5. Cosa NON cambia

- Frontmatter (rimane identico)
- Deduplica via Message-ID
- Estrazione allegati
- Comandi CLI (`import`, `process`, `status`)
- Config (`tools/config.yaml`, env var)
- Vault separato (`vaults/email/`)

## 6. Decisioni chiuse

- ✅ **Giorno a 2 cifre**: `01`, `02`, `03` — sempre zero-padded
- ✅ **Migrazione**: nessuna — si cancella tutto e si riparte da zero con il nuovo formato
- ✅ **Body ridotto (import)**: niente `**Da:**`, `**Data:**`, `**A:**` — solo `# Oggetto` + body raw
- ✅ **Body arricchito (process)**: struttura con `## In breve`, `## Azioni / Decisioni`, `## Nuovo contenuto`, `## Thread completo`

## 7. Decisioni chiuse (secondo giro)

- ✅ **Slug length**: 60 caratteri
- ✅ **Trigger process**: manuale via CLI (comando `process`). Niente auto-esecuzione dopo import.
- ✅ **Labels/tags**: rimandato. L'import non li gestisce. `labels: []` in frontmatter, popolati in futuro.

## 8. Frontmatter dopo process — analisi

Dopo `process`, il corpo della nota si arricchisce di `## In breve`, `## Azioni / Decisioni`, `## Nuovo contenuto`, `## Thread completo`. Domanda: queste informazioni vanno **anche** nel frontmatter, o restano solo nel body?

### Opzione A — Solo nel body

```yaml
# frontmatter invariato (nessun campo nuovo)
---
message_id: "..."
date: 2026-05-18
subject: "..."
---
```

```
## In breve
Riassunto qui, in Markdown libero con [link](...) e **grassetto**.

## Azioni / Decisioni
- [ ] Fare X
- [x] Fatto Y
```

| Pro | Contro |
|---|---|
| Nessuna duplicazione | Non ricercabile via frontmatter (Dataview, grep strutturato) |
| Massima libertà di formattazione | Per estrarre azioni devi parsare il Markdown |
| Naturale da editare in Obsidian | |
| Body è la fonte unica | |

### Opzione B — Anche in frontmatter

```yaml
---
summary: "Riassunto 2-3 righe"
actions:
  - "Fare X"
  - "Fare Y"
decisions: []
action_count: 2
---
```

| Pro | Contro |
|---|---|
| Query strutturata (Dataview: tutte le email con azioni aperte) | Duplicazione col body (stessa info in due punti) |
| Scriptabile (es. estrai tutte le scadenze) | YAML non supporta Markdown (niente link, bold, liste) |
| Filtrabile nella UI Obsidian | Manutenzione doppia — se aggiorni il body devi aggiornare anche il frontmatter |

### Opzione C — Ibrido (solo metadati essenziali in frontmatter)

```yaml
---
summary: "Riassunto una riga"
action_count: 3
has_decisions: true
needs_reply: true
---
```

| Pro | Contro |
|---|---|
| Filtrabile senza duplicare tutto | Duplicazione parziale comunque presente |
| Scriptabile per alert e statistiche | Campo `summary` in YAML = niente formattazione |
| Il dettaglio resta nel body | |

### Consiglio

L'opzione A (solo body) è la più pulita **finché non c'è un caso d'uso concreto** che richieda query strutturate. Aggiungere campi al frontmatter dopo è sempre possibile — toglierli è più difficile.

Se in futuro servirà Dataview su "mostrami tutte le email con azioni aperte", si può sempre aggiungere `action_count:` al frontmatter in fase di `process`. Meglio partire minimali.

## 9. Decisioni chiuse (finali)

- ✅ **Slug 60 caratteri**: confermato. Troncamento a word boundary (taglia sull'ultimo `-` prima di 60).
- ✅ **Cancellazione note esistenti**: a carico dell'utente. Hermes non tocca.
- ✅ **Frontmatter**: rimane invariato (nessun campo summary/actions). Informazioni arricchite solo nel body.

## 10. Riepilogo finale — specifica consolidata

Tutte le decisioni del brainstorming sono chiuse. Riepilogo per implementazione futura:

| Area | Decisione |
|---|---|
| **Struttura directory** | `Inbox/emails/YYYY/MM/DD/nome-file.md` |
| **Giorno** | 2 cifre zero-padded (`01`, `02`…) |
| **Nome file** | `{subject-slug-60}.md` (senza prefisso data) |
| **Slug length** | 60 char, troncamento a ultimo `-` prima del limite |
| **Collisioni** | Hash MD5(6) → contatore progressivo (invariato) |
| **Frontmatter** | Invariato rispetto al design attuale |
| **Body import** | `# Oggetto` + body raw. Niente `**Da:**`, `**Data:**`, `**A:**`, niente `## Contenuto` |
| **Body process** | `## In breve` → `## Azioni / Decisioni` → `## Nuovo contenuto` → `---` → `## Thread completo` |
| **Trigger process** | Manuale via CLI |
| **Tags/labels** | `labels: []` vuoto, da definire in futuro |
| **Note esistenti** | Utente cancella prima del nuovo import |
| **Migrazione** | Nessuna — si ricomincia da zero |
