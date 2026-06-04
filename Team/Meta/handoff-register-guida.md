---
title: "handoff_register — Guida d'uso"
aliases: [handoff register, registro handoff, handoff_register]
tags: [meta, strumenti, handoff, registro, archiviazione, guida]
---

# handoff_register — Guida completa

## Cos'è

`handoff_register` è il modulo Python del Team Olimpo che automatizza due operazioni critiche del sistema handoff:
1. **Archiviazione** dei file con `stato: completato` da `Team/Handoff/` a `Team/Handoff/Archivio/`
2. **Rigenerazione** di `Team/Handoff/Registro.md` — indice centrale di tutti i handoff attivi e completati

**Percorso nel repository**: `tools/handoff_register/`
**Versione**: 0.1.0
**Responsabile**: Efesto
**Registro gestito**: `Team/Handoff/Registro.md`

### Cosa permette di fare

`handoff_register` consente di:
- Leggere il frontmatter YAML da tutti i file handoff presenti in `Team/Handoff/`
- Identificare i file con `stato: completato`
- Spostare automaticamente questi file in `Team/Handoff/Archivio/`
- Rigenerare il `Registro.md` con due tabelle: una per i file attivi, una per quelli archiviati
- Mantenere la coerenza tra file sorgente e indice senza modificare mai i file originali
- Gestire correttamente i file legacy che non seguono le convenzioni attuali

---

## Prerequisiti

### Dipendenze Python

```
pyyaml>=6.0          → Parsing YAML e lettura frontmatter
loguru>=0.7          → Logging strutturato
rich>=13.0           → Interfaccia CLI colorata
```

Installazione ([[standard-programmazione-python]]):
```bash
uv add pyyaml loguru rich
```
> **Nota**: Se il progetto usa `pyproject.toml`, `uv add` aggiorna automaticamente le dipendenze.
> **Policy progetto**: Questo progetto usa esclusivamente `uv` per la gestione delle dipendenze. Non utilizzare `pip install` direttamente.

### Ambiente

- **Directory di lavoro**: deve essere la root del progetto (`TeamOlimpo/`)
- **Python**: 3.10+
- **OS**: Windows, macOS, Linux
- **Encoding**: UTF-8

### Strutture di input e output

**Input**: File handoff in `Team/Handoff/`
- Ogni file `.md` con frontmatter YAML
- Campi richiesti: `data`, `mittente`, `destinatario`, `tipo`, `stato`
- Campi opzionali: `priorita`, `titolo`, `processato_da`, `processato_il`

**Output**:
- File completati spostati in `Team/Handoff/Archivio/`
- `Team/Handoff/Registro.md` rigenerato con indice aggiornato
- Log dettagliato in `Library/data/handoff_register.log`

---

## Comandi disponibili

Tutti i comandi si eseguono dalla root del progetto.

### 1. Comando `sync` — Sincronizzazione completa

```bash
uv run python -m tools.handoff_register sync [opzioni]
```

Esegue entrambe le operazioni in sequenza:
1. Sposta i file con `stato: completato` in Archivio/
2. Rigenera il Registro.md

#### Uso base

```bash
# Sincronizzazione completa (default)
uv run python -m tools.handoff_register sync

# Sincronizzazione con output dettagliato
uv run python -m tools.handoff_register sync --verbose
```

#### Flag disponibili

| Flag | Short | Descrizione |
|------|-------|-------------|
| `--verbose` | `-v` | Output debug dettagliato su stderr |

#### Esempi

**Esempio 1: Sincronizzazione standard**

```bash
uv run python -m tools.handoff_register sync
```

Output:
```
[✓] Archiviati 3 file:
    - 2026-03-20_proteo-hermes_analisi-dominio.md
    - 2026-03-21_atena-hermes_profilo-ai-nuovo-membro.md
    - 2026-03-22_efesto-clio_specifica-tool.md

[✓] Registro.md rigenerato:
    - 5 file attivi
    - 12 file archiviati
```

**Esempio 2: Sincronizzazione con verbose**

```bash
uv run python -m tools.handoff_register sync -v
```

Output aggiuntivo su stderr con dettagli di parsing, file scansionati e controlli di sicurezza.

---

### 2. Comando `registro` — Solo rigenerazione Registro (read-only)

```bash
uv run python -m tools.handoff_register registro [opzioni]
```

Rigenera solo il `Registro.md` senza toccare alcun file. Non sposta nulla in Archivio. Utile per:
- Verificare l'indice senza fare modifiche
- Debug e audit dello stato del sistema
- Generare report senza effetti collaterali

#### Uso base

```bash
# Rigenera Registro.md senza spostare file
uv run python -m tools.handoff_register registro

# Con output dettagliato
uv run python -m tools.handoff_register registro -v
```

#### Esempio

```bash
uv run python -m tools.handoff_register registro
```

Output:
```
[✓] Registro.md aggiornato:
    - 5 file attivi
    - 12 file archiviati
    - 1 file legacy (warning: frontmatter incompleto)
```

---

### 3. Comando `archivia` — Solo spostamento dei completati

```bash
uv run python -m tools.handoff_register archivia [opzioni]
```

Sposta solo i file con `stato: completato` in Archivio/, senza rigenerare il Registro. Utile quando vuoi separare le due operazioni.

#### Uso base

```bash
# Sposta i file completati
uv run python -m tools.handoff_register archivia

# Con output dettagliato
uv run python -m tools.handoff_register archivia -v
```

#### Esempio

```bash
uv run python -m tools.handoff_register archivia
```

Output:
```
[✓] Archiviati 3 file:
    - 2026-03-20_proteo-hermes_analisi-dominio.md
    - 2026-03-21_atena-hermes_profilo-ai-nuovo-membro.md
    - 2026-03-22_efesto-clio_specifica-tool.md
```

---

## Flag globale: `--verbose / -v`

Disponibile su tutti i comandi. Emette log di debug su stderr con dettagli su:
- Ogni file scansionato
- Campi frontmatter estratti
- Controlli di sicurezza eseguiti
- Operazioni di spostamento/archiviazione

Uso:
```bash
uv run python -m tools.handoff_register -v sync
uv run python -m tools.handoff_register -v registro
uv run python -m tools.handoff_register -v archivia
```

---

## Gestione dei file legacy

La cartella `Team/Handoff/` contiene file storici che non seguono le naming convention e il frontmatter attuale. Esempi:
- `feedback-efesto-loguru-missing.md`
- `profilo-competenze-poros.md`
- File senza frontmatter YAML

### Comportamento dello script

Lo script **non crasha** su file legacy e applica la seguente **policy read-only**:

1. **Scansione**: legge ogni file `.md` in `Team/Handoff/`
2. **Parsing**: estrae il frontmatter se presente
3. **Warnings**: emette WARNING su stderr per ogni campo mancante (es. "campo 'data' mancante")
4. **Inclusione nel Registro**: include i file legacy nel Registro.md con `—` nei campi assenti
5. **Nessuna modifica**: non modifica mai i file sorgente, neppure per aggiungere campi mancanti

### Esempi di warning

```
WARNING | feedback-efesto-loguru-missing.md: campo 'tipo' mancante
WARNING | profilo-competenze-poros.md: campo 'destinatario' mancante
```

I file legacy rimangono in `Team/Handoff/` e sono visibili nel Registro con metadati incompleti.

---

## Policy operative (invarianti)

Il sistema handoff si basa su questi principi inviolabili:

1. **Always read-only sui sorgenti**: nessun file handoff viene mai modificato dallo script
2. **Template ignorato**: la cartella `Team/Handoff/templates/` è sempre esclusa dalla scansione
3. **Registro.md escluso**: il file `Team/Handoff/Registro.md` non viene mai scansionato come sorgente (avoid loops)
4. **No overwrite in Archivio**: se un file con lo stesso nome esiste già in `Team/Handoff/Archivio/`, lo spostamento viene saltato con WARNING
5. **Creazione automatica di directory**: `Team/Handoff/Archivio/` è creata automaticamente se non esiste
6. **Idempotenza**: eseguire il comando due volte ha lo stesso effetto di eseguirlo una volta

---

## Formato del Registro.md

Il `Registro.md` è un file markdown indicizzato in `Team/Handoff/` con due sezioni:

### Struttura

```markdown
---
title: Registro Handoff
aliases: [registro, handoff, indice]
tags: [meta, handoff, registro]
---

# Registro Handoff

Ultimo aggiornamento: 2026-03-26 14:32:05

## Handoff Attivi

(Tabella con file attivi)

## Handoff Archiviati

(Tabella con file archiviati)
```

### Tabella Attivi

| Mittente | Destinatario | Data | Tipo | Stato | Titolo |
|----------|--------------|------|------|-------|--------|
| proteo | poros | 2026-03-24 | analisi | in-corso | Analisi dominio HR |
| efesto | clio | 2026-03-26 | specifica | in-corso | Nuovo tool handoff_register |

### Tabella Archiviati

| Mittente | Destinatario | Data | Tipo | Stato | Titolo | Processato Da | Processato Il |
|----------|--------------|------|------|-------|--------|---------------|----------------|
| proteo | poros | 2026-03-20 | analisi | completato | Analisi dominio Finance | poros | 2026-03-22 |


---

## Frontmatter richiesto e opzionale

Ogni file handoff deve avere un frontmatter YAML. I campi vengono estratti dallo script per il Registro.

### Campi obbligatori

| Campo | Tipo | Descrizione | Esempio |
|-------|------|-------------|---------|
| `data` | string (ISO date) | Data del handoff | `2026-03-26` |
| `mittente` | string | Nome del membro mittente | `efesto` |
| `destinatario` | string | Nome del membro destinatario | `clio` |
| `tipo` | string | Categoria: `specifica`, `analisi`, `profilo`, `feedback`, `report` | `specifica` |
| `stato` | string | Stato: `da-processare`, `in-corso`, `completato` | `in-corso` |

### Campi opzionali

| Campo | Tipo | Descrizione | Esempio |
|-------|------|-------------|---------|
| `priorita` | string | `bassa`, `media`, `alta`, `bloccante` | `alta` |
| `titolo` | string | Titolo breve del handoff | `Nuovo tool handoff_register` |
| `processato_da` | string | Chi ha processato (aggiunto quando stato→completato) | `clio` |
| `processato_il` | string (ISO date) | Quando è stato processato | `2026-03-26` |

### Esempio di frontmatter completo

```yaml
---
data: 2026-03-26
mittente: efesto
destinatario: clio
tipo: specifica
stato: completato
priorita: alta
titolo: "Nuovo tool: handoff_register"
processato_da: clio
processato_il: 2026-03-26
---
```

---

## Casi di utilizzo comuni

### Caso 1: Workflow standard — clio riceve un handoff e lo completa

1. **Poros/Efesto crea il file**:
   ```yaml
   ---
   data: 2026-03-26
   mittente: efesto
   destinatario: clio
   tipo: specifica
   stato: da-processare
   priorita: alta
   titolo: "Nuovo tool handoff_register"
   ---
   ```

2. **Clio lavora sul task e aggiorna lo stato**:
   ```yaml
   stato: completato
   processato_da: clio
   processato_il: 2026-03-26
   ```

3. **Efesto/Poros esegue il comando**:
   ```bash
   uv run python -m tools.handoff_register sync
   ```

4. **Script**:
   - Legge `stato: completato`
   - Sposta il file in `Team/Handoff/Archivio/`
   - Rigenera il Registro con il file archiviato

### Caso 2: Audit senza modifiche

Vuoi controllare lo stato del sistema senza fare modifiche:

```bash
uv run python -m tools.handoff_register registro
```

Questo rigenera solo il Registro senza toccare alcun file.

### Caso 3: Archiviazione manuale

Se vuoi separare lo spostamento dalla rigenerazione:

```bash
# Prima: sposta i completati
uv run python -m tools.handoff_register archivia

# Poi: rigenera il Registro
uv run python -m tools.handoff_register registro
```

### Caso 4: Debug con verbose

Se qualcosa non funziona come previsto:

```bash
uv run python -m tools.handoff_register sync -v
```

Output su stderr mostra ogni step, ogni file scansionato, ogni warning.

---

## Gestione degli errori

### "Nessun file handoff trovato in Team/Handoff/"

**Causa**: La directory non esiste o è vuota.

**Soluzione**: Verifica che `Team/Handoff/` esista e contenga almeno un file `.md`.

### File con frontmatter incompleto

Lo script **non crasha**. Emette WARNING:

```
WARNING | file.md: campo 'tipo' mancante
```

Il file rimane in `Team/Handoff/` e viene incluso nel Registro con `—` nel campo mancante.

### "File gia' presente in Archivio/ — skip spostamento"

**Causa**: Un file con lo stesso nome esiste già in `Team/Handoff/Archivio/`.

**Soluzione**: Verifica manualmente in Archivio/ quale versione è la più recente, poi decidi se sovrascrivere manualmente.

### Registro.md corrotto o non aggiornato

**Causa**: Interruzione durante l'esecuzione dello script.

**Soluzione**: Esegui `uv run python -m tools.handoff_register registro` per rigenerare il Registro da zero.

---

## Logging e debug

### Modalità verbose

Per vedere ogni operazione in dettaglio:

```bash
uv run python -m tools.handoff_register -v sync
```

Output su stderr con timestamp, livello (DEBUG/WARNING/ERROR), modulo e messaggio.

### Visualizzazione log file

```bash
# Mostra le ultime 50 righe
tail -n 50 "Library/data/handoff_register.log"

# Su Windows (PowerShell)
Get-Content "Library\data\handoff_register.log" -Tail 50
```

Log file contiene tutte le operazioni: file scansionati, warning, spostamenti, rigenerazioni.

---

## Moduli interni

| Modulo | File | Responsabilità |
|--------|------|----------------|
| `cli` | `cli.py` | Entry point, argparse, dispatch comandi, logging |
| `scanner` | `scanner.py` | Lettura frontmatter YAML dai file handoff |
| `archiver` | `archiver.py` | Spostamento file completati in Archivio/ |
| `writer` | `writer.py` | Generazione di Registro.md |
| `config` | `config.py` | Path centralizzati (handoff, archivio, registro, log) |

---

## Integrazione con il Team Olimpo

### Flusso con Poros

Poros coordina:
1. Invia istruzioni ai membri (tramite handoff)
2. I membri aggiornano lo stato
3. Poros esegue `uv run python -m tools.handoff_register sync` periodicamente
4. Il Registro.md rimane aggiornato automaticamente

### Flusso con i Membri (Proteo, Atena, Efesto, Clio)

Ogni membro:
1. Riceve un handoff (file `.md` in `Team/Handoff/`)
2. Elabora il contenuto
3. Aggiorna il frontmatter con `stato: completato`, `processato_da: <nome>`, `processato_il: <data>`
4. Il file rimane in `Team/Handoff/` fino a quando `handoff_register` non lo sposta

---

## Limitazioni e note

- **Script sempre read-only**: non modifica mai i file handoff originali
- **Un Registro centrale**: esiste un solo `Registro.md` aggiornato dinamicamente
- **Nessun merge**: il comando non unisce contenuti, solo sposta file e aggiorna metadati
- **Non sincronizza il database**: il Registro.md è il sistema di riferimento autoritative; nessun database SQLite viene toccato
- **Legacy-friendly**: i file vecchi rimangono leggibili anche se con frontmatter incompleto

---

## Costi e performance

- **Velocità**: Scansione e archiviazione di 100+ file in <1 secondo
- **Memoria**: Minima, i file vengono letti uno per uno
- **Spazio disco**: Registro.md è tipicamente <5KB, archivio cresce linearmente (+0.5-2KB per file archiviato)

---

## Riferimenti e cross-reference

- **Handoff system**: [[project_handoff_sistema]] — sistema completo di handoff
- **Strumenti correlati**: [[strumenti-indice]] — indice di tutti gli strumenti
- **Vault conventions**: [[obsidian-vault]] — convenzioni Markdown/Obsidian
