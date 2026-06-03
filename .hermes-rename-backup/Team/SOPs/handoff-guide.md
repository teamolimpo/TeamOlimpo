---
title: "Handoff — Agent Output Specification & Procedure"
aliases: [handoff-guide, handoff]
tags: [sops, handoff, workflow]
---

# Handoff — Agent Output Specification & Procedure

## Rule

Every agent invocation **must** end by writing one handoff file before returning control to Hermes. No exceptions.

---

## How to Create a Handoff

Use the `synapsis_hf(act="new", ...)` MCP tool with these parameters:

| Parameter | Required | Notes |
|-----------|----------|-------|
| `act` | ✅ | `"new"` per creare, `"get"` per leggere |
| `type` | ✅ | See [Valid types](#valid-types) |
| `title` | ✅ | Max 60 characters |
| `body` | ✅ | Free Markdown content |
| `agent` | ✅ | Lowercase agent name (e.g. `efesto`, `proteo`) |
| `task` | — | Assigned by Hermes at task start (e.g. `T-042`) |
| `note` | — | What was done, deviations, operational notes |
| `st` | — | `done` / `fail` / `hold` / `kill`. Default: `done` |
| `prio` | — | `high` / `med` / `low` / `crit`. Default: `med` |
| `refs` | — | File paths to artifacts produced |
| `devi` | — | See [Deviation block](#deviation-block) |

**Do not set**: `ref`, `data`, `timestamp`, `agent` in the body — the tool adds these automatically.

---

## Valid Types

| Type | Content |
|------|---------|
| `report` | Completed operation results, statistics |
| `profile` | Competency profile for a role or AI agent |
| `spec` | Technical specification, design decision |
| `test` | Test scenarios, acceptance criteria |
| `analysis` | Research output, strategic analysis |
| `note` | Non-actionable information, announcements |
| `bug` | Bug detected during execution — routes to Efesto |
| `feedback` | Non-bug quality signal: limitation, degradation |

---

## Valid Statuses

| st | Who | When |
|----|-----|------|
| `done` | Agent | Invocation finished with usable output |
| `fail` | Agent | Unresolvable blocker — output absent or partial |
| `hold` | Agent | Blocked but recoverable — awaiting dependency |
| `kill` | **Hermes only** | Never write this yourself |

**Rules:**
- `st: fail` or `st: hold` → `note` is **required**
- `deviation.outcome == 'open'` → `st` must be `fail`

---

## Body Template

Ogni handoff body DEVE seguire questa struttura. Le sezioni sono ordinate e consistenti tra tutti gli agenti.

```markdown
## Summary

[3-5 righe: cosa è stato fatto, per chi, risultato principale. Deve essere auto-contenuto.]

## Deliverable

- [file/output creato con path relativo]

## Key Findings

- [Finding concreto e verificabile]
- [Max 5 findings]

## Wiki                             # opzionale — vedi specifica sotto

kind: concept
title: Nome Pagina Wiki
path: concepts/2026/05/short-slug
summary: >-
  Sintesi 2-3 frasi, auto-contenuta, leggibile fuori contesto.
tags: [tag1, tag2]
sources:
  - "Library/Handoff/2026/06/03/codice-handoff.md"
confidence: CONFIRMED

## Deviations                       # opzionale — solo se deviazione dallo spec

- [descrizione deviazione]

## Next Steps                        # opzionale

- [azione successiva raccomandata]
```

---

## Wiki Section Specification

La sezione `## Wiki` è opzionale ma fortemente raccomandata per handoff di tipo `report`, `analysis`, `profile`, e `spec`. Quando presente, il server MCP handoff la parserà automaticamente per creare/aggiornare una pagina wiki in `Library/Wiki/`.

### Campi

| Campo | Obbligatorio | Valori | Note |
|-------|:-----------:|--------|------|
| `kind` | ✅ | `concept` / `entity` / `comparison` / `overview` / `decision` / `research` | Classifica il contenuto |
| `title` | ✅ | Stringa (max 60 char) | Titolo della wiki page |
| `path` | ✅ | `{kind}s/YYYY/MM/short-slug` | Relativo a `Library/Wiki/` |
| `summary` | ✅ | Testo 2-3 frasi (max 300 char consigliato) | Deve essere auto-contenuto |
| `tags` | — | Array di stringhe | Per ricerca FTS5 |
| `sources` | — | Array di path handoff | Provenienza |
| `confidence` | — | `CONFIRMED` / `PARTIALLY_CONFIRMED` / `UNCONFIRMED` | Default: CONFIRMED |

### When to include Wiki section

| Handoff type | Wiki raccomandata? | Note |
|:-----------:|:-----------------:|------|
| `report` | ✅ Consigliata | Se genera conoscenza nuova |
| `analysis` | ✅ Consigliata | Ricerca = conoscenza da preservare |
| `profile` | ✅ Consigliata | Profili agente/competenza |
| `spec` | 🔶 Se rilevante | Solo se decisione architetturale |
| `test` | ❌ | Solo se scopre pattern inaspettato |
| `note` | ❌ | Annunci, informazioni non strutturate |
| `bug` | ❌ | Solo se documenta workaround |
| `feedback` | ❌ | Segnali qualità, non conoscenza |

### Esempi

#### Con sezione Wiki (report/analysis)

```markdown
## Summary

Analizzati 6 repos per pattern handoff→wiki auto-generation. Nessun competitor diretto trovato. Pattern originale.

## Wiki

kind: research
title: Handoff to Wiki Auto-Generation Pattern
path: research/2026/05/handoff-to-wiki-pattern
summary: >-
  Discovery di competitor per pattern handoff strutturato con generazione
  automatica di wiki pages. Pattern originale di Team Olimpo.
tags: [chimera, handoff, wiki, discovery]
confidence: CONFIRMED
```

#### Senza sezione Wiki (note/bug)

```markdown
## Summary

Segnalato bug nel converter PDF: encoding issue su file nk-2400.

## Deliverable

- Nessuno — bug report

## Deviations

- Conversione fallita su file nk-2400-*.md per encoding non UTF-8
```

### Regole

- La sezione `## Wiki` è **opzionale**. La sua assenza non causa errori.
- Se presente, `kind`, `title`, `path`, e `summary` sono obbligatori.
- Il path wiki non deve sovrascrivere pagine esistenti (warning non bloccante).
- Non tutti gli handoff producono conoscenza wiki — usare il buon senso.

---

## `next_action`

One sentence addressed to Hermes. Required when `status: blocked`.

```yaml
# Route to specialist
next_action: "Hermes: suggest delegating encoding fix to Efesto before resuming T-042"

# Return to user
next_action: "Output ready for user. No further action needed."

# Blocked with recovery hint
next_action: "Hermes: blocked on missing loguru — requires Efesto fix before T-038 can resume"
```

---

## `quality_score`

Self-assessed by the producing agent.

| Score | Meaning |
|-------|---------|
| 1 | Unusable output |
| 2 | Partial or significantly flawed |
| 3 | Functional but improvable |
| 4 | Meets expectations |
| 5 | Exceeds expectations |

---

## `deviation` Block

Include when execution hit a blocker, error, or incomplete output.

```yaml
deviation:
  type: "tool_failure | output_incomplete | missing_input | other"
  description: "brief description"
  cause: "identified cause"
  corrective_action: "what was done to resolve"
  outcome: "resolved | workaround | open"
  user_impact: false
```

If `outcome: open` → `status: blocked` is mandatory.

---

## Examples

### A — Standard completed report

```yaml
# synapsis_hf(act="new", ...):
act: new
type: report
title: "Fixed loguru import in pdf_converter"
body: "47/50 files converted. 3 skipped: encoding issue in nk-2400-*.md."
agent: efesto
task: T-042
note: "Added loguru to pyproject.toml, all tests pass"
st: done
prio: med
```

### B — Blocked with bug

```yaml
# synapsis_hf(act="new", ...):
act: new
type: bug
title: "ModuleNotFoundError: loguru in pdf_converter"
body: "See deviation block for details."
agent: clio
st: fail
prio: high
note: "Blocked on missing dependency — delegate fix to Efesto before T-038 resumes"
devi: '{"type": "tool_failure", "description": "ModuleNotFoundError", "cause": "Missing dependency", "corrective_action": "None", "outcome": "open", "user_impact": true}'
```



## Tool Reference

Full CLI usage (`list`, filters, `--json`, `--paths`): `Team/Meta/tools/handoff/guide.md`
