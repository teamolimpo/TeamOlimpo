---
title: "Model Sync Procedure — Update Pricing and Routing Map"
type: sop
doc_id: OLM-SOP-007
version: v1.0
status: active
effective_date: "2026-06-05"
review_date: "2026-12-05"
author: "Poros, Proteo"
scope: team
tags: [sops, poros, proteo, models, pricing, routing]
aliases: [model-sync-procedure, sync-models, aggiorna-modelli]
---

# Model Sync Procedure — Update Pricing and Routing Map

## Purpose

Define the procedure for updating `KNOWN_PRICES` in `tools/llm/config.py` and the routing map in `Library/Wiki/team/routing-map.md` with current OpenRouter API pricing and Proteo's model classification by use case.

## Scope

**Applies to:** All model price synchronization activities. Triggered by user request ("sync prices", "update models", "refresh prezzi").

**Does not apply to:** Ad-hoc model lookups, occasional price checks without full sync.

## Responsibilities

| Role | Responsibility |
|------|---------------|
| **Poros** | Fetches model data from OpenRouter API. Updates `KNOWN_PRICES` in config.py. Commits changes. Creates task for Proteo. Reports results to user. |
| **Proteo** | Analyzes fetched models. Classifies by use case (text, coding, reasoning, vision, image gen). Updates `Library/Wiki/team/routing-map.md`. Produces handoff with recommendations. |

## Definitions

| Term | Meaning |
|------|---------|
| **KNOWN_PRICES** | The static pricing dictionary in `tools/llm/config.py` mapping model IDs to input/output costs per million tokens |
| **Routing map** | `Library/Wiki/team/routing-map.md` — a classified guide mapping use cases to recommended models |

## Rules

1. The user request MUST always trigger a full sync. No skipping based on subjective judgment of "needs update".
2. Prices MUST be in USD per million tokens (input and output).
3. Models no longer present in the API response MUST be removed from `KNOWN_PRICES`.
4. Changed prices MUST use the new value. No historical notes or comparisons preserved.
5. The analysis phase (Proteo) is mandatory. Routing map MUST be updated every sync cycle.
6. Historical price comparisons MUST NOT be included in the user report.
7. No backup versions of KNOWN_PRICES must be retained.
8. Proteo MUST NOT be skipped — the procedure always includes the analysis phase.

## Procedure

### 1. Trigger detection

User says one of: "sync prices", "update models", "refresh prezzi", "aggiorna lista modelli", "fai un sync dei modelli".

### 2. Fetch models from OpenRouter API

```bash
curl -s https://openrouter.ai/api/v1/models \
  -H "Authorization: Bearer $OPENROUTER_API_KEY"
```

Extract for each model: `id`, `pricing.prompt`, `pricing.completion`, `context_length`, `architecture.modalities`, `supported_parameters`.

Save to `Library/System/models/latest.json`.

### 3. Build new KNOWN_PRICES

For each tracked model, take the API price (per token) and convert to per-million-tokens (× 1,000,000).

**Tracked models:**

| Section | Models |
|---------|--------|
| OpenAI | `openai/gpt-4o-mini`, `openai/gpt-4o`, `openai/o3-mini`, `openai/o4-mini`, `openai/gpt-5`, `openai/gpt-5-mini`, `openai/gpt-5-nano`, `openai/gpt-4.1`, `openai/gpt-4.1-mini`, `openai/gpt-4.1-nano` |
| Anthropic | `anthropic/claude-opus-4.8`, `anthropic/claude-sonnet-4`, `anthropic/claude-sonnet-4.6`, `anthropic/claude-haiku-4.5` |
| Google | `google/gemini-2.5-pro`, `google/gemini-2.5-flash`, `google/gemini-2.5-flash-lite` |
| xAI direct | `grok-4.3`, `grok-4-1-fast-non-reasoning`, `grok-4-1-fast-reasoning`, `grok-4-0709`, `grok-build-0.1`, `grok-4.20-0309-non-reasoning`, `grok-4.20-0309-reasoning`, `grok-4.20-multi-agent-0309` |
| xAI via OR | `x-ai/grok-4.20`, `x-ai/grok-4.20-multi-agent`, `x-ai/grok-4.3`, `x-ai/grok-build-0.1` |
| DeepSeek | `deepseek/deepseek-v4-flash`, `deepseek/deepseek-v4-pro`, `deepseek/deepseek-r1`, `deepseek/deepseek-chat-v3-0324` |
| Meta | `meta-llama/llama-4-maverick` |
| Other | `qwen/qwen-2.5-72b-instruct` |

### 4. Update config.py

Rewrite `KNOWN_PRICES` section in `tools/llm/config.py`:

- Maintain section order: OpenAI, Anthropic, Google, xAI direct, xAI via OR, DeepSeek, Meta, Other
- Remove models no longer in API response
- No historical notes

### 5. Commit changes

```bash
git add tools/llm/config.py
git commit -m "chore: sync KNOWN_PRICES $(date +%Y-%m-%d)"
```

### 6. Delegate analysis to Proteo

Create task: `synapsis_task(act="create", owner="Proteo", desc="OpenRouter model analysis for routing map update")`.

Brief includes:
- Path to `Library/System/models/latest.json`
- Instructions: classify models by use case (text, coding, reasoning, vision, images, audio, embeddings), price tier (budget/mid/premium), and update `Library/Wiki/team/routing-map.md`
- Include a "Quick Routing Map" section with recommendations: "For X task → use Y model → costs Z"
- The map must answer: **which model for each agent/task in the team**

### 7. Read Proteo handoff

Use `synapsis_hf(act="get", ...)` to read result. Verify `st:` field.

### 8. Report to user

Two sections:

**Updated prices** — compact table sorted by price.

**Proteo recommendations** — best choices per category.

Format:

```
── Model sync (2026-06-05) ────────────────────────
  KNOWN_PRICES: 35 entries updated (commit beb96b5)
  Routing map: updated by Proteo

  Model                   Input $/M   Output $/M   Ctx
  ─────────────────────────────────────────────────────
  GPT-5 Nano                 0.05        0.40       400K
  ...                         ...         ...        ...

  Proteo recommendations:
  • General chat: Grok 4.20 ($1.25/$2.50, 2M ctx)
  • Complex coding: GPT-5.1 Codex Max ($1.25/$10, 400K)
  • Reasoning: DeepSeek R1 ($0.70/$2.50, 163K)
  • Low-cost vision: Gemini 2.5 Flash ($0.30/$2.50, 1M)
  • Max quality: Claude Opus 4.8 ($5/$25, 1M ctx)
```

## Anti-patterns

| Anti-pattern | Correct behavior |
|---|---|
| Historical price comparison ("was X now Y") | Never include in report |
| Deciding whether update is needed | Always update on trigger |
| Keeping old KNOWN_PRICES versions | No backups retained |
| Skipping Proteo analysis | Procedure always includes Proteo |

## Workflow diagram

```
Poros                         Proteo
  │                             │
  ├─ fetch API                  │
  ├─ update config.py           │
  ├─ commit                     │
  ├─ create task ───────────────┤
  │                             ├─ analyze models
  │                             ├─ classify by use case
  │                             ├─ update routing-map.md
  │                             ├─ produce handoff
  │◄─── handoff ───────────────│
  ├─ report to user             │
```

## References

- `tools/llm/config.py` — KNOWN_PRICES dictionary
- `Library/Wiki/team/routing-map.md` — Model routing map
- `Library/System/models/` — JSON model data storage
- `cb870dc6` — OLM-SOP-002 Handoff Guide

## Revision History

| Version | Date | Author | Description of Change |
|---------|------|--------|----------------------|
| v1.0 | 2026-06-05 | Poros, Proteo | Adopted to OLM-SOP format. Translated to English. Added Purpose, Scope, Responsibilities, Definitions. Restructured into Rules + Procedure. Added anti-patterns table. |
