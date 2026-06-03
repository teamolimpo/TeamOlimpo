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
| **pdf_converter** | `tools/pdf_converter/` | Converte PDF in Markdown con estrazione immagini, post-processing e indicizzazione SQLite | Efesto | [[pdf-converter-guida]] |
| **llm** | `tools/llm/` | CLI per consulti rapidi a LLM di terze parti (xAI/Grok e Google/Gemini) | Efesto | [[tools/llm/guida]] |
| **handoff_register** | `tools/handoff_register/` | Archiviazione file handoff completati e rigenerazione indice Registro.md | Efesto | [[handoff-register-guida]] |

---

## llm

**Tipo**: modulo Python con CLI
**Versione**: 0.4.0
**Dipendenze principali**: `openai`, `google-genai`, `xai-sdk`, `python-dotenv`, `loguru`

Permette di interrogare LLM di terze parti (Grok e Gemini) da riga di comando per consulti rapidi, second opinion, elaborazioni batch e audit esterni. Output pipeable su stdout, errori su stderr.

**Modalità di utilizzo**:

| Modalità | Comando | Descrizione breve |
|----------|---------|-------------------|
| **Singola** | `uv run python -m tools.llm "prompt"` | Query singola su Grok |
| **Singola** | `uv run python -m tools.llm --provider gemini "prompt"` | Query su Gemini |
| **Singola** | `uv run python -m tools.llm --model <modello> "prompt"` | Override modello |
| **Singola** | `uv run python -m tools.llm --stdin < file.txt` | Legge prompt da file |
| **Singola** | `uv run python -m tools.llm -v "prompt"` | Output verbose (token ↑↓ separati, tempo, costo) |
| **Multi-agent** | `uv run python -m tools.llm --model grok-4.20-multi-agent-0309 --agent-count 4 "prompt"` | Multi-agent xAI (4 o 16 agenti) |
| **Models** | `uv run python -m tools.llm models` | Lista modelli disponibili e prezzi |
| **Models** | `uv run python -m tools.llm models --provider grok` | Lista modelli di un provider |
| **Batch** | `uv run python -m tools.llm --prompt template.md --input "docs/*.md" --output <dir>` | Elabora più file con template |
| **Interattivo** | `uv run python -m tools.llm` | Avvia il menu interattivo |
| **Interattivo** | `uv run python -m tools.llm -i` | Avvia il menu interattivo (esplicito) |

→ Guida completa: [[tools/llm/guida]]

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
