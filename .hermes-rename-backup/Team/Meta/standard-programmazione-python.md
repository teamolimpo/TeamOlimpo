---
title: Standard di Programmazione Python nel Team Olimpo
tags: [meta, python, standards, team]
aliases: [standard python, programmazione python]
---

# Standard di Programmazione Python nel Team Olimpo

Questo documento definisce gli standard di programmazione Python adottati dal Team Olimpo. L'obiettivo è garantire codice di qualità, manutenibile e efficiente, utilizzando tool moderni per la gestione delle dipendenze e l'esecuzione di script.

## Scelta di uv come Tool Principale

### Motivazioni

Il Team Olimpo adotta **uv** come strumento principale per la gestione delle dipendenze e l'esecuzione di script Python, sostituendo pip tradizionale. Le ragioni principali sono:

- **Velocità**: uv è significativamente più veloce di pip nelle operazioni di installazione e risoluzione dipendenze, grazie a un resolver avanzato e caching intelligente.
- **Gestione Dipendenze Moderna**: Supporta nativamente `pyproject.toml` (standard PEP 621), eliminando la necessità di `requirements.txt` in molti casi.
- **Isolamento Ambiente**: Crea ambienti virtuali automaticamente senza intervento manuale, riducendo errori di configurazione.
- **Semplicità**: Un singolo comando per installare, eseguire e gestire progetti, riducendo la complessità dei workflow.
- **Compatibilità**: Compatibile con l'ecosistema Python esistente, ma ottimizzato per pratiche moderne.

Confronto rapido:
- **pip**: Lento, richiede virtualenv manuale, usa `requirements.txt`.
- **uv**: Veloce, automatico, usa `pyproject.toml`, include esecuzione diretta.

### Installazione di uv

Installa uv globalmente (una volta sola):

```bash
curl -LsSf https://astral.sh/uv/install.sh | sh
```

Verifica l'installazione:

```bash
uv --version
```

## Gestione Dipendenze con uv

### Creazione di un Nuovo Progetto

Per iniziare un nuovo progetto Python:

```bash
uv init mio-progetto
cd mio-progetto
```

Questo crea una struttura base con `pyproject.toml`, `src/` e `.python-version`.

### Aggiungere Dipendenze

Aggiungi dipendenze al progetto:

```bash
uv add requests loguru
```

Per dipendenze di sviluppo (es. pytest, ruff):

```bash
uv add --dev pytest ruff
```

> **Policy progetto**: Questo progetto usa esclusivamente `uv` per la gestione delle dipendenze. Non utilizzare `pip install` direttamente.

Il file `pyproject.toml` viene aggiornato automaticamente. Esempio di struttura:

```toml
[project]
name = "mio-progetto"
version = "0.1.0"
dependencies = [
    "requests",
    "loguru",
]

[tool.uv]
dev-dependencies = [
    "pytest",
    "ruff",
]
```

### Installazione Dipendenze

Installa tutte le dipendenze definite:

```bash
uv sync
```

Questo crea un ambiente virtuale isolato in `.venv/` e installa tutto.

## Esecuzione Script e Tool con uv run

`uv run` permette di eseguire script o comandi senza attivare manualmente l'ambiente virtuale. È ideale per automazioni e script standalone.

### Esempi Pratici

Esegui uno script Python:

```bash
uv run python mio_script.py
```

Esegui test con pytest:

```bash
uv run pytest
```

Esegui linting con ruff:

```bash
uv run ruff check .
uv run ruff format .
```

Per script che richiedono dipendenze specifiche, definiscile in `pyproject.toml` e usa `uv run`:

```python
# mio_script.py
import requests
import loguru

loguru.logger.info("Script in esecuzione")
response = requests.get("https://api.example.com")
print(response.json())
```

Esegui con:

```bash
uv run python mio_script.py
```

### Creazione di un Progetto Esempio

1. Crea progetto:

   ```bash
   uv init esempio-team-olimpo
   cd esempio-team-olimpo
   ```

2. Aggiungi dipendenze comuni per automazioni:

   ```bash
   uv add pydantic loguru typer
   uv add --dev pytest ruff mypy
   ```

3. Sincronizza:

   ```bash
   uv sync
   ```

4. Crea uno script di esempio in `src/main.py`:

   ```python
   # src/main.py
   """Script di esempio per il Team Olimpo."""

   from typing import List
   import typer
   import loguru
   from pydantic import BaseModel

   class Task(BaseModel):
       name: str
       status: str = "pending"

   app = typer.Typer()

   @app.command()
   def list_tasks(tasks: List[str] = typer.Option([], "--task", help="Lista di task")):
       """Elenca i task forniti."""
       loguru.logger.info("Elenco task richiesti")
       for task in tasks:
           print(f"- {task}")

   if __name__ == "__main__":
       app()
   ```

5. Esegui lo script:

   ```bash
   uv run python src/main.py --task "analisi dati" "generazione report"
   ```

6. Esegui test (aggiungi test in `tests/`):

   ```bash
   uv run pytest
   ```

## Integrazione nei Workflow Esistenti

### Migrazione da pip a uv

Per progetti esistenti con `requirements.txt`:

1. Crea `pyproject.toml` con dipendenze:

   ```toml
   [project]
   name = "progetto-esistente"
   dependencies = [
       "requests",  # copia da requirements.txt
       "loguru",
   ]
   ```

2. Rimuovi `requirements.txt` e usa `uv sync` invece di `pip install -r requirements.txt`.

3. Sostituisci `python script.py` con `uv run python script.py`.

### Integrazione con Automazioni

Nei workflow del Team Olimpo:

- Per script operativi (es. conversione PDF, manipolazione dati), usa `uv run` per garantire isolamento.
- Documenta dipendenze in `pyproject.toml` per riproducibilità.
- Per tool CLI come quelli in `tools/`, considera migrare a uv per esecuzione.

Esempio di integrazione in uno script bash:

```bash
#!/bin/bash
# Esegui script Python con uv
uv run python tools/pdf_converter/cli.py --input file.pdf
```

### Best Practices

- **Idempotenza**: Gli script dovrebbero essere sicuri da rieseguire.
- **Logging**: Usa `loguru` invece di `print()`.
- **Type Hints e Docstring**: Sempre presenti.
- **Error Handling**: Gestisci eccezioni con try/except specifici.
- **Configurazione Esterna**: Usa file di config o variabili d'ambiente, non hardcoded.

## Conclusioni

Adottando uv, il Team Olimpo migliora l'efficienza e la manutenibilità del codice Python. Questi standard assicurano workflow coerenti e moderni, facilitando la collaborazione e l'automazione.

Per aggiornamenti o domande, consulta [[Team/Members/Efesto]] o apri una discussione nel team.