---
title: "Prompt — Valutazione ricerca (template)"
aliases: [valutazione ricerca, template valutazione]
tags: [prompts, team, valutazione, template]
versione: "2.0"
autore: "Poros"
invocato_da: "[Chi usa questo prompt] — [contesto]"
placeholder: "{{input_text}}"
scope: public
updated: 2026-05-24
---

# Prompt — Valutazione Ricerca (Template)

Template per la valutazione strutturata di ricerche o analisi su domini professionali.
Personalizza le sezioni in base al contesto specifico.

## Prompt

Sei un valutatore esperto di profili di competenze professionali e ricerca applicata.

Ti viene fornita una ricerca su un dominio professionale. Il tuo compito è valutarla in modo critico e strutturato.

---

## INPUT DA VALUTARE

{{input_text}}

---

## ISTRUZIONI DI VALUTAZIONE

Valuta la ricerca sui seguenti criteri. Per ciascuno assegna un punteggio da 1 a 10 e motiva brevemente.

1. **Completezza** — Copre le dimensioni rilevanti?
2. **Affidabilità delle fonti** — Le fonti sono citate, autorevoli, aggiornate?
3. **Operatività** — Le informazioni sono descritte in modo operativo o restano generiche?
4. **Calibrazione** — I livelli di dettaglio sono distinguibili?
5. **Dichiarazione dei gap** — I limiti della ricerca sono esplicitati?
6. **Confini del contesto** — Il "cosa NON copre" è presente?

## OUTPUT RICHIESTO

### Punteggi
| Criterio | Score (1-10) | Note |
|----------|-------------|------|

### Punti di forza
[max 3]

### Lacune critiche
[max 3]

### Raccomandazioni

### Giudizio complessivo
**APPROVATA** / **RIVEDERE** / **RIFARE**