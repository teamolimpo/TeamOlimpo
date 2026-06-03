---
title: SOP Trigger Index
aliases: [sop-index, sop-trigger-map, command-index]
tags: [sops, hermes, routing, index]
---

# SOP Trigger Index

Mappa comandi ricorrenti → SOP file.
Hermes: consulta via `d_get` quando una richiesta sembra un task ricorrente.

| Trigger | SOP | Agente | Descrizione |
|---------|-----|--------|-------------|
| aggiorna modelli, sync prices, update models, refresh prezzi, check prezzi, sync dei modelli | `Team/SOPs/model-sync-procedure.md` | Hermes → Proteo | Update KNOWN_PRICES + routing map |
| comprimi log, compress logs, cleanup logs, compressione log | `Team/SOPs/log-compression.md` | Hermes | Log compression pipeline (hot/warm/cold) |
| design first, test gate, sviluppo design-first | `Team/SOPs/design-first-workflow.md` | Hermes | Design-First, Test-Gated development workflow |
| review agente, verify agent, gap analysis, agent review | `Team/SOPs/agent-review-flow.md` | Hermes → Clio/Metis | Agent QC review and gap analysis |
| kba analysis, deltaV risk, analisi KBA, kba gap | `Team/SOPs/kba-analysis-flow.md` | Hermes → Dike | KBA risk scoring and gap analysis |
