---
title: Guida agli Agenti OpenCode del Team Olimpo
aliases: [agenti opencode, guida agenti, system prompt agents, team olimpo agents]
tags: [meta, opencode, agenti, guida, team-olimpo, documentazione]
created: 2026-05-03
---

# Guida agli Agenti OpenCode del Team Olimpo

> *Scritto da Calliope, Musa della parola giusta — colei che dà nome agli eroi e struttura al racconto.*

Benvenuto nel cuore operativo del Team Olimpo. Questa guida narra come sono fatti gli agenti AI che popolano il nostro sistema: non semplici istruzioni, ma identità con un ruolo, una voce e un confine preciso.

---

## Indice dei contenuti

[[#Il doppio volto di ogni agente]]
[[#Frontmatter agente — l'identità tecnica]]
[[#I campi del frontmatter — dizionario operativo]]
[[#Mode — primary vs subagent]]
[[#Permissions — i tre livelli di accesso]]
[[#Model — scegliere il motore giusto]]
[[#Description — l'etichetta che decide il destino]]
[[#Esempi concreti — leggere l'anima di un agente]]
[[#Best practices — la saggezza di Atena]]
[[#Workflow — creare o rigenerare un agente]]
[[#Checklist rapida per nuovi agenti]]
[[#Governance e Aggiornamenti]]

---

## Il doppio volto di ogni agente

Ogni membro del Team Olimpo esiste in due forme, come una moneta con due facce:

| Forma | Percorso | Destinatario | Scopo |
|--------|-----------|--------------|-------|
| **Profilo descrittivo** | `Team/Members/<Nome>.md` | Umani | Chi è, cosa fa, confini |
| **File agente operativo** | `.opencode/agents/<nome>.md` | Claude Code (OpenCode) | Come agisce, istruzioni esecutive |

> **Regola d'oro di Atena**: un membro NON è operativo finché non possiede entrambi i file. Uno senza l'altro è solo metà di un essere vivente.

### La differenza sostanziale

Il **profilo descrittivo** è una presentazione: sintetica, leggibile, priva di istruzioni tecniche. Risponde alla domanda: *"A chi mi rivolgo?"*

Il **file agente** è un sistema operativo: contiene tutto ciò che Claude Code deve sapere per agire. È autosufficiente, non lascia nulla al caso o al contesto esterno non referenziato.

---

## Frontmatter agente — l'identità tecnica

Il frontmatter YAML in cima a `.opencode/agents/<nome>.md` è la **scheda tecnica** che OpenCode legge per decidere chi sei.

### Struttura minima

```yaml
---
name: poros
mode: primary
description: Orchestratore del Team Olimpo. Usa questo agente come punto di ingresso principale per qualsiasi richiesta.
model: xai/grok-code-fast-1
permission:
  read: allow
  edit: allow
  bash: ask
  task: allow
---
```

> **Nota di Calliope**: nota che `name` è in minuscolo, come il nome del file. L'identità tecnica segue la forma dello slug, non il nome proprio con maiuscola che usiamo nel corpo del documento.

---

## I campi del frontmatter — dizionario operativo

### `name`
- **Tipo**: stringa, lowercase
- **Significato**: identificativo univoco, deve corrispondere al nome del file (senza `.md`)
- **Esempio**: `poros`, `proteo`, `atena`

### `mode`
- **Tipo**: stringa
- **Valori possibili**: `primary` | `subagent`
- **Significato**: determina come l'agente interagisce con l'utente
  - `primary`: agente principale, l'utente può invocarlo direttamente (solo Poros attualmente)
  - `subagent`: agente specializzato, invocato via `@nome` o da altri agenti

### `description`
- **Tipo**: stringa (150-200 caratteri)
- **Significato**: **critica** — è il testo che Claude Code usa per decidere quando invocare l'agente
- **Regola d'oro**: deve contenere il **ruolo** E i **trigger d'uso** ("Usa quando...")
- **Anti-pattern**: description vaghe ("Aiuta con varie cose") o troppo restrittive ("Solo per YAML")

**Esempi a confronto:**

| ✅ Buona | ❌ Da evitare |
|----------|---------------|
| `Esperta documentazione e verifica conformità per il vault Obsidian del Team Olimpo. Conosce tutte le convenzioni del vault e verifica la qualità dell'output destinato all'utente.` | `Gestisce la documentazione.` |
| `Analista di processi e workflow per il Team Olimpo. Monitora l'evoluzione del sistema, documenta decisioni chiave, garantisce trasparenza operativa e traccia la provenienza delle modifiche.` | `Aiuta con i processi.` |

### `model`
- **Tipo**: stringa
- **Significato**: modello AI che alimenta l'agente
- **Valori comuni nel team**:
  - `xai/grok-code-fast-1` — veloce, efficace per compiti strutturati (Poros, Efesto)
  - `opencode/big-pickle` — bilanciato, adatto a ragionamento e ricerca (Proteo, Atena, Clio, Dike, Metis, Calliope)

### `permission`
- **Tipo**: oggetto YAML con campi annidati
- **Significato**: definisce cosa l'agente può fare nel filesystem e nel sistema

---

## Mode — primary vs subagent

### `mode: primary`
- **Chi**: solo Poros attualmente
- **Cosa significa**: l'agente è il punto di ingresso per l'utente
- **Comportamento**: può orchestrare, delegare agli altri, restituire risultati all'utente
- **Configurazione globale**: definito in `opencode.json` come `default_agent: "poros"`

### `mode: subagent`
- **Chi**: tutti gli altri membri (Proteo, Atena, Efesto, Clio, Dike, Metis, Calliope)
- **Cosa significa**: agente specializzato, mai esposto direttamente all'utente
- **Comportamento**: riceve compiti da Poros o da altri, produce output, non comunica con l'utente
- **Invocazione**: via `@nome-agente` nei messaggi o tasto Tab

> **Nota narrativa**: nel mito, Poros è il solo messaggero che parla agli dei e agli uomini. Gli altri abitano l'Olimpo e agiscono nel loro dominio specifico.

---

## Permissions — i tre livelli di accesso

Le permissioni controllano l'interazione con il filesystem e il sistema. Ogni agente ha un profilo tarato sulle sue necessità.

### I quattro verbi del potere

| Permesso | Valori | Cosa permette |
|----------|--------|---------------|
| `read` | `allow` / `deny` | Leggere file nel workspace |
| `edit` | `allow` / `deny` | Modificare o creare file |
| `bash` | `allow` / `ask` / `deny` | Eseguire comandi shell |
| `task` | `allow` / `deny` | Delegare ad altri agenti (solo per orchestratori) |

### Mappatura attuale del Team Olimpo

| Agente | read | edit | bash | task | Perché questo profilo |
|--------|------|------|------|------|---------------------|
| **Poros** | allow | allow | ask | allow | Orchestra: deve leggere tutto, coordinare, chiede conferma per bash |
| **Proteo** | allow | allow | deny | deny | Ricerca e scrive profili, non esegue codice né delega |
| **Atena** | allow | allow | deny | allow | HR Manager: crea agenti, delega a Calliope per i nomi |
| **Efesto** | allow | allow | ask | deny | Sviluppa script, chiede conferma per bash, non delega |
| **Clio** | allow | allow | ask | deny | Gestisce vault, verifica, non esegue codice |
| **Dike** | allow | allow | deny | deny | Analizza KBA, solo lettura e scrittura record |
| **Metis** | allow | deny | deny | deny | Thinking partner: solo lettura, non scrive né esegue |
| **Calliope** | allow | allow | deny | deny | Documentazione creativa, non esegue codice né delega |

### Cosa significa `bash: ask`
L'agente può eseguire comandi bash, ma **chiede conferma** prima di farlo. Protegge da esecuzioni accidentali. Poros e Efesto usano questo livello.

### Cosa significa `task: allow`
Solo chi deve orchestrare o collaborare può delegare. Attualmente: Poros (orchestratore) e Atena (delega a Calliope per i nomi).

---

## Model — scegliere il motore giusto

La scelta del modello non è estetica, è funzionale. Atena ha codificato questo criterio nel suo sistema di design:

### Matrice decisionale

| Modello | Quando usarlo | Esempi nel team |
|---------|---------------|-----------------|
| **xai/grok-code-fast-1** | Compiti strutturati, orchestrazione, sviluppo codice. Velocità ed efficienza. | Poros (orchestrazione), Efesto (sviluppo Python) |
| **opencode/big-pickle** | Ragionamento profondo, ricerca, analisi, sintesi creativa. Bilanciato. | Proteo (ricerca), Atena (design), Clio (verifiche), Dike (analisi KBA), Metis (strategia), Calliope (documentazione) |

**Regola di Atena**: se il compito richiede giudizio e il prompt non può coprire ogni caso, serve un modello più capace. Se il compito è procedurale e le istruzioni sono esaustive, il modello leggero basta.

---

## Description — l'etichetta che decide il destino

La `description` nel frontmatter è la stringa più importante dopo il nome. È ciò che Claude Code legge per decidere: *"Questo agente è adatto a questo compito?"*

### Anatomia di una description efficace

```
[RUOLO] + [azione principale] + [trigger d'uso espliciti]
```

### Esempi dal Team Olimpo

**Dike (Analista KBA)**:
```
Analista di processi e workflow per il Team Olimpo. Monitora l'evoluzione del sistema, documenta decisionsi chiave, garantisce trasparenza operativa e traccia la provenienza delle modifiche.
```

**Clio (Archivista)**:
```
Esperta di documentazione e verifica conformità per il vault Obsidian del Team Olimpo. Conosce tutte le convenzioni del vault e verifica la qualità dell'output destinato all'utente.
```

**Calliope (io stessa)**:
```
Specialista di nomenclatura mitologica del Team Olimpo. Ogni volta che il team deve dare un nome a qualcosa — un nuovo membro, un progetto, uno strumento, un concetto — sei tu a proporre il nome giusto.
```

### Anti-pattern da evitare

1. **Troppo vaga**: `"Aiuta con vari compiti"` → Claude Code non sa quando usarla
2. **Troppo restrittiva**: `"Solo per file YAML"` → esclude casi d'uso legittimi
3. **Duplicata**: due agenti con description simili → confuzione nel routing
4. **Solo poetica**: `"Porta la luce della saggezza"` → Claude Code non apprezza metafore, vuole operatività

---

## Esempi concreti — leggere l'anima di un agente

Analizziamo tre agenti per vedere come i pezzi si concatenano.

### 1. Poros — L'Orchestratore

```yaml
---
name: poros
mode: primary
description: Orchestratore del Team Olimpo. Usa questo agente come punto di ingresso principale per qualsiasi richiesta.
model: xai/grok-code-fast-1
permission:
  read: allow
  edit: allow
  bash: ask
  task: allow
---
```

**Perché funziona**:
- `mode: primary` → unico punto di ingresso
- `description` chiara: "punto di ingresso principale"
- `bash: ask` → non esegue senza conferma
- `task: allow` → può delegare a tutti

### 2. Proteo — Il Ricercatore

```yaml
---
description: Ricercatore Senior specializzato in analisi domini professionali e mappatura competenze. Produce profili strutturati per nuovi membri del team.
mode: subagent
model: opencode/big-pickle
permission:
  read: allow
  edit: allow
  webfetch: allow
  websearch: allow
---
```

**Perché funziona**:
- `webfetch` e `websearch` → deve navigare il web per la ricerca
- `edit: allow` → scrive i profili di competenze
- `task: deny` (implicito) → non delega ad altri
- `model: big-pickle` → bilanciato per ricerca e sintesi

### 3. Metis — Il Thinking Partner

```yaml
---
description: Esperta di strategia e ottimizzazione operativa per il Team Olimpo. Analizza processi, identifica colli di bottiglia e propone miglioramenti strutturali.
mode: subagent
model: opencode/big-pickle
permission:
  read: allow
---
```

**Perché funziona**:
- Solo `read: allow` → non scrive file, non esegue codice
- `edit` non serve → è un facilitatore di pensiero, non un esecutore
- Identità chiara: strategia e ottimizzazione

---

## Best practices — la saggezza di Atena

Atena, nel suo ruolo di HR Manager e Agent Designer, ha codificato principi che rendono un agente non solo funzionante, ma eccellente.

### 1. Autosufficienza del file agente
Ogni file agente deve contenere tutto ciò che serve per operare. Se l'agente ha bisogno di contesto esterno non referenziato, è incompleto.

### 2. Due documenti, due scopi
- **Profilo descrittivo** (`Team/Members/<Nome>.md`): risponde a *"chi è e cosa fa"* (per umani)
- **File agente** (`.opencode/agents/<nome>.md`): risponde a *"come lo fa"* (per Claude Code)
Non sono versioni della stessa cosa: hanno scopi e destinatari diversi.

### 3. Confini netti > competenze ampie
Un membro con confini chiari e competenze limitate è più utile di uno con competenze vaste ma confini ambigui. Meglio fare bene una cosa che farne molte in modo vago.

### 4. Struttura-tipo del file agente
Ordine non arbitrario — segue la priorità di lettura di Claude Code:

1. **Frontmatter** — identità tecnica
2. **Identità** — chi sei, missione (2-4 frasi)
3. **Personalità e stile** — tono, ritmo, atteggiamento
4. **Regole operative** — vincoli non negoziabili
5. **Competenze** — cosa sai fare e con quale profondità
6. **Processo operativo** — cosa fai, in che ordine, con quali verifiche
7. **Limitazioni** — cosa NON fai
8. **Formato di output** — struttura dell'output prodotto

### 5. Calibrazione della profondità
- Membro con dominio ristretto e procedurale (Clio, Calliope): istruzioni dettagliate ma concise
- Membro con dominio ampio che richiede giudizio (Metis, Dike): istruzioni più ricche, con principi e framework
- Lunghezza del prompt consuma contesto: se puoi dire la stessa cosa in meno parole senza perdere precisione, fallo

### 6. Anti-pattern comuni
- **Personalità decorativa**: descrivere un tono che le istruzioni operative contraddicono
- **Limitazioni vaghe**: "Non fare cose che non ti competono" non dice nulla
- **Processo senza passi**: "Analizza e produci" non è un processo
- **Competenze-lista**: elencare tecnologie senza spiegare come e quando usarle

---

## Workflow — creare o rigenerare un agente

Il processo di creazione di un nuovo membro segue un flusso preciso, orchestrato da Poros:

### Flusso di creazione (7 step)

1. **Briefing** (Poros): raccoglie competenze richieste e vincoli
2. **Analisi dominio** (Proteo): produce profilo di competenze in `Team/Handoff/`
3. **Scelta nome** (Calliope o Atena): associato al dominio, verificando `Team/Members/Registro.md`
4. **Profilo descrittivo** (Atena): crea `Team/Members/<Nome>.md`
5. **File agente** (Atena): crea `.opencode/agents/<nome>.md`
6. **Registro** (Atena): aggiorna `Team/Members/Registro.md`
7. **Archiviazione** (Atena): sposta handoff in `Team/Handoff/Archivio/`

> **Nota**: il membro è operativo solo al completamento degli step 4 e 5.

### Flusso di rigenerazione

Se un membro esistente necessita di aggiornamento:

1. Nuovo profilo di competenze (Proteo)
2. Lettura critica dei file attuali (Atena)
3. Confronto: cosa preservare, migliorare, aggiungere, rimuovere
4. Studio dei riferimenti (file agente più evoluti del team)
5. Produzione nuove versioni di entrambi i file
6. Aggiornamento Registro

---

## Checklist rapida per nuovi agenti

Prima di considerare un agente completo, verifica:

```markdown
[ ] Frontmatter presente con tutti i campi (name, mode, description, model, permission)
[ ] `name` in lowercase, corrispondente al nome del file
[ ] `description` contiene ruolo + trigger d'uso (150-200 caratteri)
[ ] `mode` corretto (primary/subagent)
[ ] Permission calibrati sul ruolo (non dare bash a chi non serve)
[ ] File agente autosufficiente (non dipende da contesto esterno non referenziato)
[ ] Profilo descrittivo creato in `Team/Members/<Nome>.md`
[ ] Registro aggiornato in `Team/Members/Registro.md`
[ ] Nome mitologico verificato (non usato, coerente col dominio)
[ ] Convenzioni vault rispettate (tags, aliases, wikilinks se produce output nel vault)
```

---

## Governance e Aggiornamenti

Come ogni organismo vivente, il Team Olimpo evolve. I documenti che ne definiscono l'architettura non sono scolpiti nel marmo, ma scritti su tavolette che possono essere aggiornate quando la saggezza lo richiede.

### Chi aggiorna la guida

La responsabilità degli aggiornamenti è distribuita secondo dominio e competenza:

- **Calliope** (io stessa): per tutto ciò che riguarda i **contenuti creativi** — nomenclatura, stile narrativo, tono, struttura delle sezioni di identità, esempi di scrittura. Se la guida deve raccontare meglio un concetto o acquisire una nuova voce, è compito mio.

- **Dike**: per tutto ciò che riguarda i **processi e la conformità** — flussi di lavoro, permessi, strutture decisionali, anti-pattern, verifiche di qualità. Se un processo cambia o richiede maggiore trasparenza, Dike interviene.

> **Principio di coerenza**: Calliope detta la forma, Dike garantisce la sostanza. Nessun aggiornamento è considerato completo se entrambi i piani — creativo e procedurale — sono stati ponderati.

### Quando aggiornare

La guida deve essere aggiornata in questi scenari:

1. **Nuove best practices**: quando Atena codifica nuovi principi di design agenti validati dall'esperienza operativa.
2. **Cambiamenti OpenCode**: quando il sistema sottostante introduce nuove funzionalità, campi nel frontmatter o muta il comportamento degli agenti.
3. **Evoluzione del Team**: quando nuovi membri entrano o i ruoli esistenti mutano significativamente.
4. **Correzioni**: errori rilevati nella documentazione, incongruenze tra file agente e guida.

### Come proporre un aggiornamento

Il flusso segue il principio di orchestrazione di Poros:

1. **Proposta**: chiunque individui una necessità di aggiornamento formula una proposta chiara (Calliope per creatività, Dike per processi, o qualsiasi membro che rilevi un problema).
2. **Verifica Poros**: la proposta passa a Poros, che valuta l'impatto sul sistema esistente e la coerenza con il resto della documentazione.
3. **Implementazione**: Poros delega l'aggiornamento al responsabile competente (Calliope o Dike).
4. **Revisione**: il responsabile aggiorna la guida seguendo le [convenzioni del vault]([[obsidian-vault]]).
5. **Pubblicazione**: la modifica viene salvata, verificata e integrata.

> **Nota di Calliope**: questo flusso non è burocrazia, è armonia. Poros assicura che ogni cambiamento serva al tutto, non al singolo.

---

## Note finali di Calliope

Questa guida non è un manuale tecnico freddo: è il racconto di come diamo forma a identità artificiali che abitano il nostro Olimpo digitale. Ogni agente è una scelta di parole, una calibrazione di tono, un confine nettamente tracciato.

Quando creerai o aggiornerai un agente, ricorda: **il nome giusto e la parola esatta cristallizzano l'identità**. Io, Calliope, sono qui per questo — ma spetta ad Atena plasmare l'intero essere.

Per convenzioni sul vault Obsidian (frontmatter, wikilinks, path immagini), consulta sempre [[obsidian-vault]].

Per il flusso di creazione dettagliato: [[flusso-creazione-membro]].

---

*Calliope, dalla bella voce, Musa dell'epica — Team Olimpo*
