---
title: "pdf_converter — Guida d'uso"
aliases: [pdf converter, conversione pdf, pdf_converter]
tags: [meta, strumenti, pdf, conversione, guida]
---

# pdf_converter — Guida completa

## Cos'è

`pdf_converter` è il modulo Python del Team Olimpo che automatizza la conversione di file PDF in documenti Markdown compatibili con il vault Obsidian della Library.

**Percorso nel repository**: `tools/pdf_converter/`
**Versione**: 0.1.0
**Responsabile**: Efesto

### Cosa produce

Data in input un PDF, il converter produce:
- Un file **Markdown** in `lib/documents/<slug>.md` con frontmatter YAML e contenuto del documento
- Una cartella **immagini** in `lib/assets/images/<slug>/` con tutte le immagini estratte dal PDF
- Un **record** nel database SQLite `lib/data/pdf_index.db` con metadati e stato della conversione

Il Markdown prodotto è compatibile con Obsidian: le immagini usano path relativi al file `.md`, il frontmatter rispetta lo schema del vault.

---

## Prerequisiti

### Dipendenze Python

```
pymupdf          → lettura PDF e estrazione metadati
pymupdf4llm      → conversione PDF → Markdown con immagini
pydantic         → validazione modelli dati
loguru           → logging strutturato
rich             → output CLI formattato
pyyaml           → generazione frontmatter YAML
```

Installazione ([[standard-programmazione-python]]):
```powershell
uv add pymupdf pymupdf4llm pydantic loguru rich pyyaml
```
> **Nota**: Se il progetto usa `pyproject.toml`, `uv add` aggiorna automaticamente le dipendenze.
> **Policy progetto**: Questo progetto usa esclusivamente `uv` per la gestione delle dipendenze. Non utilizzare `pip install` direttamente.

### Ambiente

- **Directory di lavoro**: deve essere la root del progetto (`TeamOlimpo/`)
- **Python**: 3.10+
- **OS**: Windows, macOS, Linux

---

## Come si usa

Tutti i comandi si eseguono dalla root del progetto con:

```powershell
uv run python -m tools.pdf_converter <COMANDO> [opzioni]
```

Flag globale disponibile su tutti i comandi:
```powershell
--verbose / -v    → mostra output di debug dettagliato
```

---

### `init` — Inizializzazione

Crea le cartelle necessarie e inizializza il database SQLite. Da eseguire **una sola volta** alla prima installazione.

```powershell
uv run python -m tools.pdf_converter init
```

**Cosa crea**:
- `Inbox/` — cartella dove depositare i PDF da convertire
- `lib/documents/` — output Markdown
- `lib/assets/images/` — output immagini
- `lib/data/pdf_index.db` — database SQLite

L'operazione è idempotente: eseguirla di nuovo non sovrascrive nulla.

---

### `convert` — Conversione singolo PDF

Converte un file PDF specifico.

```powershell
uv run python -m tools.pdf_converter convert "Inbox/documento.pdf"
uv run python -m tools.pdf_converter convert "Inbox/documento.pdf" --force
```

**Parametri**:

| Parametro | Obbligatorio | Descrizione |
|-----------|:---:|-------------|
| `PDF` | sì | Path al file PDF (relativo alla root del progetto o assoluto) |
| `--force` / `-f` | no | Riconverte anche se il documento è già nel database |

**Comportamento**:
- Se il PDF è già stato convertito (presente nel DB con status `completed`), il comando lo **salta** e avvisa. Usare `--force` per riconvertire.
- Se il PDF aveva un errore precedente (status `error`), viene ritentato automaticamente senza `--force`.

**Output**:
```
Conversione: documento.pdf
Completato: lib/documents/documento.md (3 immagini, 1.24s)
```

---

### `convert-all` — Conversione batch

Converte tutti i PDF presenti in `Inbox/` che non sono ancora stati convertiti.

```powershell
uv run python -m tools.pdf_converter convert-all
uv run python -m tools.pdf_converter convert-all --force
```

**Parametri**:

| Parametro | Obbligatorio | Descrizione |
|-----------|:---:|-------------|
| `--force` / `-f` | no | Riconverte tutti i PDF, anche quelli già nel database |

**Comportamento**:
- Scansiona `Inbox/*.pdf` (non ricorsivo)
- Salta automaticamente i PDF già convertiti con successo
- Mostra una progress bar durante l'elaborazione
- Al termine mostra il riepilogo: completati / errori

**Output esempio**:
```
PDF da convertire: 3 (saltati già presenti: 2)
[████████████████████] 3/3  nk-2400-0160.pdf
Riepilogo conversione:
  Completati:  3
  Errori:      0
```

---

### `search` — Ricerca full-text

Cerca nei documenti indicizzati usando SQLite FTS5.

```powershell
uv run python -m tools.pdf_converter search "DeltaV security"
uv run python -m tools.pdf_converter search "recovery media" --limit 5
```

**Parametri**:

| Parametro | Obbligatorio | Default | Descrizione |
|-----------|:---:|---------|-------------|
| `QUERY` | sì | — | Testo da cercare |
| `--limit` / `-n` | no | 20 | Numero massimo di risultati |

**Sintassi FTS5 supportata**:

| Operatore | Esempio | Significato |
|-----------|---------|-------------|
| AND (implicito) | `security update` | Entrambi i termini presenti |
| `AND` esplicito | `security AND update` | Entrambi i termini |
| `OR` | `security OR vulnerability` | Almeno uno dei termini |
| `NOT` | `security NOT patch` | security senza patch |
| `*` (prefisso) | `vuln*` | Termini che iniziano con "vuln" |
| `"..."` (frase) | `"recovery media"` | Frase esatta |

**Campi cercati**: filename, title, author, tags, category, notes

---

### `list` — Elenco documenti

Mostra la lista dei documenti indicizzati nel database.

```powershell
uv run python -m tools.pdf_converter list
uv run python -m tools.pdf_converter list --limit 10
uv run python -m tools.pdf_converter list --sort filename --asc
uv run python -m tools.pdf_converter list --status error
```

**Parametri**:

| Parametro | Default | Descrizione |
|-----------|---------|-------------|
| `--limit` / `-n` | 50 | Numero massimo di documenti |
| `--sort` | `converted_at` | Campo di ordinamento: `converted_at`, `filename`, `num_pages`, `file_size_bytes`, `title` |
| `--asc` | no (decrescente) | Ordinamento crescente |
| `--status` | tutti | Filtra per stato: `completed` oppure `error` |

---

### `stats` — Statistiche

Mostra statistiche aggregate su tutti i documenti nel database.

```powershell
uv run python -m tools.pdf_converter stats
```

**Output**:

| Metrica | Descrizione |
|---------|-------------|
| Documenti totali | Numero totale di PDF processati |
| Completati | Conversioni riuscite |
| Errori | Conversioni fallite |
| Pagine totali | Somma di tutte le pagine |
| Immagini totali | Immagini estratte da tutti i documenti |
| Tempo medio (s) | Tempo medio di elaborazione per documento |
| Dimensione totale PDF (MB) | Dimensione cumulativa dei PDF originali |

---

## Pipeline interna

Quando si esegue una conversione, il tool segue questa pipeline:

```
PDF input
   ↓
[1] extract_metadata()     → legge titolo, autore, pagine con PyMuPDF
   ↓
[2] convert_pdf()          → converte in Markdown con pymupdf4llm
                             estrae e salva le immagini in assets/images/<slug>/
   ↓
[3] post_process()         → pulizia del Markdown grezzo:
                             • rimuove numeri di pagina isolati
                             • collassa righe vuote eccessive
                             • normalizza gerarchia heading
                             • corregge path immagini (assoluti e CWD-relativi → relativi al file)
                             • aggiunge frontmatter YAML
   ↓
[4] index_document()       → inserisce o aggiorna il record nel database SQLite
   ↓
Markdown output in lib/documents/<slug>.md
```

---

## Output Markdown — Struttura

Ogni file `.md` prodotto ha questa struttura:

```markdown
---
title: Titolo del documento
source_pdf: nome-originale.pdf
converted_at: '2026-03-25 11:42:58'
num_pages: 10
author: Nome Autore
num_images: 3
---

# Contenuto del documento...

![](../assets/images/slug/nome-immagine.png)

...
```

### Path immagini

Il post-processor converte automaticamente tutti i path immagini in path **relativi al file `.md`**:
- Da path assoluto: `C:\Users\dev\...\assets\images\slug\img.png`
- Da path CWD-relativo: `lib/assets/images/slug/img.png`
- A path relativo: `../assets/images/slug/img.png` ✓

---

## Database SQLite

Il file `lib/data/pdf_index.db` contiene la tabella `documents` con:

| Campo | Tipo | Descrizione |
|-------|------|-------------|
| `filename` | TEXT | Nome del file PDF originale |
| `slug` | TEXT UNIQUE | Slug normalizzato (chiave logica) |
| `pdf_path` | TEXT | Path relativo al PDF sorgente |
| `md_path` | TEXT | Path relativo al Markdown generato |
| `images_dir` | TEXT | Path relativo alla cartella immagini |
| `title` | TEXT | Titolo dai metadati PDF |
| `author` | TEXT | Autore dai metadati PDF |
| `num_pages` | INTEGER | Numero di pagine |
| `num_images` | INTEGER | Immagini estratte |
| `status` | TEXT | `completed`, `error`, `skipped` |
| `converted_at` | TEXT | Timestamp ISO 8601 |
| `tags` | TEXT | Tag assegnabili manualmente |
| `category` | TEXT | Categoria assegnabile manualmente |
| `notes` | TEXT | Note libere |

La tabella ha un indice FTS5 (`documents_fts`) per la ricerca full-text, sincronizzato automaticamente tramite trigger.

---

## Log

Il converter scrive un log rotante in `lib/data/pdf_converter.log`:
- Rotazione: ogni 5 MB
- Retention: 30 giorni
- Livello: DEBUG (tutto viene registrato nel file)

Per vedere i log in tempo reale durante una conversione:
```powershell
uv run python -m tools.pdf_converter convert-all --verbose
```

---

## Troubleshooting

### Il PDF viene saltato anche con `--force`

Verificare che il file esista nel path specificato. Il flag `--force` bypassa il controllo del database ma non crea il file.

### Immagini non visibili in Obsidian

Verificare che il path nel `.md` sia relativo e corretto:
```
# Corretto
![](../assets/images/slug/immagine.png)

# Rotto — path assoluto
![](C:/Users/dev/.../immagine.png)

# Rotto — path CWD-relativo
![](lib/assets/images/slug/immagine.png)
```

Se il file è già stato convertito e il path è sbagliato, riconvertire con `--force`.

### Errore "pymupdf4llm non è installato"

```powershell
uv add pymupdf4llm
```
> **Nota**: Vedi [[standard-programmazione-python]] per la gestione delle dipendenze con uv.

### Il database non viene trovato

Eseguire `uv run python -m tools.pdf_converter init` dalla root del progetto.

---

## Moduli interni

| Modulo | File | Responsabilità |
|--------|------|----------------|
| `cli` | `cli.py` | Entry point CLI, parsing argomenti, comandi |
| `converter` | `converter.py` | Estrazione metadati e conversione PDF→Markdown |
| `post_processor` | `post_processor.py` | Pulizia Markdown, fix path immagini, frontmatter |
| `indexer` | `indexer.py` | Database SQLite, FTS5, CRUD documenti |
| `models` | `models.py` | Modelli Pydantic (DocumentMetadata, ConversionResult) |
| `config` | `config.py` | Configurazione centralizzata path e parametri |
| `utils` | `utils.py` | Funzioni utility (slugify, path, conteggio file) |
