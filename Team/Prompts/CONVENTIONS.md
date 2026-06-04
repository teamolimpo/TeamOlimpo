---
title: "CONVENTIONS — Prompt Library Team Olimpo"
tags: [meta, prompts, conventions]
updated: 2026-05-24
---

# CONVENTIONS — Prompt Library

Regole di scrittura e manutenzione per i prompt del Team Olimpo.

---

## 1. Path — Split Duale

| Scope | Path | Contenuto |
|-------|------|-----------|
| PUBLIC 🔓 | `Team/Prompts/` | Pattern, template vuoti, convenzioni, esempi generici |
| PRIVATE 🔒 | `Library/prompts/` | Prompt operativi reali con path interni e placeholders |

---

## 2. Naming Convention

```
{dominio}-{scopo}.md
```

- **Dominio**: `team`, `general` (corrisponde alla directory)
- **Scopo**: trattino singolo, lowercase, max 4 parole
- **Ok**: `valutazione-ricerca.md`, `analisi-impatto.md`, `prompt-template.md`
- **Vietato**: underscore, camelCase, spazi, numeri in sequenza

---

## 3. Frontmatter Obbligatorio

```yaml
---
title: "Prompt — {Nome descrittivo}"
tags: [prompts, {dominio}, {argomento}]
versione: "1.0"
autore: "{nome agente}"
invocato_da: "{chi} — {quando}"
placeholders: ["{{var1}}", "{{var2}}"]
scope: public|private
updated: YYYY-MM-DD
---
```

**Campi REQUIRED**: `title`, `tags`, `versione`, `autore`, `invocato_da`, `scope`

---

## 4. Placeholder

- Usare **doppia mustache**: `{{var_name}}`
- Nomi descrittivi in snake_case
- Esempi: `{{input_text}}`, `{{kba_text}}`, `{{rules_context}}`

---

## 5. Prompt PUBLIC — Cosa NON mettere

Nei prompt `scope: public` è VIETATO:

- Path a `Library/`, `tools/`, `.claude/agents/`
- Referimenti a strumenti interni (`llm`, `kba_merger`)
- Nomi reali di persone o clienti
- Placeholder che rivelano strutture dati interne

I prompt PUBLIC devono essere template anonimizzati o esempi generici.

---

## 6. Versioning (SemVer)

| Cambiamento | Bump |
|------------|------|
| Cambio struttura output, criteri, framework | Major (`2.0`) |
| Aggiunta criteri, esempi, affinamenti | Minor (`1.1`) |
| Correzioni minori, formattazione | Patch (`1.0.1`) |

Dopo ogni major/minor, rieseguire test su 3 input noti.

---

## 7. Ciclo di Vita

1. **Nuovo prompt**: creare in `Library/prompts/{dominio}/` con scope appropriate
2. **Modifica**: bump versione, aggiornare `updated`
3. **Deprecazione**: spostare in `Library/prompts/_archivio/` o `Team/Prompts/_archivio/`
4. **Eliminazione**: non cancellare mai — archiviare

---

## 8. Indici

- `Team/Prompts/_indice.md` — elenca SOLO prompt `scope: public`
- `Library/prompts/_indice.md` — elenca TUTTI i prompt con flag scope
- Gli indici vanno aggiornati OGNI volta che si aggiunge/modifica/depreca un prompt