---
title: "Template — Prompt Operativo"
tags: [prompts, template, conventions]
versione: "1.0"
autore: "Team Olimpo"
invocato_da: "[Chi usa questo prompt] — [contesto/step]"
placeholders: ["{{input_text}}", "{{variabile}}"]
scope: public
updated: 2026-05-24
---

# Prompt — [Nome Descrittivo]

[Contesto / identità del valutatore in 1-3 righe]

---

## INPUT

{{input_text}}

---

## ISTRUZIONI

1. [Istruzione 1]
2. [Istruzione 2]
3. [Istruzione 3]

## OUTPUT RICHIESTO

### Sezione 1
[formato atteso]

### Sezione 2
[formato atteso]

### Giudizio complessivo
**APPROVATO** / **DA RIVEDERE** / **RIFIUTATO**

---

> **Nota:** Copia questo template in `Library/prompts/{dominio}/` per la versione operativa.
> I placeholder in doppia mustache `{{var}}` sono sostituiti al momento dell'invocazione.