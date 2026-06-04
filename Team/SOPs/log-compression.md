---
title: "SOP — Compressione Log Livelli (Chimera 3.3)"
tags: [sop, chimera, compressione, log, hot-warm-cold]
updated: 2026-05-24
---

# SOP — Compressione Log Livelli

## Policy — Soglie di Compressione

| Livello | Finestra | Taskmanager events | Session Memory observations |
|---------|----------|-------------------|---------------------------|
| 🔥 **Hot** | 0-7 giorni | Dettaglio completo | Observations integrali, FTS5 searchable |
| 🟡 **Warm** | 8-30 giorni | `details` compresso a max 200 char tramite Token Juice C2 | `content` compresso a max 300 char, FTS5 ancora funzionante |
| 🔵 **Cold** | >30 giorni | Eventi condensati in SummaryEvent per settimana ISO | Observations flaggate `compression_level=2`, sommario settimanale in tabella `summaries` (level 3) |

## Cosa NON viene compresso

- ❌ Handoff files (append-only, intoccabili)
- ❌ Wiki (memoria lunga, non toccata)
- ❌ Deliverable (output finale)
- ❌ Task attivi (solo task con `updated_at` oltre soglia)
- ❌ Dati non vengono mai eliminati — solo compressi o flaggati

## Comandi

### Taskmanager

```bash
# Dry-run: mostra cosa verrebbe compresso, non modifica nulla
uv run python -m tools.taskmanager compress --cold --dry-run

# Apply: esegue compressione cold (>30gg)
uv run python -m tools.taskmanager compress --cold --apply

# Compressione warm (8-30gg)
uv run python -m tools.taskmanager compress --warm --apply

# Forza età personalizzata
uv run python -m tools.taskmanager compress --warm --apply --age-days 14
```

### Session Memory

```bash
# Dry-run
uv run python -m tools.session_memory compress --warm --dry-run

# Apply
uv run python -m tools.session_memory compress --warm --apply
```

### Cron Automation

```bash
# Compressione settimanale warm
uv run python -m tools.log_compressor weekly

# Compressione mensile cold
uv run python -m tools.log_compressor monthly

# Stato ultima esecuzione
uv run python -m tools.log_compressor status
```

Il cron logga in `Library/System/Poros/log_compression.log`.

## Meccanismo

1. **Warm**: Token Juice C2 ProseCompressor con `intensity="full"` comprime il contenuto preservando i fatti. Osservazioni già corte (<100 char) vengono marcate senza ricomprimere.
2. **Cold**: Gli eventi vengono raggruppati per settimana ISO e condensati in un SummaryEvent/SummaryData. Le observations originali rimangono in DB con `compression_level=2`.
3. **Recupero**: Se serve il dettaglio originale, gli handoff_path sono sempre preservati → si recupera dal file handoff originale.

## Manutenzione

- Eseguire `weekly` ogni lunedì (o via cron se configurato)
- Eseguire `monthly` il primo del mese
- Dopo ogni major upgrade degli strumenti, rieseguire `pytest tests/test_log_compression.py -v` (30 test)
- Monitorare `log_compression.log` per errori