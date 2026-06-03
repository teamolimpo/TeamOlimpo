---
title: "OQ Recovery Template — Operative Qualification post-Recovery"
aliases: [oq, recovery, verifica, qualification, post-blocco, task-risposto]
tags: [meta, workflow, quality, oq, recovery, handoff]
---

# OQ Recovery Template — Operative Qualification

## Cos'è

L'**OQ (Operative Qualification) Recovery** è il processo di verifica che un blocco (deviazione) sia stato effettivamente risolto prima di riprendere il task originale. Non basta che il tool "sembra funzionare" — serve una verifica strutturata.

Questo template definisce i **3 criteri minimi** per dichiarare un task "rifatto" dopo un blocco.

---

## Quando usare questo template

Usa l'OQ Recovery quando:
- Un handoff è stato `bloccato` per deviazione
- Hai applicato un'azione correttiva
- Stai per riprendere il task (`stato: in-corso`) o dichiararlo completato

**Nota**: L'OQ Recovery non sostituisce il [[deviation-log-guida]]. È un complemento che verifica la risoluzione.

---

## I 3 criteri di verifica

### Criterio 1: Strumento verificato

Il tool che ha causato il blocco è **reattivo e funzionante**.

| Checkbox | Voce |
|----------|------|
| ☐ | Il tool/libreria/toolchain è stato testato con input semplice |
| ☐ | Il comando/tool esegue senza errori |
| ☐ | L'output atteso viene prodotto correttamente |

**Nota**: "Funzionante" significa che il tool fa quello che faceva prima del blocco. Non serve che faccia di più.

### Criterio 2: Condizioni rimosse

Le condizioni che hanno causato il blocco **non sono più presenti**.

| Checkbox | Voce |
|----------|------|
| ☐ | La causa specifica della deviazione è stata eliminata |
| ☐ | Non ci sono condizioni ambientali residue (path, permessi, dipendenze) |
| ☐ | Input identici a quelli che hanno causato il blocco ora funzionano |

**Nota**: Verifica con lo stesso input che ha causato il blocco. Non basta un input diverso.

### Criterio 3: Log analizzato

Il log dell'errore è stato **letto e compreso**.

| Checkbox | Voce |
|----------|------|
| ☐ | Il traceback/log dell'errore originale è stato esaminato |
| ☐ | La causa radice è identificata e documentata |
| ☐ | Non ci sono warning o errori residui nel log |

**Nota**: "Analizzato" non significa "ignorato". Devi capire cosa è successo e annotarlo.

---

## Formato tabellare

```
## OQ Recovery Verification

### 1. Strumento verificato
- [ ] Il tool è testato con input semplice
- [ ] Il tool esegue senza errori
- [ ] L'output atteso viene prodotto

### 2. Condizioni rimosse
- [ ] La causa del blocco è eliminata
- [ ] Condizioni ambientali OK
- [ ] Input originale ora funziona

### 3. Log analizzato
- [ ] Traceback esaminato
- [ ] Causa radice identificata
- [ ] Nessun errore residuo

### Note
[Spazio per note di verifica]

### Esito OQ
- [ ] Passato — Riprendi task
- [ ] Fallito — Non riprendere, risolvere prima
```

---

## Esempio compilato

### Caso: Tool failure — modulo mancante

**Handoff originale**: Conversione PDF con CLI
**Deviazione**: `tool_failure` — ModuleNotFoundError: 'loguru'

**OQ Recovery compilato**:

```markdown
## OQ Recovery Verification

### 1. Strumento verificato
- [x] Il tool è testato con input semplice → Testato con `uv run python -m tools.pdf_converter list`
- [x] Il tool esegue senza errori → Output: lista documenti visualizzata
- [x] L'output atteso viene prodotto → CLI risponde correttamente

### 2. Condizioni rimosse
- [x] La causa del blocco è eliminata → loguru reinstallata con `uv add loguru`
- [x] Condizioni ambientali OK → Dipendenza in requirements.txt
- [x] Input originale ora funziona → Stesso file PDF della deviazione convertito

### 3. Log analizzato
- [x] Traceback esaminato → ModuleNotFoundError in cli.py:22
- [x] Causa radice identificata → Dipendenza rimossa da requirements.txt
- [x] Nessun errore residuo → Zero warning, zero errori

### Note
La dipendenza era stata rimossa accidentalmente durante refactoring requirements.
Aggiunta ora a requirements.txt. Verificato con pip list.

### Esito OQ
- [x] Passato — Riprendi task
- [ ] Fallito — Non riprendere, risolvere prima
```

---

## Transizione di stato post-OQ

| Esito OQ | Azione |
|----------|--------|
| **Passato** | Aggiornare `stato` da `bloccato` a `in-corso` o `completato` |
| **Fallito** | Mantenere `stato: bloccato`, ripetere azione correttiva |

### Frontmatter dopo OQ passato

```yaml
---
data: 2026-03-24
mittente: poros
destinatario: clio
tipo: specifica
stato: in-corso
priorita: alta
titolo: "Conversione PDF KBA"

deviazione:
  tipo: "tool_failure"
  descrizione: "ModuleNotFoundError durante CLI"
  causa: "Dipendenza loguru mancante"
  azione_correttiva: "Reinstallata dipendenza"
  esito: "risolto"
  impatto_utente: false
---
```

---

## Checklist pre-completamento

Prima di dichiarare `stato: completato` un handoff che ha avuto deviazione:

- [ ] OQ Recovery compilato per ogni deviazione
- [ ] Tutti i 3 criteri sono passati
- [ ] Note documentate nel template
- [ ] frontmatter aggiornato con esito
- [ ] Causa radice in deviazione.causa

---

## Note

- L'OQ è **locale al singolo blocco**: se ci sono più deviazioni, ripeti la verifica per ognuna
- Non serve OQ per deviazioni con `esito: non_risolto` — sono già documentate come non risolvibili
- L'OQ è un processo interno, non un report all'utente

---

## Riferimenti

- [[deviation-log-guida]] — Guida deviation log
- [[handoff-guida]] — Sistema handoff completo
- [[acm-report-template]] — Template report settimanale ACM