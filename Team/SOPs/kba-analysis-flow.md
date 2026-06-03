---
title: KBA Analysis Flow
aliases: [kba-analysis-flow, kba-gap-flow]
tags: [sops, kba, dike]
---

# KBA Analysis Flow

Step validati uno alla volta. Ogni step viene aggiunto qui solo dopo essere stato testato.

---

## Step 1 — Gap check

```bash
uv run python -m tools.kba_merger gap Inbox/<export.xlsx> --recursive
```

Classifica ogni KBA in:
- `ok` — record in catalogo e MD non modificato
- `da_rianalizzare` — record in catalogo ma MD più recente (riconvertito)
- `da_analizzare` — MD presente ma nessun record
- `da_convertire` — nessun MD trovato

Output: `Library/deliverables/kba_gap_<data>.txt` + `.xlsx`

---

## Step 2 — Convertire PDF

```bash
uv run python -m tools.pdf_converter convert-all --inbox /mnt/hgfs/KBA
```

Converte PDF nuovi/modificati in `lib/documents/<slug>.md`.
Rileva automaticamente i file già convertiti (hash) e li salta. Se un PDF è stato modificato, lo riconverte.

---

## Step 3 — Gap check (verifica)

```bash
uv run python -m tools.kba_merger gap Inbox/<export.xlsx> --recursive
```

Rilancia gap check per vedere lo stato aggiornato dopo la conversione.
