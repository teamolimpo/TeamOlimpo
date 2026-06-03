---
title: ADQ Checklist — Agent Design Qualification
tags: [aqf, template, checklist, design-review]
aqf_stage: ADQ
version: 1.0
created: 2026-05-16
author: Atena (Team Olimpo)
status: operativo
---

# ADQ Checklist — Agent Design Qualification

Template di design review per nuovi membri del Team Olimpo. Compilato da **Atena** e validato da **Poros** prima dell'attivazione di un nuovo agente.

---

## 1. Frontmatter YAML

File agente in `.opencode/agents/<nome>.md`:

- [ ] `description` — stringa operativa (~150-200 caratteri) che distingue l'agente in modo non ambiguo da tutti gli altri
- [ ] `mode` — corretto per il tipo di agente (`primary`, `subagent`, `all`)
- [ ] `model` — calibrato alla complessità del ruolo (opus per giudizio, sonnet per efficienza, haiku/hot per procedurali)
- [ ] `permission` — include solo i tool necessari, nessun tool superfluo
- [ ] Assenza di campi custom obsoleti (`tools:`, `name:`, `archetipo:`, `tags:`)
- [ ] Assenza di formato `tools:` — usare solo `permission:` con `bash:`, `edit:`, `read:`, `task:`, `webfetch:`, `websearch:`

> **Riferimento**: `opencode.json` per configurazione globale, `.opencode/agents/` per file esistenti.

---

## 2. Identità e Personalità

- [ ] Nome mitologico assegnato (coerente con schema del team, preferenza greco)
- [ ] Identità definita in 2-4 frasi: chi è, missione nel team, origine mitologica
- [ ] Personalità calibrata alla funzione (tono, ritmo, atteggiamento, linguaggio)
- [ ] Assenza di contraddizioni tra personalità dichiarata e istruzioni operative
- [ ] Sezione "Chi sono" presente (per umani: identità, cosa fa, cosa non fa — 2-3 paragrafi)

> **Criterio**: un umano deve capire il ruolo in 30 secondi leggendo la sezione "Chi sono". Un agente Claude Code deve poter operare senza ambiguità leggendo il resto del file.

---

## 3. Competenze

- [ ] Competenze mappate su operazioni concrete, non generiche
- [ ] Per ogni competenza: descrizione operativa (cosa fare, come, quando)
- [ ] Competenze non sovrapposte con altri membri del team
- [ ] Gap informativi dichiarati (cosa il membro NON sa fare)
- [ ] Se il membro interagisce con il vault Obsidian: riferimento a `Team/SOPs/obsidian-vault-conventions.md`

> **Anti-pattern**: "competenze-lista" — elencare tecnologie senza spiegare come e quando usarle. Ogni competenza deve avere contesto d'uso.

---

## 4. Istruzioni Operative (Cosa fare / Cosa NON fare)

- [ ] Processo operativo con passi numerati (input → azione → output per ogni passo)
- [ ] Regole operative chiare: vincoli non negoziabili, lingua, protocolli
- [ ] Limitazioni esplicite: cosa NON fare, confini del ruolo, quando rifiutare un task
- [ ] Criteri di qualità per ogni output prodotto
- [ ] Sezioni obbligatorie presenti: identità, personalità, regole operative, competenze, processo operativo, limitazioni, interazioni

> **Anti-pattern**: "Processo senza passi" — "Analizza e produci output" non è un processo. Ogni passo deve avere input, azione, output.
> **Anti-pattern**: "Limitazioni vaghe" — "Non fare cose che non ti competono" non è una limitazione. Elencare esplicitamente.

---

## 5. Limiti e Confini

- [ ] Scenario di escalation definito (quando e come rifiutare un task)
- [ ] Confini rispetto ad altri membri del team (cosa fa questo vs cosa fanno gli altri)
- [ ] Dichiarazione esplicita di ciò che NON rientra nel dominio
- [ ] Barriere di sicurezza: l'agente non deve poter eseguire operazioni distruttive senza verifica

> **Principio**: "Confini netti > competenze ampie" — un membro con confini chiari e competenze limitate è più utile di uno con competenze vaste ma confini ambigui.

---

## 6. Tool Abilitati

- [ ] Tool concessi coerenti con le competenze dichiarate
- [ ] `bash: allow` solo se l'agente deve eseguire comandi shell
- [ ] `task: allow` solo se l'agente deve delegare ad altri agenti
- [ ] `webfetch`/`websearch` solo se l'agente fa ricerca esterna
- [ ] Nessun tool negato che è necessario al ruolo

| Ruolo | Tool tipici |
|-------|-------------|
| Scrive codice/file | `Read, Write, Edit, Glob, Grep, Bash` |
| Ricerca e analisi | `Read, Write, Glob, Grep, WebSearch, WebFetch` |
| Delega ad altri agenti | `Read, Write, Edit, Glob, Grep, Task` |
| Solo consultazione (read-only) | `Read, Glob, Grep` |

---

## 7. Guiding Documents

- [ ] Riferimenti a documenti guida presenti e accessibili
- [ ] Se membro produce output per vault: riferimento a `Team/SOPs/obsidian-vault-conventions.md`
- [ ] Se membro segue convenzioni specifiche: path del documento di riferimento inserito nel file agente
- [ ] Riferimenti a guide tecniche pertinenti (es. `Team/Meta/pdf-converter-guida.md`, `Team/SOPs/handoff-guide.md`)

> **Principio**: "Pattern briefing + riferimento" — non spiegare tutte le convenzioni nel prompt. Puntare al documento di riferimento, evidenziare solo i punti critici.

---

## 8. Risk Classification

| Campo | Valore |
|-------|--------|
| **risk_class** | [Alto / Medio / Basso] |
| **Livello AQF richiesto** | [vedi tabella] |
| **Motivazione** | (spiegare perché questa classe, con riferimento ai criteri AQF) |

### Criteri di assegnazione

| Classe | Criterio | Livello AQF |
|--------|----------|-------------|
| **Alto** | Impatto diretto su output utente finale, orchestrazione, dati critici | ADQ completo + AEQ + AOQ + APQ + ACM |
| **Medio** | Impatto su qualità vault o processi interni, ma non direttamente su utente | ADQ essenziale + AOQ + ACM |
| **Basso** | Produzione contenuti tematici, task ben delimitati | ADQ minimo + ACM leggero |

---

## 9. Traceability Matrix

Requisito → Test di qualifica (OQ) → Esito. Compilata al completamento dell'agent design.

| ID | Requisito | Test OQ | Esito | Note |
|----|-----------|---------|-------|------|
| R-01 | Frontmatter YAML valido e completo | Lettura parsing OpenCode | ⬜ | |
| R-02 | Identità e personalità definite | Review umana (Poros) | ⬜ | |
| R-03 | Competenze mappate su operazioni concrete | Verifica Atena | ⬜ | |
| R-04 | Processo operativo con passi numerati | Lettura file agente | ⬜ | |
| R-05 | Limitazioni esplicite e confini chiari | Lettura file agente | ⬜ | |
| R-06 | Tool coerenti con competenze | Verifica permission vs competenze | ⬜ | |
| R-07 | Riferimenti a guiding documents (se applicabile) | Verifica path documenti | ⬜ | |
| R-08 | Risk class assegnata e motivata | Validazione Poros | ⬜ | |
| R-09 | Assenza campi custom obsoleti nel frontmatter | Parsing OpenCode | ⬜ | |
| R-10 | Sezione "Chi sono" presente e leggibile | Review umana | ⬜ | |

> **Nota**: i test OQ (Operational Qualification) verificano che l'agente risponda ai requisiti di design. Test più approfonditi (PQ — Performance Qualification) sono gestiti nella fase AOQ.

---

## 10. Sign-off

| Ruolo | Nome | Data | Firma |
|-------|------|------|-------|
| **Designer** | Atena | | |
| **Reviewer** | Poros | | |
| **Approvatore** | Poros | | |

### Verifica finale

- [ ] Checklist completata e verificata
- [ ] Traceability matrix: tutti i test OQ superati
- [ ] Risk class assegnata e concordata
- [ ] File agente salvato in `.opencode/agents/<nome>.md`
- [ ] Registro aggiornato in `Team/Members/Registro.md`
- [ ] Handoff da Proteo archiviato in `Team/Handoff/Archivio/`

---

## Appendice: Riferimenti AQF

| Sigla | Nome | Descrizione |
|-------|------|-------------|
| **ADQ** | Agent Design Qualification | Design review del file agente (questa checklist) |
| **AEQ** | Agent Evaluation Qualification | Valutazione delle competenze dichiarate |
| **AOQ** | Agent Operational Qualification | Verifica operativa dell'agente in esecuzione |
| **APQ** | Agent Profiling Qualification | Profilazione dinamica del comportamento |
| **ACM** | Agent Continuous Monitoring | Monitoraggio continuo e audit periodici |

---

*Template ADQ v1.0 — Progettato da Atena per il Team Olimpo. Riferimento: `Team/Members/Registro.md` per risk classification completa.*
