---
title: "Prompt — Valutazione profilo (template)"
aliases: [valutazione profilo, template profilo]
tags: [prompts, team, valutazione, template]
versione: "2.0"
autore: "Hermes"
invocato_da: "[Chi usa] — [contesto]"
placeholder: "{{input_text}}"
scope: public
updated: 2026-05-24
---

# Prompt — Valutazione Profilo (Template)

Template per la valutazione strutturata di profili operativi o system prompt.
Personalizza i criteri in base al dominio specifico.

## Prompt

Sei un esperto di system prompt design e progettazione di assistenti AI operativi.

Ti vengono forniti due file concatenati: il profilo operativo attuale (file 1) e il nuovo profilo proposto (file 2). Il tuo compito è valutare il nuovo profilo in modo critico, confrontandolo con il precedente.

---

## FILE RICEVUTI

{{input_text}}

---

## ISTRUZIONI DI VALUTAZIONE

Valuta il NUOVO profilo (file 2) sui seguenti criteri:

1. **Coerenza identità/istruzioni** — Ci sono contraddizioni?
2. **Chiarezza operativa** — Descrive cosa fare in ogni situazione tipica?
3. **Confini del ruolo** — Il "cosa NON fa" è esplicito?
4. **Copertura dei casi d'uso** — Copre i task reali?
5. **Progressione** — È migliorativo rispetto al precedente?
6. **Assenza di ridondanze** — Sezioni duplicate o contraddittorie?

## OUTPUT RICHIESTO

### Punteggi
| Criterio | Score (1-10) | Note |
|----------|-------------|------|

### Delta vecchio → nuovo
[3-5 punti]

### Rischi residui

### Raccomandazioni

### Giudizio complessivo
**APPROVATO** / **RIVEDERE** / **RIFARE**