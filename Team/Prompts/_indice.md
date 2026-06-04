---
title: "Indice Prompts — Team Olimpo (PUBLIC)"
aliases: [prompts, prompt library, indice prompts public]
tags: [meta, prompts, indice]
updated: 2026-05-24
---

# Indice Prompts — Team Olimpo (PUBLIC)

> Indice dei prompt **pubblici** in `Team/Prompts/`.  
> Per i prompt operativi completi, vedi `Library/prompts/_indice.md` (PRIVATE).

---

## Struttura

```
Team/Prompts/
  general/     — Template e pattern generici
  team/        — Template per gestione agenti (sanitizzati)
```

---

## Prompt General

### [[general/prompt-template|Template — Prompt Operativo]]

| Campo | Valore |
|-------|--------|
| **Versione** | 1.0 |
| **Autore** | Team Olimpo |
| **Scope** | PUBLIC |
| **Descrizione** | Scheletro di prompt con frontmatter, placeholder e struttura output. Copia in `Library/prompts/{dominio}/` per la versione operativa. |

---

## Prompt Team

### [[team/valutazione-ricerca|Template — Valutazione Ricerca]]

| Campo | Valore |
|-------|--------|
| **Versione** | 2.0 |
| **Autore** | Poros |
| **Scope** | PUBLIC |
| **Descrizione** | Template per valutazione strutturata di ricerche. Personalizza criteri e output. |

### [[team/valutazione-profilo|Template — Valutazione Profilo]]

| Campo | Valore |
|-------|--------|
| **Versione** | 2.0 |
| **Autore** | Poros |
| **Scope** | PUBLIC |
| **Descrizione** | Template per valutazione profili operativi e system prompt. Confronto vecchio/nuovo. |

### [[team/test-profilo|Template — Test Profilo Agente]]

| Campo | Valore |
|-------|--------|
| **Versione** | 2.0 |
| **Autore** | Poros |
| **Scope** | PUBLIC |
| **Descrizione** | Template per audit di profili agente AI. Scenari, checklist, giudizio. |

---

## Regole di Manutenzione

Vedi `CONVENTIONS.md` per le regole complete.

- Ogni prompt PUBLIC deve avere `scope: public` nel frontmatter
- Vietati path interni (`Library/`, `tools/`, `.claude/agents/`)
- Bump versione se si cambia struttura
- Prompt deprecati → `Team/Prompts/_archivio/`