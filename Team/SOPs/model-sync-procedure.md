---
title: Model Sync Procedure
aliases: [model-sync-procedure, sync-models, aggiorna-modelli]
tags: [sops, poros, proteo, modelli, prezzi, routing]
---

# Model Sync Procedure

Procedura per aggiornare `KNOWN_PRICES` e la mappa di routing con i prezzi correnti da OpenRouter API, **inclusa l'analisi Proteo** su quali modelli usare per cosa.

## Trigger

L'utente dice una delle seguenti:

- "Poros, aggiorna lista modelli"
- "sync prices"
- "update models"
- "refresh prezzi"
- "check prezzi attuali"
- "fai un sync dei modelli"

## Output

1. `KNOWN_PRICES` in `tools/llm/config.py` aggiornato con i prezzi reali
2. `Library/Wiki/team/routing-map.md` aggiornata da Proteo con classificazione e raccomandazioni
3. Report all'utente: tabella prezzi + raccomandazioni su cosa usare

## Workflow

### Step 1 — Fetch models

Esegui:

```bash
curl -s https://openrouter.ai/api/v1/models \
  -H "Authorization: Bearer $OPENROUTER_API_KEY"
```

Estrai per ogni modello: `id`, `pricing.prompt`, `pricing.completion`, `context_length`, `architecture.modalities`, `supported_parameters`.

Salva il JSON in `Library/System/models/latest.json` per passarlo a Proteo.

### Step 2 — Build new KNOWN_PRICES

Per ogni modello target nella lista sottostante, prendi il prezzo dall'API e costruisci il nuovo dict. I prezzi API sono per token — converti a milioni (× 1.000.000).

**Modelli da tracciare** (per agente Team Olimpo e uso frequente):

| Sezione | Modelli |
|---------|---------|
| OpenAI | `openai/gpt-4o-mini`, `openai/gpt-4o`, `openai/o3-mini`, `openai/o4-mini`, `openai/gpt-5`, `openai/gpt-5-mini`, `openai/gpt-5-nano`, `openai/gpt-4.1`, `openai/gpt-4.1-mini`, `openai/gpt-4.1-nano` |
| Anthropic | `anthropic/claude-opus-4.8`, `anthropic/claude-sonnet-4`, `anthropic/claude-sonnet-4.6`, `anthropic/claude-haiku-4.5` |
| Google | `google/gemini-2.5-pro`, `google/gemini-2.5-flash`, `google/gemini-2.5-flash-lite` |
| xAI direct | `grok-4.3`, `grok-4-1-fast-non-reasoning`, `grok-4-1-fast-reasoning`, `grok-4-0709`, `grok-build-0.1`, `grok-4.20-0309-non-reasoning`, `grok-4.20-0309-reasoning`, `grok-4.20-multi-agent-0309` |
| xAI via OR | `x-ai/grok-4.20`, `x-ai/grok-4.20-multi-agent`, `x-ai/grok-4.3`, `x-ai/grok-build-0.1` |
| DeepSeek | `deepseek/deepseek-v4-flash`, `deepseek/deepseek-v4-pro`, `deepseek/deepseek-r1`, `deepseek/deepseek-chat-v3-0324` |
| Meta | `meta-llama/llama-4-maverick` |
| Altri | `qwen/qwen-2.5-72b-instruct` |

### Step 3 — Update config.py

Riscrivi la sezione `KNOWN_PRICES` in `tools/llm/config.py` con i nuovi prezzi.

Regole:
- Prezzi in USD per milione di token (input, output)
- Mantieni l'ordine per sezioni (OpenAI, Anthropic, Google, xAI direct, xAI via OR, DeepSeek, Meta, Altri)
- Se un modello non è più nell'API, **rimuovilo** da KNOWN_PRICES
- Se il prezzo è cambiato, usa il nuovo valore — nessuna nota storica

### Step 4 — Commit

```bash
git add tools/llm/config.py
git commit -m "chore: sync KNOWN_PRICES $(date +%Y-%m-%d)"
```

### Step 5 — Crea task e delega a Proteo

Crea task con owner Proteo, descrizione "Analisi modelli OpenRouter per mappa di routing".

Poi lancia Proteo con brief che include:

- Path del `latest.json` con tutti i modelli
- Istruzioni: classifica i modelli per caso d'uso (testo, coding, reasoning, vision, immagini, audio, embeddings), fascia di prezzo (budget/mid/premium), e aggiorna `Library/Wiki/team/routing-map.md`
- Include la sezione "Mappa di Routing Rapida" con raccomandazioni del tipo: "Se serve X → usa questo modello → costa Y"
- La mappa deve rispondere alla domanda: **quale modello usare per ogni agente/task del team**

### Step 6 — Leggi handoff di Proteo

Usa `synapsis_hf(act="get", ...)` per leggere il risultato. Verifica `st:` field.

### Step 7 — Report all'utente

Mostra due cose:

1. **Prezzi aggiornati** — tabella compatta dei prezzi correnti (dal più economico)
2. **Raccomandazioni Proteo** — riassunto delle scelte migliori per categoria

Formato report:

```
── Sync modelli (data) ─────────────────────────
  KNOWN_PRICES: X entries aggiornate (commit abc1234)
  Routing map: aggiornata da Proteo

  ⋮ prezzi correnti ⋮

  Raccomandazioni Proteo:
  • Testo generale: Modello X ($/M) — motivazione
  • Coding: Modello Y ($/M) — motivazione
  • Ragionamento: Modello Z ($/M) — motivazione
  • Visione: ...
```

## Anti-patterns

- ❌ **Nessun confronto storico** — non dire "prima costava X ora Y"
- ❌ **Nessuna soglia** — non decidere tu se aggiornare o no, aggiorna sempre
- ❌ **Nessun backup** — non tenere vecchie versioni di KNOWN_PRICES
- ❌ **Proteo saltato** — la procedura include sempre Proteo per la parte di analisi

## Workflow deleghe

```
Poros                      Proteo
  │                          │
  ├─ fetch API               │
  ├─ update config.py        │
  ├─ commit                  │
  ├─ crea task ─────────────►│
  │                          ├─ analizza modelli
  │                          ├─ classifica per caso d'uso
  │                          ├─ aggiorna routing-map.md
  │                          ├─ produce handoff
  │◄─── handoff ────────────│
  ├─ report utente           │
```

## Esempio

Utente: "Poros, aggiorna lista modelli"

Poros:
1. Fetch API → 357 modelli → `latest.json`
2. Build KNOWN_PRICES → 35 entries
3. Update config.py → edit
4. Commit → `beb96b5`
5. Crea task T-SYNC-042 → delega Proteo
6. Legge handoff Proteo → routing map aggiornata
7. Report:

```
── Sync modelli (29 Maggio 2026) ───────────────
  KNOWN_PRICES: 35 entries (commit beb96b5)
  Routing map: aggiornata da Proteo

  Modello                   Input $/M   Output $/M   Ctx
  ─────────────────────────────────────────────────────
  GPT-5 Nano                 0.05        0.40        400K
  DeepSeek V4 Flash          0.10        0.20          1M
  ...
  GPT-5.5 Pro               30.00      180.00         1M

  Raccomandazioni Proteo:
  • Chat general purpose: Grok 4.20 ($1.25/$2.50, 2M ctx)
  • Coding complesso: GPT-5.1 Codex Max ($1.25/$10, 400K)
  • Ragionamento: DeepSeek R1 ($0.70/$2.50, 163K)
  • Visione economica: Gemini 2.5 Flash ($0.30/$2.50, 1M)
  • Massima qualità: Claude Opus 4.8 ($5/$25, 1M ctx)
```
