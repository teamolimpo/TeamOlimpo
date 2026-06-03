---
title: Mapping Vault Email — Architettura e Regole
tags: [meta, email, vault, addressbook]
aliases: [email vault, vault email, addressbook]
---

# Mapping Vault Email — Architettura e Regole

> **ℹ️ Nota**: il vault email ora è integrato nel vault principale (`lib/emails/`). Non ha niente a che fare con `Inbox/` (che è per documenti/PDF grezzi).

---

## 1. Architettura

Il vault email vive in `lib/emails/` (configurato via `EMAIL_VAULT_ROOT` in env var o `tools/config.yaml`).

```
PROJECT_ROOT/
├── lib/emails/                  ← EMAIL INTEGRATE nel vault principale
│   ├── Inbox/emails/               ← Note email .md (cronologico YYYY/MM/)
│   ├── Inbox/attachments/          ← Allegati email
│   ├── Addressbook/                    ← Rubrica contatti
│   ├── _review/                    ← Registry, agent-logs, stato elaborazione
│   │   ├── registry/
│   │   └── agent-logs/
│   ├── _templates/                 ← Template vault (daily.md, email.md)
│   └── .obsidian/                  ← Config Obsidian
│
├── tools/email_processor/          ← Tool Python per import/elaborazione
├── lib/                        ← VAULT PRINCIPALE Team Olimpo (NON toccato dalle email)
└── Inbox/                     ← Documenti/PDF in ingresso (NON email)
```

**Principio**: il vault email è integrato in `lib/emails/`. Le operazioni di import, elaborazione e catalogazione contatti avvengono tutte dentro `lib/emails/`.

---

## 2. Struttura del vault email

```
emails/
├── Inbox/
│   ├── emails/
│   │   ├── YYYY/
│   │   │   ├── MM/
│   │   │   │   ├── YYYY-MM-DD-oggetto-email.md
│   │   │   │   └── ...
│   │   │   └── ...
│   │   └── ...
│   └── attachments/
│       └── YYYY/
│           └── MM/
│               └── allegato.pdf
├── Addressbook/
│   ├── mario-rossi.md
│   ├── anna-bianchi.md
│   └── ...
├── _review/
│   ├── registry/
│   │   └── processing-state.json
│   └── agent-logs/
├── _templates/
│   ├── daily.md
│   └── email.md
└── .obsidian/
    └── ...
```

---

## 3. Regole di naming

### 3.1 Note email in `Inbox/emails/YYYY/MM/`

Formato: `{YYYY-MM-DD}-{subject-slug}.md`

| Esempio | Note |
|---|---|
| `2026-05-18-report-sicurezza.md` | Data + oggetto slugificato |
| `2026-05-18-external-mcafee-av-report-lonigo.md` | Con hash collisione (6 char) |
| `2026-05-18-unify-69d679-1.md` | Con contatore se hash collide |

Regole:
- Data in formato ISO (`YYYY-MM-DD`)
- Subject slugificato (lowercase, trattini, max ~120 char)
- Se collisione nomefile: aggiungi hash MD6, poi contatore

### 3.2 Schede contatto in `Addressbook/`

Formato: `{slug-nome}.md`

| Nome | File | Slug |
|---|---|---|
| Mario Rossi | `mario-rossi.md` | `mario-rossi` |
| Anna Bianchi | `anna-bianchi.md` | `anna-bianchi` |

Regole:
- Lowercase, spazi → trattini, caratteri speciali rimossi
- Slug = nome del file senza `.md`
- Niente spazi o punteggiatura nel filename

### 3.3 Allegati in `Inbox/attachments/YYYY/MM/`

Formato originale preservato. Path relativi nei wikilink delle note email.

---

## 4. Frontmatter

### 4.1 Note email

```yaml
---
date: "YYYY-MM-DD"
from: "Nome Mittente <email@dominio.com>"
to: "Destinatario <email@dominio.com>"
subject: "Oggetto email"
priority: media
tags: []
project:
source: nome-file.eml
---
```

### 4.2 Schede contatto (`Addressbook/`)

```yaml
---
title: Nome Cognome
tags: [cliente, partner, collega]
aliases: [nome.cognome@email.it]
email: nome.cognome@email.it
organizzazione: Nome Azienda
ruolo: Titolo Professionale
primo_contatto: 2024-01-15
ultimo_contatto: 2026-05-18
---
```

---

## 5. Flusso di elaborazione

```
.eml files                     tools/config.yaml
(/mnt/hgfs/Emails/inbox)       EMAIL_DIR/EMAIL_VAULT_ROOT
        │                              │
        ▼                              ▼
┌──────────────────────────────────────────────┐
│  tools/email_processor                       │
│                                              │
│  import    → Inbox/emails/YYYY/MM/note.md    │
│  elabora   → arricchimento AI (TODO)         │
│  status    → statistiche vault (TODO)        │
└──────────────────────────────────────────────┘
        │
        ▼
┌──────────────────────────────────────────────┐
│  Eunomia (subagent)                          │
│  - estrazione contatti da email importate    │
│  - deduplicazione contatti                   │
│  - creazione/aggiornamento schede Addressbook/   │
│  - report a Poros                           │
└──────────────────────────────────────────────┘
        │
        ▼
    emails/Inbox/emails/
    emails/Addressbook/
```

Passi:
1. **email_processor import** — legge `.eml` da `EMAIL_DIR`, crea note .md in `Inbox/emails/`
2. **Eunomia** (trigger manuale via Poros) — elabora le note email, estrae contatti, popola/aggiorna `Addressbook/`
3. **Archiviazione** — email processate spostate in `Archivio/` (o rimosse dopo conferma)

---

## 6. Configurazione

Due livelli di configurazione (priorità decrescente):

| Variabile | Default | Descrizione |
|---|---|---|
| `EMAIL_DIR` | `/mnt/hgfs/Emails/inbox` | Sorgente email .eml |
| `EMAIL_VAULT_ROOT` | `emails/` (relativo a PROJECT_ROOT) | Vault destinazione |

Oppure via `tools/config.yaml`:
```yaml
email_processor:
  email_dir: /mnt/hgfs/Emails/inbox
  vault_root: emails/
```

---

## 7. Relazione con il vault principale Team Olimpo

| Area | Vault email | Vault principale (lib/) |
|---|---|---|
| Scopo | Email, contatti, addressbook | Documenti tecnici, wiki, meta |
| Path | `emails/` | `lib/` |
| Contatti | `Addressbook/` | N/A |
| Email | `Inbox/emails/` | N/A |
| Tool | `tools/email_processor/` | Tutti gli altri tool |

**Nessun incrocio**. I due vault sono indipendenti. Eunomia opera solo nel vault email.

---

## 8. Roadmap

- [x] **Addressbook**: `Persone/` rinominato in `Addressbook/`
- [ ] **elabora**: implementare comando `email_processor elabora`
- [ ] **status**: implementare comando `email_processor status`
- [ ] **Pipeline Eunomia**: testare flusso completo import → contatti → report
- [ ] **Archivio**: definire politica di archiviazione dopo elaborazione
