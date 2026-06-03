# Template Spec Definitivo — Hermes

> Template canonico per la creazione di Spec via `handoff_create(type: "spec")`.
> Usa sempre questo scheletro. Ogni sezione è obbligatoria — se non applicabile, scrivi "N/A" con motivazione.

---

## Struttura YAML Frontmatter

```yaml
---
title: "<Titolo descrittivo>"
type: spec
status: draft
task_id: "<T-ID>"
version: 1
date: <YYYY-MM-DD>
tags: [<tag1>, <tag2>]
---
```

## Sezioni

### 1. Obiettivo

Una frase che risponde a: **cosa vogliamo ottenere?** Massimo 3 righe. Nessun dettaglio implementativo.

> Esempio: *Rendere Team Olimpo più deterministico attraverso modifiche a leva alta al prompt di Hermes, con routing rigido, confini espliciti e workflow a gate.*

### 2. Contesto

Perché stiamo facendo questo? Quale problema risolve? Chi sono gli attori coinvolti? Quali evidenze o decisioni precedenti ci sono?

- Link a documenti rilevanti (spec precedenti, handoff, wiki)
- Riferimenti a pattern osservati in altri progetti se pertinenti
- Dolore o opportunità che ha generato la richiesta

### 3. Vincoli

Elenco puntato di ciò che **non possiamo** fare o che **dobbiamo** rispettare. Per ogni vincolo, chiedersi: "Se lo infrangiamo, il progetto fallisce?"

Esempi:
- Tempo: completabile in <X ore/giorni
- Nessun nuovo layer software (DB, server, API)
- Solo tool MCP esistenti
- Retrocompatibilità con casi d'uso esistenti
- Budget cognitivo: non aumentare la lunghezza del prompt oltre X%

### 4. Approcci Considerati

Almeno 2 approcci alternativi con trade-off espliciti. Massimo 4. Per ognuno:

**Nome:** `<breve descrizione>`
- **Come funziona:** 1-2 righe
- **Pro:** 1-2 punti
- **Contro:** 1-2 punti
- **Verdetto:** ✅ Scelto / ❌ Scartato / 🔶 Riserva

Se uno è scelto, la sezione 5 lo dettaglia. Se nessuno è chiaramente migliore, dirlo.

### 5. Approccio Scelto

Descrizione dell'approccio selezionato dalla sezione 4. Perché questo e non gli altri? Quale trade-off ha fatto pendere la bilancia?

### 6. Specifica (Dettaglio)

La carne. Deve essere sufficientemente dettagliata da poter essere implementata senza tornare a chiedere chiarimenti. Include:

- **Comportamento atteso** — passo passo
- **Formati, strutture, naming conventions**
- **Edge cases** — almeno 3-5 (cosa succede se X va male? se l'input è Y? se lo strumento Z non risponde?)
- **Interazioni con altri sistemi** (taskmanager, handoff, kb_search, MCP tools)
- **Esempi concreti** se aiuta la chiarezza

### 7. Criteri di Successo

Come facciamo a sapere che abbiamo finito e che funziona? Criteri verificabili, non opinioni.

- **Testing:** cosa testare e come
- **Metriche:** se applicabile (es. "tempo medio di risposta < 30s")
- **Checklist di verifica:** punti da spuntare per dichiarare completato

### 8. Non Fare (Confini)

Cosa è esplicitamente **fuori scope**. Questa sezione è importante quanto l'obiettivo — evita creep e aspettative errate.

- NON fare X
- NON estendere a Y senza discussione
- NON toccare Z

---

## Verifica Pre-Rilascio

Prima di salvare la spec, controlla:
- [ ] Ogni sezione è compilata (o motivata "N/A")
- [ ] Almeno 2 approcci considerati in sezione 4
- [ ] Edge cases coprono input anomali + fallimenti tool + casi limite
- [ ] Criteri di successo sono verificabili (non "funziona bene" ma "3/3 test passano")
- [ ] Confini sono chiari e specifici
- [ ] Frontmatter YAML è valido
