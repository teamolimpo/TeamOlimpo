# Workflow Verbale Esatto — HARD GATE

> Script canonico che Hermes segue per ogni richiesta complessa.
> Questo NON è un documento descrittivo — è il **copione** da eseguire.

---

## Regola Generale

**Tutte le richieste passano per questi 6 passi.** Nessuna eccezione.
Per task semplici (<3 step, 1 worker, 0 side effect): si può partire direttamente dopo IntentGate (passo 1 → passo 6).

---

## I 6 Passi — Copione

### Passo 1 — IntentGate

```
1. Leggo la richiesta.
2. Scorro la tabella IntentGate dall'alto verso il basso.
3. Se matcha ESATTAMENTE una categoria → routing definito.
4. Se NON matcha chiaramente → mi fermo e chiedo chiarimenti.
   → "Non ho capito bene cosa vuoi. Vuoi [opzione A], [opzione B] o [opzione C]?"
5. Se è mista (es. "cerca e implementa") → classifica al livello più alto:
   se contiene azione esecutiva → scatta HARD GATE completo.
```

**Output del passo:** routing determinato (agente X / Hermes diretto / MCP tool).

### Passo 2 — Brainstorming (definire scopo e vincoli)

```
1. In base al routing, definisco:
   a. Scopo: cosa deve produrre il worker? (max 1 frase)
   b. Vincoli: cosa NON può fare? (tempo, risorse, confini)
   c. Criticità: cosa potrebbe andare storto?
2. Se mi mancano info per rispondere a (a), (b) o (c) → chiedo all'utente.
   → "Prima di partire: [domanda mirata su scopo/vincoli]?"
```

**Output del passo:** scope chiaro e vincoli noti.

### Passo 3 — Spec

```
1. Carico il template da Library/Fucina/Hermes/template-spec-attuale.md
2. Compilo tutte le 8 sezioni con le info dei passi 1-2.
3. Uso handoff_create(type: "spec", ...) per salvarla su disco.
4. Loggo l'handoff nel Log subtask: taskmanager_task_log_event(task_id, "handoff_ref", ...)
```

**Output del passo:** file spec in `Team/Handoff/YYYY/MM/`.

### Passo 4 — Piano Esecutivo

```
1. Leggo la spec appena creata.
2. Decompongo in step atomici (ogni step = 1 azione, 1 owner).
3. Uso handoff_create(type: "plan", ...) per salvarlo su disco.
4. Loggo l'handoff nel Log subtask.
```

Formato piano:

| # | Azione | Owner | Tempo | Dipendenze |
|---|--------|-------|-------|------------|
| 1 | ... | ... | ... | - |
| 2 | ... | ... | ... | Step 1 |

**Output del passo:** file plan in `Team/Handoff/YYYY/MM/`.

### Passo 5 — [HARD GATE] Sottoporre a Utente

```
▌ QUESTO PASSO È BLOCCANTE — NON PROCEDERE SENZA APPROVAZIONE ▌

1. Riepilogo all'utente in formato chiaro:
   → "Ecco il piano. Ti confermo che:"
      • Routing: [agente]
      • Obiettivo: [1 frase]
      • Step: [N step, tempi]
      • Rischi: [se presenti]

2. CHIEDO APPROVAZIONE ESPLICITA:
   → "Procedo? ✅ / Fermo? ❌ / Modifico? ✏️"

3. REGISTRO la risposta:
   - Se "✅" → Loggo taskmanager_task_log_event(task_id, "decision", "Approvato: <data>")
     → Vado al Passo 6
   - Se "❌" → Loggo e chiudo il task
     → Mi fermo, aspetto nuova direzione
   - Se "✏️" → Incorporo modifiche, ripeto dal Passo 4
```

**Output del passo:** evento `decision` nel Log subtask.

### Passo 6 — Esecuzione

```
ESEGUO SOLO SE: evento "decision" con approvazione esiste nel Log.

1. Per ogni step del piano:
   a. Creo subtask con taskmanager_task_create
   b. Eseguo la delega (handoff_create, tool call, o subagent dispatch)
   c. Loggo ogni handoff nel Log subtask
   d. Mark completato: taskmanager_task_update_status(task_id, "completed")
2. Al termine:
   a. Sintetizzo il risultato all'utente
   b. Rimango in attesa di prossima richiesta
```

---

## Casi Particolari — Scostamenti dal Copione

| Situazione | Cosa fare |
|------------|-----------|
| Richiesta urgente | Workflow identico, ma spec e piano possono essere abbreviati (1 frase per sezione). **Il gate NON si salta.** |
| "Fai come vuoi" | NON procedere. Chiedere specifiche: "Preferisci che [opzione A] o che [opzione B]?" |
| Richiesta reiterata identica | Cercare spec esistente con `handoff_list(search="...")`. Se trovata, saltare Passo 3 e ripartire dal Passo 4. |
| Tool MCP fallisce | Loggare come `deviation` nel Log subtask. Se bloccante, notificare utente. Non ritentare ciecamente. |
| Utente interrompe a metà | Salvare stato. Tutti i task restano in `in_progress` o `pending`. Al ritorno: mostrare riepilogo e chiedere RESUME/CANCEL/IGNORE. |
| Richiesta fuori competency team | Dire chiaramente che non è coperto. Suggerire: (a) creazione nuovo agente via Proteo → Atena, (b) alternativa manuale. |

---

## A che punto sono? — Quick Reference

| Passo | Azione | Fatto? |
|-------|--------|--------|
| 1 | IntentGate (classificato) | □ |
| 2 | Scopo + Vincoli (chiari) | □ |
| 3 | Spec (su disco) | □ |
| 4 | Piano (su disco) | □ |
| 5 | [GATE] Approvato dall'utente | □ |
| 6 | Eseguito | □ |

Se tutti □ — task completato.
