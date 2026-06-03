---
title: "consulto — Guida d'uso"
aliases: [consulto, tool consulto, ai esterne, grok, gemini]
tags: [meta, strumenti, ai, consulto, guida]
---

# consulto — Guida completa

## Cos'è

`consulto` è il modulo Python del Team Olimpo che automatizza le consulte a LLM di terze parti (xAI/Grok e Google/Gemini) da linea di comando, con un'interfaccia unificata e configurazione minimale.

**Percorso nel repository**: `tools/consulto/`
**Versione**: 0.4.0
**Responsabile**: Efesto

### Cosa permette di fare

`consulto` consente di:
- Inviare prompt testuali a Grok (xAI) o Gemini (Google) con una singola riga di comando
- Configurare facilmente quale provider e quale modello usare
- Usare system prompt opzionali per guidare il comportamento del modello
- Leggere prompt da argomenti, stdin, o file
- Ottenere risposte pulite su stdout (pipeable, facilmente integrabile in script)
- Visualizzare metadati sulla risposta in modalità verbose (token, tempo, modello effettivo)

---

## Prerequisiti

### Dipendenze Python

```
openai>=1.0            → SDK OpenAI (usato come client per xAI modelli standard)
google-genai>=1.0      → SDK Google GenAI (nuovo, non il vecchio google-generativeai)
xai-sdk>=0.1           → SDK xAI per modelli multi-agent (grok-4.20-multi-agent-*)
python-dotenv>=1.0     → Caricamento variabili d'ambiente da .env
loguru>=0.7            → Logging strutturato
```

Installazione (tutte incluse nel `pyproject.toml` - [[standard-programmazione-python]]):
```powershell
uv sync
```
> **Nota**: `uv sync` legge `pyproject.toml` e configura l'ambiente virtuale automaticamente.

### Configurazione API key

Le API key si salvano in un file `.env` nella **root del progetto** (`TeamOlimpo/.env`):

```
XAI_API_KEY=xai-...
GEMINI_API_KEY=AI...
```

**Il file `.env` è in `.gitignore` — non verrà mai committato.**

#### Come ottenere le API key

**Per Grok (xAI)**:
1. Vai a https://console.x.ai
2. Effettua il login o registrati
3. Crea una nuova API key
4. Copia la chiave e aggiungila al file `.env` come `XAI_API_KEY=xai-...`

**Per Gemini (Google)**:
1. Vai a https://aistudio.google.com/apikey
2. Effettua il login con il tuo account Google
3. Clicca "Create API key" (per il progetto di default o uno nuovo)
4. Copia la chiave e aggiungila al file `.env` come `GEMINI_API_KEY=AI...`

### Ambiente

- **Directory di lavoro**: deve essere la root del progetto (`TeamOlimpo/`)
- **Python**: 3.10+
- **OS**: Windows, macOS, Linux
- **Encoding**: Windows usa UTF-8 automaticamente (gestito da `consulto` internamente)

---

## Come si usa

Tutti i comandi si eseguono dalla root del progetto. Il tool supporta quattro modalità di uso:

### 1. Consulto singolo (modo base)

```powershell
uv run python -m tools.consulto [opzioni] PROMPT
```

### 2. Comando `models` (lista modelli)

```powershell
uv run python -m tools.consulto models
uv run python -m tools.consulto models --provider grok
```

### 3. Modalità batch (elabora più file con template)

```powershell
uv run python -m tools.consulto --prompt <template.md> --input <file_o_glob> [--output <cartella>] [opzioni]
```

### 4. Modalità interattiva (menu)

```powershell
uv run python -m tools.consulto              # nessun argomento
uv run python -m tools.consulto -i           # flag esplicito
```

### Flag globali

Flag disponibili su tutti i comandi (salvo dove diversamente indicato):

```powershell
--verbose / -v    → mostra metadati su stderr (modello, token, tempo)
--provider / -p   → scelta del provider (grok, gemini)
--model / -m      → override del modello default
--system          → messaggio di sistema opzionale
--stdin           → legge il prompt da stdin
--interactive/-i  → avvia il menu interattivo
--version         → mostra la versione di consulto
```

---

## Uso base — Esempi

### Consulto semplice (provider default = Grok)

```powershell
uv run python -m tools.consulto "Qual è la capitale della Francia?"
```

**Output**: (solo il testo della risposta)
```
La capitale della Francia è Parigi.
```

### Con provider diverso (Gemini)

```powershell
uv run python -m tools.consulto --provider gemini "Spiega il teorema di Bayes in 3 righe"
```

### Con system prompt

```powershell
uv run python -m tools.consulto --system "Rispondi sempre in italiano, con linguaggio semplice" "What is entropy?"
```

### Con override del modello

Per usare il modello flagship di Grok (piu' potente, piu' lento, piu' costoso):

```powershell
uv run python -m tools.consulto --provider grok --model grok-4.20-0309-non-reasoning "Analizza in profondità questa questione complessa: ..."
```

Per usare il modello standard di Gemini:

```powershell
uv run python -m tools.consulto --provider gemini --model gemini-2.5-flash "..."
```

### Lettura da stdin (pipe e file)

```powershell
cat documento.txt | uv run python -m tools.consulto --stdin

# Oppure con redirect da file
uv run python -m tools.consulto --stdin < mio_prompt.txt

# Oppure con echo su Windows
echo "Analizza questo testo" | uv run python -m tools.consulto --stdin
```

### Output verbose (mostra token e tempo)

```powershell
uv run python -m tools.consulto --verbose "Cos'è un API gateway?"
```

**Output su stdout** (testo della risposta):
```
Un API gateway è un server che funge da punto di accesso...
```

**Output su stderr** (riga stats sempre presente + dettagli verbose):
```
(4.4s · ↑169 ↓393 tok · $0.0002)

--- verbose ---
Provider:  grok
Modello:   grok-4-1-fast-non-reasoning
Token in:  169
Token out: 393
```

---

## Flag disponibili

### Flag della modalità singola

| Flag | Short | Argomento | Descrizione |
|------|-------|-----------|-------------|
| `--provider` | `-p` | `PROVIDER` | Scelta provider: `grok` (default), `gemini` |
| `--model` | `-m` | `MODELLO` | Override del modello default per il provider |
| `--system` | — | `SYSTEM_PROMPT` | Messaggio di sistema opzionale |
| `--stdin` | — | — | Legge il prompt da stdin invece che da argomento |
| `--agent-count` | — | `N` | Numero agenti per modelli multi-agent (4 o 16). Ignorato per modelli standard. Default: 4 |
| `--verbose` | `-v` | — | Mostra metadati su stderr (token, tempo, modello effettivo) |
| `--version` | — | — | Mostra la versione di consulto e esce |

### Flag della modalità batch

| Flag | Argomento | Descrizione |
|------|-----------|-------------|
| `--prompt` | `FILE.md` | File Markdown contenente il template (sezione `## Prompt` obbligatoria) |
| `--input` | `GLOB\|PATH...` | Uno o più file o glob pattern da processare (es. `lib/documents/*.md`) |
| `--output` | `CARTELLA` | Cartella dove salvare i risultati. Default: stdout con separatori |

### Flag della modalità interattiva

| Flag | Short | Descrizione |
|------|-------|-------------|
| `--interactive` | `-i` | Attiva esplicitamente il menu interattivo |

### Comportamento dei comandi

**Prompt obbligatorio** — Specificare un PROMPT come argomento posizionale **OPPURE** usare `--stdin`:

```powershell
# Valido
uv run python -m tools.consulto "il mio prompt"
echo "il mio prompt" | uv run python -m tools.consulto --stdin

# Errore — manca il prompt
uv run python -m tools.consulto
```

**Output**: L'output della risposta va su **stdout** (pulito, senza decorazioni), gli errori e i log vanno su **stderr**.

Questo design rende possibile usare consulto in pipe:

```powershell
# Estrarre solo la risposta per ulteriore elaborazione
uv run python -m tools.consulto "Dammi una lista di 5 elementi" | sort
```

---

## Provider disponibili

### Grok (xAI) — Provider default

**Modello default**: `grok-4-1-fast-non-reasoning`
- Costo: $0.20/M input, $0.50/M output (il più economico)
- Contesto: 2M token
- Ideale per: consulti rapidi, dove non serve ragionamento complesso

**Quando usare Grok**:
- Consulti rapidi e risposte veloci
- Brainstorming e ideazione
- Analisi di testi medi

**Modelli Grok disponibili**:

| Modello | Prezzo (1M tok) | Note |
|---------|-----------------|------|
| `grok-4-1-fast-non-reasoning` | $0.20 in / $0.50 out | Default — veloce ed economico |
| `grok-4-1-fast-reasoning` | $0.20 in / $0.50 out | Aggiunge ragionamento chain |
| `grok-4.20-0309-non-reasoning` | $2.00 in / $6.00 out | Flagship, qualità massima |
| `grok-4.20-0309-reasoning` | $2.00 in / $6.00 out | Flagship con reasoning — usato per analisi KBA |
| `grok-4.20-multi-agent-0309` | $2.00 in / $6.00 out | Multi-agent (vedi sezione dedicata) |

Esempio:
```powershell
uv run python -m tools.consulto --provider grok "Domanda semplice"
uv run python -m tools.consulto --model grok-4-1-fast-reasoning "Problema che richiede ragionamento"
uv run python -m tools.consulto --model grok-4.20-0309-reasoning "Analisi di altissima qualità"
uv run python -m tools.consulto --model grok-4.20-multi-agent-0309 "Ricerca approfondita multi-agent"
```

### Gemini (Google) — Provider alternativo

**Modello default**: `gemini-2.5-flash-lite`
- Costo: $0.10/M input, $0.40/M output (molto economico)
- Ha **free tier** (rate-limited ma ottimo per sviluppo/test)
- Ideale per: throughput elevato, uso gratuito

**Quando usare Gemini**:
- Quando le API key Grok non sono disponibili
- Free tier per sviluppo e test
- Quando si preferisce la famiglia Gemini di Google

**Alternative in Gemini**:
- `gemini-2.5-flash` — più capace ($0.30/$2.50 per 1M, con free tier)
- NON usare `gemini-2.0-flash` — deprecato, shutdown previsto 1 giugno 2026

Esempio:
```powershell
uv run python -m tools.consulto --provider gemini "Domanda normale"
uv run python -m tools.consulto --provider gemini --model gemini-2.5-flash "Risultati più sofisticati"
```

### Confronto rapido

| Aspetto | Grok | Gemini |
|---------|------|--------|
| Provider default | Sì | — |
| Modello default | `grok-4-1-fast-non-reasoning` | `gemini-2.5-flash-lite` |
| Costo (fast) | $0.20 in / $0.50 out | $0.10 in / $0.40 out |
| Free tier | No | Sì (rate-limited) |
| Ideale per | Consulti rapidi | Uso gratuito, throughput |
| SDK usato | openai (standard) / xai-sdk (multi-agent) | google-genai nativo |

---

## Configurazione avanzata

### Override del modello per singola chiamata

```powershell
# Grok: usa il modello flagship
uv run python -m tools.consulto --model grok-4.20-0309-non-reasoning "Analisi complessa"

# Gemini: usa il modello standard
uv run python -m tools.consulto --provider gemini --model gemini-2.5-flash "Query complessa"
```

### System prompt personalizzato

```powershell
# Imposta il tone e lo stile
uv run python -m tools.consulto --system "Rispondi come un esperto di machine learning, in italiano, con esempi concreti" "Cos'è il gradient descent?"

# Limita la lunghezza della risposta
uv run python -m tools.consulto --system "Rispondi in massimo 100 parole" "Spiega il principio di Occam"

# Specifica un ruolo
uv run python -m tools.consulto --system "Sei un consulente di architettura software. Rispondi in modo tecnico e strutturato." "Come organizzaresti un microservizio?"
```

### Lettura da file

```powershell
# Leggi il prompt da un file di testo
uv run python -m tools.consulto --stdin < mio_prompt.txt

# Su Windows, con Get-Content (PowerShell)
Get-Content mio_prompt.txt | uv run python -m tools.consulto --stdin

# Su Windows, con type + pipe
type mio_prompt.txt | uv run python -m tools.consulto --stdin
```

### Combinare stdin, provider, modello e system prompt

```powershell
# Lettura da file, Gemini, modello custom, system prompt
cat documento.txt | uv run python -m tools.consulto --stdin --provider gemini --model gemini-2.5-flash --system "Analizza come un esperto di sicurezza informatica"
```

---

## Novità v0.4.0

### 1. Supporto modelli multi-agent (grok-4.20-multi-agent-0309)

I modelli multi-agent xAI coordinano più sub-agenti AI in parallelo per ricerche approfondite. Richiedono `xai-sdk` (incluso nel `pyproject.toml`) e usano un'API diversa dall'SDK OpenAI standard — il routing è automatico in base al nome del modello.

#### Flag `--agent-count`

Controlla quanti agenti vengono coordinati in parallelo:

| Valore | Uso |
|--------|-----|
| `4` | Default — query veloci, costo ragionevole |
| `16` | Ricerca approfondita — più lento, ~4x più costoso |

```powershell
# Multi-agent con 4 agenti (default)
uv run python -m tools.consulto --provider grok --model grok-4.20-multi-agent-0309 "Prompt complesso"

# Multi-agent con 16 agenti (ricerca approfondita)
uv run python -m tools.consulto --provider grok --model grok-4.20-multi-agent-0309 --agent-count 16 "Ricerca estesa"
```

#### Nota sui costi

Il modello multi-agent fattura i token di tutti i sub-agenti. Con 4 agenti, il costo effettivo per query è ~4x quello nominale ($2.00/$6.00 per 1M). Usare per ricerche web o domande aperte, non per risposte a domande tecniche strutturate dove modelli standard danno risultati equivalenti.

Da una comparazione del 2026-04-07 su un prompt DeltaV/PID:
- `grok-4.20-multi-agent-0309`: 17.7k token input (vs ~350 degli altri), costo $0.044, risposta qualitativamente analoga
- `grok-4.20-0309-reasoning`: 336 token input, costo $0.009, dettagli DeltaV-specifici migliori

**Raccomandazione**: preferire `grok-4.20-0309-reasoning` per analisi tecniche; usare multi-agent solo per ricerche che beneficiano di parallelismo (es. "raccogli informazioni su X da fonti diverse").

### 2. Token input/output separati

La riga stats ora mostra token inviati e ricevuti con frecce ↑↓:

```
(4.4s · ↑169 ↓393 tok · $0.0002)
```

- `↑` = token input (inviati al modello)
- `↓` = token output (ricevuti dal modello)

### 3. Fix subcommand `models`

Il subcommand `uv run python -m tools.consulto models` ora funziona correttamente. In precedenza la stringa "models" veniva inviata come prompt al provider invece di essere riconosciuta come subcommand.

---

## Novita' v0.3.0

### 1. `--system` risolto come path

Il flag `--system` ora accetta sia una stringa di testo che un path a file. Se il valore e' un path esistente sul filesystem, `consulto` ne legge il contenuto e lo usa come system prompt. Se non e' un path (o la lettura fallisce), la stringa viene usata invariata.

```powershell
# System prompt da file
uv run python -m tools.consulto --system ".claude/agents/dike.md" "Analizza questo testo"

# System prompt come stringa (comportamento invariato)
uv run python -m tools.consulto --system "Rispondi in italiano" "test"
```

Questo e' utile per riutilizzare i profili agente del Team Olimpo (in `.claude/agents/`) come system prompt senza doverli copiare inline.

### 2. `--var KEY=VALUE` — Variabili template

Permette di iniettare variabili personalizzate nei template batch. Ogni `--var` e' nella forma `KEY=VALUE` e sostituisce il placeholder `{{KEY}}` nel template. Il flag e' ripetibile.

```powershell
# Inietta la variabile 'site' nel template
uv run python -m tools.consulto \
  --prompt Team/Prompts/kba/analisi-rischio-kba.md \
  --input "lib/documents/*.md" \
  --var site=Lonigo \
  --var anno=2026
```

Nel template basta usare `{{site}}` o `{{anno}}` — i placeholder vengono sostituiti dopo quelli built-in (`{{kba_text}}`, `{{filename}}`, `{{date}}`).

### 3. `--dry-run` — Anteprima senza chiamata API

Mostra il payload (system prompt + prompt utente renderizzato) che verrebbe inviato all'API, senza effettuare alcuna chiamata. Non richiede API key configurata. Utile per verificare il rendering del template prima di consumare token.

```powershell
# Verifica il rendering di un batch (mostra solo il primo file)
uv run python -m tools.consulto \
  --dry-run \
  --prompt Team/Prompts/kba/analisi-rischio-kba.md \
  --input "lib/documents/*.md" \
  --var site=Lonigo

# Anteprima chiamata singola
uv run python -m tools.consulto --dry-run "Dimmi ciao"

# Anteprima con system prompt da file
uv run python -m tools.consulto --dry-run --system ".claude/agents/dike.md" "test"
```

Output di esempio:
```
=== SYSTEM ===
(nessuno)
=== USER ===
Dimmi ciao
=== END DRY RUN ===
```

---

## Nuove funzionalita' (v0.2.0)

### 1. Comando `models` — Lista modelli disponibili

Interroga le API dei provider per ottenere in tempo reale la lista dei modelli disponibili, con informazioni su quali sono i default e i prezzi (se configurati).

#### Sintassi

```powershell
# Elenca tutti i modelli di tutti i provider
uv run python -m tools.consulto models

# Elenca solo i modelli di un provider specifico
uv run python -m tools.consulto models --provider grok
uv run python -m tools.consulto models --provider gemini
```

#### Output

```
GROK (xAI)
  grok-4-1-fast-non-reasoning       [default]    input: $0.20/M   output: $0.50/M
  grok-4-1-fast-reasoning                        input: $0.20/M   output: $0.50/M
  grok-4.20-0309-non-reasoning                   input: $2.00/M   output: $6.00/M
  grok-4.20-0309-reasoning                       input: $2.00/M   output: $6.00/M

GEMINI (Google)
  gemini-2.5-flash-lite             [default]    input: $0.10/M   output: $0.40/M
  gemini-2.5-flash                               input: $0.30/M   output: $2.50/M
```

#### Note

- Il tag `[default]` indica il modello usato quando non specifichi `--model`
- I prezzi vengono caricati dal dizionario statico `KNOWN_PRICES` in `config.py` — se un modello non è presente, mostra "prezzo n.d."
- I prezzi sono espressi per **milione di token** (sia input che output)
- Utile per scoprire i nuovi modelli disponibili senza consultare la documentazione

#### Esempi

```powershell
# Vedi tutti i modelli e i loro prezzi
uv run python -m tools.consulto models

# Scopri quali modelli Grok sono disponibili
uv run python -m tools.consulto models --provider grok

# Usa il modello Grok flagship dopo aver confermato che esiste
uv run python -m tools.consulto models --provider grok
# (output mostra grok-4.20-0309-non-reasoning disponibile)
uv run python -m tools.consulto --model grok-4.20-0309-non-reasoning "Analisi complessa"
```

---

### 2. Modalità batch — Elabora più file con template

Legge un template Markdown (con placeholder), lo applica a uno o più file di input, chiama l'API per ciascun file, e salva i risultati. Ideale per elaborazioni ripetitive su interi dataset.

#### Sintassi

```powershell
uv run python -m tools.consulto --prompt <template.md> --input <file_o_glob> [--output <cartella>] [--provider ...] [--model ...]
```

#### Componenti

**Template (`--prompt`)**:
- File Markdown con una sezione heading `## Prompt` obbligatoria
- Supporta i seguenti placeholder:
  - `{{kba_text}}` — contenuto del file di input
  - `{{filename}}` — nome file senza estensione
  - `{{date}}` — data odierna in formato ISO (YYYY-MM-DD)
- Tutto il testo dopo `## Prompt` fino alla prossima heading di livello 1 o 2 è considerato il template

**Input (`--input`)**:
- Uno o più argomenti, ognuno può essere:
  - Un path assoluto: `C:\path\to\file.md`
  - Un path relativo: `lib/documents/doc.md`
  - Un glob pattern: `lib/documents/*.md`, `lib/**/*.md`
- I duplicati vengono rimossi automaticamente
- Se nessun file viene trovato, il comando esce con errore

**Output (`--output`)**:
- Se specificato: crea la cartella, salva i risultati come `<filename>-<provider>.txt`
- Se omesso: stampa i risultati su stdout con separatori tra file

#### Formato template

Esempio di file template `Team/Prompts/kba/analisi-rischio.md`:

```markdown
---
title: Analisi di rischio KBA
description: Analizza un documento KBA per identificare rischi
---

## Prompt

Sei un analista di rischio specializzato. Analizza il seguente documento e identifica:
- Rischi operativi e di sicurezza
- Punti di criticità
- Raccomandazioni di mitigazione

Documento:
{{kba_text}}

Data analisi: {{date}}
File: {{filename}}

Rispondi in italiano, in formato strutturato con bullet point.
```

#### Progresso batch

Durante l'elaborazione, il comando stampa su **stderr** il progresso nel formato:

```
[1/10] documento1.md ... ok (1.2s) -> documento1-grok.txt
[2/10] documento2.md ... ok (0.8s) -> documento2-grok.txt
[3/10] documento3.md ... ERRORE lettura: file non trovato
[4/10] documento4.md ... ERRORE API (2.1s): rate limit exceeded
[5/10] documento5.md ... ok (1.5s) -> documento5-grok.txt
...
```

- Mostra l'indice e il totale dei file (`[N/TOT]`)
- Se un file ha errore, il batch continua con i successivi
- In fine stampa il numero di errori riscontrati (exit code 1 se errori > 0)

#### Esempi

**Esempio 1: Batch con salvataggio su file**

```powershell
# Analizza tutti i documenti KBA, salva i risultati in Team/Handoff/
uv run python -m tools.consulto \
  --prompt Team/Prompts/kba/analisi-rischio.md \
  --input "lib/documents/*.md" \
  --output Team/Handoff/risultati-analisi
```

Output:
```
[1/5] nk-2400-0150.md ... ok (2.3s) -> nk-2400-0150-grok.txt
[2/5] nk-2400-0151.md ... ok (2.1s) -> nk-2400-0151-grok.txt
[3/5] nk-2400-0152.md ... ok (2.4s) -> nk-2400-0152-grok.txt
[4/5] nk-2400-0153.md ... ok (2.2s) -> nk-2400-0153-grok.txt
[5/5] nk-2400-0154.md ... ok (2.0s) -> nk-2400-0154-grok.txt
```

**Esempio 2: Batch con output a stdout**

```powershell
# Analizza due file specifici, stampa i risultati concatenati su stdout
uv run python -m tools.consulto \
  --prompt Team/Prompts/kba/analisi.md \
  --input lib/documents/doc1.md lib/documents/doc2.md
```

Output (su stdout):
```
============================================================
# doc1.md
============================================================

[Risposta Grok per doc1]

============================================================
# doc2.md
============================================================

[Risposta Grok per doc2]
```

**Esempio 3: Batch con Gemini e modello specifico**

```powershell
uv run python -m tools.consulto \
  --prompt Team/Prompts/kba/analisi-rischio-kba.md \
  --input "lib/documents/**/*.md" \
  --provider gemini \
  --model gemini-2.5-flash \
  --output Team/Handoff/analisi
```

**Esempio 4: Batch con system prompt aggiuntivo**

```powershell
uv run python -m tools.consulto \
  --prompt Team/Prompts/team/test-profilo.md \
  --input ".claude/agents/proteo.md" \
  --output "Library/deliverables/" \
  --system ".claude/agents/poros.md"
```

#### Note sul batch

- Se `--prompt` è specificato, `--input` è **obbligatorio**
- Il rendering dei placeholder avviene **prima** della chiamata API
- L'errore di un singolo file **non blocca** l'elaborazione degli altri
- I tempi di risposta possono variare significativamente a seconda del provider e della lunghezza del documento
- Usa `--verbose` per vedere dettagli su ogni chiamata (modello usato, token, ecc.)

---

### 3. Modalità interattiva — Menu testuale

Una guida passo-passo interattiva per chi non ricorda i comandi. Permette di scegliere il prompt (da template o testo libero), il file di input (opzionale), il provider, il modello, e salva il risultato su file se desiderato.

#### Attivazione

La modalità interattiva si attiva automaticamente quando:
- Non specifichi alcun argomento: `uv run python -m tools.consulto`
- Usi il flag `--interactive` o `-i`: `uv run python -m tools.consulto -i`

#### Flusso

1. **Scelta del prompt**:
   - Il tool scopre automaticamente i file `.md` in `Team/Prompts/**/*.md`
   - Elenca i prompt disponibili con titolo e descrizione (da frontmatter YAML)
   - Opzione finale: "Testo libero" per scrivere il prompt direttamente
   - Default: "Testo libero"

2. **Input opzionale** (solo se hai scelto un prompt da template):
   - Chiede un file o glob pattern (es. `lib/documents/*.md`)
   - Se specifichi un file singolo: elabora solo quel file
   - Se specifichi un glob: esegue batch interattivo
   - Se lasci vuoto (invio): chiede il testo da inserire nel placeholder `{{kba_text}}`

3. **Scelta provider e modello**:
   - Chiede quale provider usare (grok, gemini, ecc.)
   - Chiede quale modello (invio per usare il default del provider)

4. **Invio e risposta**:
   - Mostra la risposta del modello
   - Informazioni sulla risposta (provider, modello, tempo)

5. **Salvataggio opzionale**:
   - Chiede se salvare la risposta su file
   - Default: `consulto-output-<provider>.txt`
   - Permette di personalizzare il nome del file

#### Esempio interattivo

```
=== CONSULTO — Team Olimpo ===

Prompt disponibili:
  [1] kba/analisi-rischio — Analizza un documento KBA per identificare rischi
  [2] kba/classificazione — Classifica per area tematica
  [3] traduzione — Traduci da English a Italiano
  [4] Testo libero

Scelta [default: 4]: 1

File di input (glob, path, o invio per testo libero):
  Esempi: lib/documents/*.md  oppure  lib/documents/nk-2400-0150.md
> lib/documents/nk-2400-0150.md

Provider [grok/gemini, default: grok]:
Modello [invio per default: grok-4-1-fast-non-reasoning]:

[Invio richiesta...]

--------------------------------------------
--- Risposta ---
Analisi di rischio per il documento nk-2400-0150:

**Rischi operativi**:
- Insufficienza di controlli su autorizzazioni
- ...

**Rischi di sicurezza**:
- ...

**Raccomandazioni**:
- ...
--------------------------------------------
(Provider: grok | Modello: grok-4-1-fast-non-reasoning | Tempo: 2.3s)

Salvare in file? [s/N]: s
Percorso file [consulto-output-grok.txt]: Team/Handoff/analisi-nk-2400-0150.txt
Salvato in: C:\Users\dev\Desktop\TeamOlimpo\Team\Handoff\analisi-nk-2400-0150.txt
```

#### Note sulla modalità interattiva

- La directory `Team/Prompts/` viene scansionata automaticamente per scoprire i template
- I template devono avere una sezione `## Prompt` (come nella modalità batch)
- Se un template non è parsabile, viene saltato con un warning
- Il batch interattivo (più file da un singolo template) chiede il provider/modello una volta sola
- Utile per utenti che non ricordano i flag esatti o vogliono un'esperienza guidata

---

## Output Markdown e integrazione con Obsidian

Sebbene `consulto` sia concepito per output grezzo su stdout (facilmente pipeable), se vuoi salvare una consulta nel vault Obsidian, il flusso è:

```powershell
# Salva la risposta in un file Markdown
uv run python -m tools.consulto "Spiega il concetto di entropia" > risposta.md

# Oppure con output verbose su stderr e risposta su stdout
uv run python -m tools.consulto --verbose "Domanda" 2>verbose.log 1>risposta.txt
```

Il file generato conterrà solo il testo grezzo della risposta, senza frontmatter. Se necessario, aggiungi manualmente:

```markdown
---
title: "Titolo della consulta"
date: 2026-03-25
provider: grok
model: grok-4-1-fast-non-reasoning
tags: [ai, consulta]
---

# Domanda
Spiega il concetto di entropia

# Risposta
...
```

---

## Logging e debug

### Modalità verbose

Per vedere dettagli sulla chiamata API (token, tempo di risposta, modello effettivo):

```powershell
uv run python -m tools.consulto --verbose "Domanda"
```

Output su **stderr**:
```
(1.2s · ↑42 ↓156 tok · $0.0001)
--- verbose ---
Provider:  grok
Modello:   grok-4-1-fast-non-reasoning
Token in:  42
Token out: 156
```

### Debugging della configurazione

Se la API key non viene trovata, il tool stampa un messaggio esplicativo su stderr:

```
Errore: API key per 'grok' non trovata.

La variabile d'ambiente richiesta è: XAI_API_KEY

Come configurarla:
  1. Crea (o modifica) il file: C:\Users\dev\Desktop\TeamOlimpo\.env
  2. Aggiungi la riga:
         XAI_API_KEY=la-tua-chiave-api

  3. Ottieni la chiave da: https://console.x.ai

Nota: il file .env è escluso da git (.gitignore) — non verrà mai committato.
```

---

## Troubleshooting

### "Errore: API key per 'grok' non trovata"

**Soluzione**:
1. Verifica che il file `.env` esista nella root del progetto (`TeamOlimpo/.env`)
2. Verifica che contenga la riga `XAI_API_KEY=xai-...`
3. Verifica che la chiave sia non vuota (non sia `XAI_API_KEY=`)
4. Riavvia il terminale (le variabili d'ambiente caricate da `.env` vengono lette al primo import)

Verifica della configurazione:
```powershell
# Stampa il valore della variabile d'ambiente (se vuota, non è configurata)
$env:XAI_API_KEY  # PowerShell
echo $XAI_API_KEY  # bash
```

### "Errore: La libreria 'openai' non è installata"

```powershell
uv add openai
```
> Vedi [[standard-programmazione-python]] per la gestione delle dipendenze con uv. **Policy progetto**: usa esclusivamente `uv` per gestire dipendenze.

### "Errore: La libreria 'google-genai' non è installata"

```powershell
uv add google-genai
```
> Vedi [[standard-programmazione-python]] per la gestione delle dipendenze con uv. **Policy progetto**: usa esclusivamente `uv` per gestire dipendenze.

### "Errore: python-dotenv non è installato"

```powershell
uv add python-dotenv
```
> Vedi [[standard-programmazione-python]] per la gestione delle dipendenze con uv. **Policy progetto**: usa esclusivamente `uv` per gestire dipendenze.

### La risposta è lenta o timeout

- **Grok**: controlla il tuo rate limit su https://console.x.ai (base: ~480 richieste/minuto)
- **Gemini free tier**: rate limit di 10-15 richieste/minuto, upgrade il tier se necessario
- Prova con un modello diverso (ad es., un modello "fast" invece del flagship)

### Caratteri speciali non visualizzati correttamente (Windows)

Il tool `consulto` forza automaticamente UTF-8 su stdout e stderr, quindi questo non dovrebbe accadere. Se vedi caratteri corrotti:

1. Verifica che il terminale PowerShell supporti UTF-8:
   ```powershell
   $OutputEncoding = [System.Text.UTF8Encoding]::new($false)
   ```

2. Oppure usa bash (se disponibile):
   ```bash
   uv run python -m tools.consulto "Domanda con accenti è éù"
   ```

### Uscita con codice di errore 1

Il tool esce con codice 1 se:
- Manca il PROMPT (e non è usato `--stdin`)
- La API key non è configurata
- La risposta del modello fallisce (errore API, timeout, rate limit)

Esegui con `--verbose` per più dettagli:

```powershell
uv run python -m tools.consulto --verbose "Domanda" ; Write-Host "Exit code: $LASTEXITCODE"  # PowerShell
uv run python -m tools.consulto --verbose "Domanda" ; echo $?  # bash
```

---

## Moduli interni

| Modulo | File | Responsabilità |
|--------|------|----------------|
| `cli` | `cli.py` | Entry point, parsing argomenti, setup logging, coordin orchestrazione |
| `config` | `config.py` | Caricamento `.env`, costanti, funzioni di recupero API key |
| `providers` | `providers/` | Interfaccia comune e implementazioni provider (Grok, Gemini) |
| `providers/base` | `providers/base.py` | Protocol e dataclass ChatResponse |
| `providers/grok` | `providers/grok.py` | GrokProvider (SDK OpenAI con base_url xAI) |
| `providers/gemini` | `providers/gemini.py` | GeminiProvider (SDK google-genai nativo) |

---

## Limitazioni e note

- **No streaming**: le risposte sono complete (non vengono mostrate token-by-token)
- **No context history**: ogni chiamata è indipendente, non c'è memoria tra consulte
- **No file upload**: il prompt è solo testo, non puoi allegare file
- **Rate limits**: sia Grok che Gemini hanno rate limit — controlla la console se riscontri problemi di throttling

---

## Costi indicativi

Basato su una consulta tipica (~500 token input, ~1000 token output):

| Provider | Modello | Costo | Tempo medio |
|----------|---------|-------|------------|
| Grok | grok-4-1-fast-non-reasoning | ~$0.0006 | <2s |
| Grok | grok-4.20-0309-non-reasoning | ~$0.006 | <5s |
| Grok | grok-4.20-0309-reasoning | ~$0.009 | ~25s |
| Grok | grok-4.20-multi-agent-0309 (4 agenti) | ~$0.044 | ~30s |
| Gemini | gemini-2.5-flash-lite | ~$0.0005 | <2s |
| Gemini | gemini-2.5-flash | ~$0.0015 | <3s |

**Gemini free tier**: copre ampiamente l'uso in fase di sviluppo.

---

## Riferimenti ufficiali

- **xAI API docs**: https://docs.x.ai/developers/rest-api-reference/inference/chat
- **xAI modelli**: https://docs.x.ai/developers/models
- **xAI console**: https://console.x.ai
- **Google GenAI SDK**: https://github.com/googleapis/python-genai
- **Gemini API docs**: https://googleapis.github.io/python-genai/
- **Gemini prezzi**: https://ai.google.dev/gemini-api/docs/pricing
- **Gemini modelli**: https://ai.google.dev/gemini-api/docs/models
- **Google AI Studio (API key)**: https://aistudio.google.com/apikey
