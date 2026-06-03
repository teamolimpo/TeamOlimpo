---
title: "Prompt — Test profilo agente (template)"
aliases: [test profilo, template audit agente]
tags: [prompts, team, test, template]
versione: "2.0"
autore: "Poros"
invocato_da: "[Chi usa] — audit periodico o dopo modifiche"
placeholder: "{{input_text}}"
scope: public
updated: 2026-05-24
---

# Prompt — Test Profilo Agente (Template)

Template per audit di profili agente AI operativi. Personalizza scenari e criteri in base al contesto.

## Prompt

Sei un esperto di system prompt design e progettazione di assistenti AI operativi.

Ti viene fornito il profilo operativo completo di un agente AI. Il tuo compito è valutarlo criticamente come se lo stessi leggendo per la prima volta.

---

### PROFILO DA TESTARE

{{input_text}}

---

### ISTRUZIONI DI VALUTAZIONE

### 1. Test di chiarezza operativa
Rispondi: Chi è? Cosa fa? Cosa NON fa? Come lavora? Con chi interagisce?

### 2. Test di coerenza interna
Identifica eventuali contraddizioni o ridondanze.

### 3. Test dei casi limite
Proponi 3 scenari concreti. Per ciascuno: il profilo è sufficiente? Cosa manca?

### 4. Test di completezza
Verifica la presenza di: identità chiara, competenze core, confini, flussi di lavoro, gestione ambiguità, regole handoff, lingua specificata.

### OUTPUT RICHIESTO

### Identità del profilo

### Test chiarezza operativa
| Domanda | Risposta | Giudizio |

### Contraddizioni rilevate

### Scenari di test
**Scenario 1**: [task] — sufficiente: sì/no — Gap:

### Checklist completezza

### Punti di forza [max 3]

### Lacune prioritarie [max 3]

### Giudizio complessivo
**SOLIDO** / **MIGLIORABILE** / **DA RIVEDERE**

### Raccomandazioni specifiche