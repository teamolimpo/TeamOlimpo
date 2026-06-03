---
title: email_processor — Design di import
tags: [meta, design, email, tool]
---

# email_processor — Design del comando `import`

> Documento di riferimento per l'implementazione. Rilascia in `Library/tools/email_processor/`.

---

## 1. Scopo

Legge file `.eml` da una directory sorgente, li parsizza e produce note Markdown nel vault email (`vaults/email/`). Operazione deterministica in Python — niente AI, niente link ad addressbook.

---

## 2. Input

| Parametro | Fonte | Default |
|---|---|---|
| Directory sorgente `.eml` | `EMAIL_DIR` env var → `tools/config.yaml` | `/mnt/hgfs/Emails/inbox` |
| Vault destinazione | `EMAIL_VAULT_ROOT` env var → `tools/config.yaml` | `vaults/email/` |
| `--limit N` | CLI flag | nessuno (tutti) |
| `--verbose` | CLI flag | False |

---

## 3. Output

### 3.1 Struttura directory

```
vaults/email/
├── Inbox/emails/YYYY/MM/
│   ├── YYYY-MM-DD-slug-30caratteri.md
│   └── ...
├── Inbox/attachments/YYYY/MM/
│   ├── allegato1.pdf
│   └── allegato2.docx
└── ...
```

- `Inbox/emails/YYYY/MM/` — note email, organizzazione cronologica
- `Inbox/attachments/YYYY/MM/` — allegati estratti, stessa struttura data

### 3.2 Naming file note email

```
{YYYY-MM-DD}-{subject-slug-30}.md
```

- **Data**: `YYYY-MM-DD` dalla data dell'email (ISO normalizzata)
- **Subject slug**: lowercase, trattini, caratteri non alfanumerici rimossi
- **Max lunghezza slug**: **30 caratteri** (troncato a word boundary se possibile)
- **Collisioni**: se file esiste già → aggiunge hash MD6 del subject (6 char) → se ancora collisione → contatore progressivo

Esempi:

| Subject | Nome file |
|---|---|
| `Report sicurezza Q1` | `2026-05-18-report-sicurezza-q1.md` |
| `External McAfee AV Report Lonigo` | `2026-05-18-external-mcafee-av-report.md` |
| `Fwd: Re: Fwd: Important notification about your account` | `2026-05-18-fwd-re-fwd-important-notific.md` |
| (collisione) | `2026-05-18-fwd-re-fwd-important-notific-3f8a2c.md` |
| (doppia collisione) | `2026-05-18-fwd-re-fwd-important-notific-3f8a2c-1.md` |

### 3.3 Naming allegati

Il nome originale dell'allegato è preservato. Se collisione nel path di destinazione, si antepone un timestamp `{YYYYMMDD_HHMMSS}_` al nome.

### 3.4 Cartelle cronologiche

Le cartelle `YYYY/MM/` vengono create automaticamente in base alla data dell'email. Se la data non è parsabile, si usa `unknown/unknown/`.

---

## 4. Frontmatter della nota email

```yaml
---
message_id: "<abc123@domain.com>"
date: 2026-05-18
from: "Mario Rossi <m.rossi@domain.com>"
to:
  - "Anna Bianchi <a.bianchi@domain.com>"
cc:
  - "Luigi Verdi <l.verdi@domain.com>"
subject: "Report sicurezza Q1"
priority: normal
status: new
labels: []
attachments:
  - name: report-q1.pdf
    path: Inbox/attachments/2026/05/report-q1.pdf
    size: 245760
source: 20260518_090000_report.eml
---
```

### 4.1 Campi

| Campo | Tipo | Obbligatorio | Note |
|---|---|---|---|
| `message_id` | string | sì | Header Message-ID. Per deduplica. |
| `date` | string (ISO) | sì | `YYYY-MM-DD`. Normalizzata da dateutil. |
| `from` | string | sì | `"Nome <email>"` o solo email se nome assente. |
| `to` | list[string] | sì | Lista destinatari. Formato stesso di `from`. |
| `cc` | list[string] | no | Lista CC. Default `[]`. |
| `subject` | string | sì | Oggetto email. |
| `priority` | string | sì | `low \| normal \| high`. Default `normal`. |
| `status` | string | sì | `new \| processed \| flagged`. Default `new`. |
| `labels` | list[string] | no | Tags Gmail-style. Vuoto all'import. |
| `attachments` | list[object] | no | Lista allegati con `name`, `path`, `size`. |
| `source` | string | sì | Nome del file .eml originale. |

### 4.2 Stati (valori permessi)

`status` segue questo ciclo di vita:

```
new → (import)          stato iniziale
new → processed         dopo process
new → flagged           manuale o se priority=high
```

Valori: `new`, `processed`, `flagged`

### 4.3 Priorità (valori permessi)

`priority`: `low`, `normal`, `high`

All'import è sempre `normal`. Il cambiamento avviene in `process` o manualmente.

---

## 5. Comportamento import

### 5.1 Parsing .eml

Cosa estrarre dagli header:

| Header | Campo frontmatter | Note |
|---|---|---|
| `Message-ID` | `message_id` | Pulisci `<>` |
| `Date` | `date` | Parsa con dateutil → `YYYY-MM-DD`. |
| `From` | `from` | Decodifica header, formato `"Nome <email>"` |
| `To` | `to` | Lista, stesso formato |
| `CC` | `cc` | Lista, stesso formato. Default `[]` |
| `Subject` | `subject` | Decodifica header |
| `References`, `In-Reply-To` | (non in frontmatter) | Per deduplica thread |

Cosa estrarre dal body:
- Solo `text/plain` (primo part disponibile)
- Niente HTML, niente processing

### 5.2 Deduplica

Prima di creare una nuova nota, controllare:

1. Esiste già un file in `Inbox/emails/**/*.md` con `message_id:` corrispondente?
   - Se sì → **SKIP** (logga `Skipping {file}: already imported`)
   - Se no → importa

Implementazione: cerca il `message_id` nel frontmatter delle note già esistenti.
Per performance, si può mantenere un indice veloce in `_review/registry/`.

### 5.3 Estrazione allegati

Per ogni part del .eml con `Content-Disposition: attachment`:
1. Leggi nome file originale dall'header
2. Determina path: `Inbox/attachments/{YYYY}/{MM}/{nome-file}`
3. Crea directory se non esiste
4. Salva il binario
5. Aggiungi alla lista `attachments` nel frontmatter

Se il nome file esiste già: anteponi `{YYYYMMDD_HHMMSS}_`.

### 5.4 Contatti (raw)

Niente link ad addressbook. `from`, `to`, `cc` contengono stringhe raw decodificate nel formato `"Nome <email>"`.

L'arricchimento con link ad Addressbook/ è compito di `process` (o Eunomia).

---

## 6. Comportamento CLI

```bash
# Importa tutte le email
python -m tools.email_processor import

# Importa al massimo 5 email
python -m tools.email_processor import --limit 5

# Importa da directory specifica (sovrascrive EMAIL_DIR)
python -m tools.email_processor import --email-dir /tmp/emails
```

### Flag

| Flag | Tipo | Default | Descrizione |
|---|---|---|---|
| `--limit` / `-l` | int | `None` | Max email da importare (file più recenti prima) |
| `--email-dir` | Path | `None` | Sorgente .eml (override di `EMAIL_DIR`) |
| `--verbose` / `-v` | bool | `False` | Log DEBUG su stderr |

Ordine di elaborazione: file .eml ordinati per `mtime` decrescente (più recenti prima).

---

## 7. Cosa NON fa import

- ❌ Link ad Addressbook/ (lo fa `process` o Eunomia)
- ❌ Classificazione AI
- ❌ Sintesi del corpo
- ❌ Estrazione azioni/task
- ❌ Modifica di file esistenti
- ❌ Cancellazione di file
- ❌ Elaborazione .msg (solo .eml)

---

## 8. Casi d'angolo

| Situazione | Comportamento |
|---|---|
| `EMAIL_DIR` non esiste | Errore con messaggio chiaro → exit code 1 |
| `.eml` malformato | Salta, logga errore, continua |
| Data non parsabile | Usa `unknown` per la cartella |
| File .eml inaccessibile (permessi) | Salta, logga warning |
| Allegato con nome vuoto | Usa `attachment-{n}.bin` |
| Stesso `message_id` già importato | SKIP silenzioso |
| Path allegato troppo lungo | Tronca il nome file a 100 char |

---

## 9. Dipendenze Python

Esistenti (già in uso):
- `typer` — CLI
- `loguru` — logging
- `python-dateutil` — parsing date
- `pyyaml` — config
- `email` (standard lib) — parsing .eml
- `hashlib` (standard lib) — hash collisioni

Non servono nuove dipendenze.
