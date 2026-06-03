---
title: "SOP — Design-First, Test-Gated Development Workflow"
tags: [sop, workflow, design, testing, quality]
date: 2026-05-20
---

# SOP: Design-First, Test-Gated Development

> *Prima si progetta, poi si implementa, poi si testa, poi si passa allo step successivo. Niente scorciatoie.*

---

## Principio

Ogni modifica sostanziale al sistema (nuovo tool, nuova automazione, modifica architetturale, nuovo agente) segue questo flusso obbligatorio. Non si scrive codice prima di aver progettato. Non si passa allo step successivo senza aver testato il precedente.

---

## Flusso Obbligatorio

### Fase 1: Design Document

Prima di scrivere **una riga di codice**, crea un design document che contiene:

```markdown
## Design: [Titolo]

### Obiettivo
Cosa vogliamo ottenere. Perché. Quale problema risolve.

### Architettura
Come funziona. Componenti, flusso dati, interfacce.

### Checklist Implementazione

- [ ] Step 1: [cosa] — *criterio di completamento: [test/verifica]*
- [ ] Step 2: [cosa] — *criterio di completamento: [test/verifica]*
- [ ] Step N: [cosa] — *criterio di completamento: [test/verifica]*

### Test
Come si verifica ogni step. Cosa deve succedere perché sia "fatto bene".
```

Il design document va in `Library/deliverables/<nome>.md` e diventa il task parent.

### Fase 2: Task Creation

Ogni step della checklist diventa un subtask del parent:

```
T-XXX-001  "[Design: Titolo]"                              (parent, in_progress)
  ├── T-XXX-002  "📝 Log"                                  (subtask, in_progress — MAI CHIUSO)
  ├── T-XXX-003  "Step 1: [cosa]"                          (subtask, pending)
  ├── T-XXX-004  "Step 2: [cosa]"                          (subtask, pending)
  └── T-XXX-005  "Step N: [cosa]"                          (subtask, pending)
```

### Fase 3: Implementazione Step-by-Step

Per ogni step:

1. `taskmanager_task_update_status("T-XXX-NNN", "in_progress")` — start step
2. Implementa (codice, configurazione, documentazione)
3. Esegui il test/verifica definito nel design document
4. Se il test fallisce → fix → ritenta
5. Se il test passa → spunta la checkbox nel design document
6. `taskmanager_task_update_status("T-XXX-NNN", "completed")` — step completato
7. `taskmanager_task_log_event("T-LOG-ID", "note", "Step N completato: [risultato test]")`
8. Passa allo step successivo

**Regola**: non si inizia lo step N+1 finché lo step N non è completato e testato.

### Fase 4: Chiusura

Solo quando **tutti** gli step sono completati:

1. Verifica che tutte le checkbox siano spuntate
2. Verifica che tutti i test passino
3. Segnala all'utente che il lavoro è completo
4. L'utente dice "chiudi" → chiudi il Log subtask → parent auto-completa

---

## Quando è Obbligatorio

Questo flusso è obbligatorio per:

- 🟢 Nuovo tool/automazione (Efesto)
- 🟢 Nuovo agente (Atena)
- 🟢 Modifica architetturale (MCP server, task manager, handoff)
- 🟢 Refactoring significativo
- 🟡 Modifica minore a tool esistente → design document breve, ma comunque presente
- ⚪ Bugfix urgente → si può bypassare, ma va documentata la deviazione

---

## Deviazioni

Se per qualsiasi motivo il flusso non può essere seguito (bugfix urgente, prototipo esplorativo):

1. Documenta la deviazione: `taskmanager_task_log_event("T-LOG-ID", "deviation", "motivo")`
2. Il design document può essere scritto dopo, ma **deve** essere scritto
3. I test rimangono obbligatori

---

## Template Minimo per Design Document Breve

Per modifiche minori:

```markdown
## Design: [Titolo]

**Obiettivo**: [una riga]
**Cosa cambia**: [file/componenti coinvolti]
**Checklist**:
- [ ] Step 1: ...
- [ ] Step 2: ...
```

---

## Changelog

| Data | Cosa |
|------|------|
| 2026-05-20 | Creazione SOP |
