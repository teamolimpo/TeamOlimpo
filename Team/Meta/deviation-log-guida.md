---
title: "Deviation Log — Guida al tracking delle deviazioni"
aliases: [deviation, deviazione, deviation-log, tracking-errori, blocchi]
tags: [meta, workflow, quality, deviation, handoff]
---

# Deviation Log — Guida al tracking delle deviazioni

## Cos'è

Il **Deviation Log** è il sistema di tracciamento delle deviazioni nel flusso di lavoro del Team Olimpo. Una deviazione è qualsiasi **scostamento dal comportamento atteso** che impedisce il completamento standard di un task o handoff.

Il deviation log non sostituisce il bug report — è uno strumento **operativo** per documentare, classificare e risolvere i blocchi durante l'elaborazione.

### Distinzione con altri strumenti

| Strumento | Quando usarlo | Tipo di contenuto |
|-----------|---------------|-------------------|
| **Deviation Log** | Blocco durante l'elaborazione di un handoff | Scostamento, fallimento tool, timeout, formato errato |
| **Bug Report** | Difetto strutturale in un tool/script | Traceback, passi per riprodurre, fix richiesto |
| **Feedback** | Miglioramento suggerito | Cosa funziona / non funziona, suggerimento |

---

## Tipi di deviazione

Ogni deviazione viene classificata con un **tipo** che identifica la natura del blocco:

| Tipo | Descrizione | Esempio |
|------|-------------|---------|
| `output_incompleto` | L'output prodotto è parziale o mancante | Tool genera solo metà del risultato atteso |
| `tool_failure` | Il tool usato non esegue correttamente | CLI che crasha, modulo che non importa |
| `timeout` | L'operazione supera il tempo massimo | Operazione che non completa in tempo ragionevole |
| `errore_formato` | L'output non è nel formato atteso | Markdown malformato, JSON invalido |
| `altro` | Deviazione non categorizzabile sopra | Caso edge non previsto |

---

## Struttura della deviazione nel frontmatter

Quando un handoff incontra una deviazione, il frontmatter YAML deve includere il blocco `deviazione`:

```yaml
deviazione:
  tipo: "output_incompleto"
  descrizione: "breve descrizione della deviazione"
  causa: "causa identificata"
  azione_correttiva: "cosa fatto per risolvere"
  esito: "risolto"
  impatto_utente: false
```

### Campi del blocco deviazione

| Campo | Tipo | Obbligatorio | Valori | Descrizione |
|-------|------|--------------|--------|-------------|
| `tipo` | Testo | Sì | Vedi tabella tipi sopra | Categoria della deviazione |
| `descrizione` | Testo | Sì | Stringa libera | Descrizione sintetica del problema |
| `causa` | Testo | Sì | Stringa libera | Causa identificata o ipotesi |
| `azione_correttiva` | Testo | Sì | Stringa libre | Azione intrapresa per risolvere |
| `esito` | Testo | Sì | `risolto`, `non_risolto`, `workaround` | Stato finale della deviazione |
| `impatto_utente` | Booleano | Sì | `true`, `false` | L'utente ha visto l'errore? |

---

## Workflow operativo

### 1. Rilevamento della deviazione

Quando un membro (destinatario dell'handoff) incontra un blocco:

1. **Non completare** l'handoff con `stato: completato`
2. **Documentare** la deviazione nel frontmatter
3. **Aggiornare** lo stato a `bloccato`

### 2. Documentazione della deviazione

Aggiornare il frontmatter esistente con il blocco `deviazione`:

```yaml
---
data: 2026-03-24
mittente: poros
destinatario: clio
tipo: specifica
stato: bloccato
priorita: alta
titolo: "Conversione PDF KBA"

deviazione:
  tipo: "tool_failure"
  descrizione: "Il converter crasha durante l'estrazione delle immagini"
  causa: "Dipendenza PIL mancante nell'ambiente di esecuzione"
  azione_correttiva: "Installata dipendenza, riavviato il tool"
  esito: "risolto"
  impatto_utente: false
---
```

### 3. Risoluzione della deviazione

Dopo aver risolto il problema:

1. **Verificare** che il task possa proseguire
2. **Aggiornare** i campi `esito` e `azione_correttiva`
3. **Cambiare** `stato` da `bloccato` a `in-corso` o `completato`
4. **Documentare** nel corpo dell'handoff cosa è stato fatto

### 4. Caso con workaround

Se la deviazione è risolta con un workaround (soluzione temporanea):

```yaml
deviazione:
  tipo: "errore_formato"
  descrizione: "Output JSON malformato"
  causa: "Encoding non supportato dal parser"
  azione_correttiva: "Convertito manualmente l'output in txt, workaround applicato"
  esito: "workaround"
  impatto_utente: true
```

---

## Esempi pratici

### Esempio 1: Tool failure — modulo mancante

```yaml
deviazione:
  tipo: "tool_failure"
  descrizione: "ModuleNotFoundError: 'loguru' durante esecuzione CLI"
  causa: "Dipendenza rimossa da requirements.txt"
  azione_correttiva: "Reinstallata dipendenza con uv add loguru"
  esito: "risolto"
  impatto_utente: false
```

### Esempio 2: Output incompleto

```yaml
deviazione:
  tipo: "output_incompleto"
  descrizione: "Solo 3 su 10 KBA convertite"
  causa: "Il parser incontra caratteri non ASCII e salta il record"
  azione_correttiva: "Aggiunto pre-processing per pulizia caratteri, rilanciato task"
  esito: "risolto"
  impatto_utente: false
```

### Esempio 3: Timeout

```yaml
deviazione:
  tipo: "timeout"
  descrizione: "La conversione di file >10MB non completa in 120s"
  causa: " Nessuna gestione timeout nel converter, file troppo grande"
  azione_correttiva: "Split del file in chunk, processato separatamente"
  esito: "workaround"
  impatto_utente: true
```

### Esempio 4: Errore formato

```yaml
deviazione:
  tipo: "errore_formato"
  descrizione: "Il Markdown generato manca di frontmatter"
  causa: "Il template non include frontmatter per file senza metadati"
  azione_correttiva: "Aggiunto frontmatter generico manualmente"
  esito: "risolto"
  impatto_utente: false
```

---

## Integrazione con il sistema handoff

### Frontmatter handoff completo con deviazione

```yaml
---
data: 2026-03-24
mittente: poros
destinatario: clio
tipo: specifica
stato: bloccato
priorita: alta
titolo: "Conversione batch KBA"

deviazione:
  tipo: "tool_failure"
  descrizione: "CLI crasha su file con caratteri speciali"
  causa: "Encoding non gestito nel parser"
  azione_correttiva: "Patch temporanea applicata, da verificare con Efesto"
  esito: "workaround"
  impatto_utente: true
---
```

### Transizioni di stato con deviazione

| Stato iniziale | Deviazione | Stato finale |
|---------------|------------|--------------|
| `in-corso` | Si rileva blocco | `bloccato` |
| `bloccato` | Deviazione risolta | `in-corso` |
| `bloccato` | Deviazione non risolvibile | `bloccato` (documentare in corpo) |
| `in-corso` | Deviazione risolta con workaround | `completato` (con note) |

---

## Raccomandazioni operative

1. **Non nascondere le deviazioni**: ogni blocco va documentato, anche se risolto rapidamente
2. **Sii specifico nella causa**: "non funziona" non è sufficiente, indica cosa non funziona e perché
3. **Distingu workaround da risoluzione**: se usi un workaround, indica `esito: workaround` e documenta il motivo
4. **Traccia l'impatto utente**: se `impatto_utente: true`, significa che l'utente finale ha visto l'errore — questo è un segnale di qualità
5. **Aggiorna sempre i campi**: una deviazione senza esito o causa è inutile per il tracking

---

## Query e analisi

Per trovare tutte le deviazioni nel sistema:

```bash
# Cerca tutti i file handoff con deviazione
grep -r "deviazione:" Team/Handoff/ --include="*.md" -l
```

Per filtrare per tipo o esito, cerca nel frontmatter.

---

## Riferimenti

- [[handoff-guida]] — Sistema handoff completo
- [[handoff-register-guida]] — Script di registrazione
- [[oq-recovery-template]] — Template OQ per verifica recovery
- [[acm-report-template]] — Template report settimanale ACM