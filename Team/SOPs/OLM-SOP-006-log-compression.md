---
title: "Log Compression — Hot/Warm/Cold Lifecycle"
type: sop
doc_id: OLM-SOP-006
version: v1.0
status: active
effective_date: "2026-06-05"
review_date: "2026-12-05"
author: "Poros"
scope: team
tags: [sop, chimera, compression, log, hot-warm-cold, maintenance]
---

# Log Compression — Hot/Warm/Cold Lifecycle

## Purpose

Define the log compression policy for Team Olimpo data management. Hot (0-7 days) retains full detail, Warm (8-30 days) compresses content via Token Juice, Cold (>30 days) condenses events into weekly summaries. Prevents unbounded data growth while preserving retrievability.

## Scope

**Applies to:** Task events, session observations, and log data across all agents.

**Does not apply to:** Handoff files (append-only, never compressed), Wiki (long-term memory, untouched), deliverables (final output never modified), active tasks (only tasks past the age threshold).

## Responsibilities

| Role | Responsibility |
|------|---------------|
| **Poros** | Runs weekly and monthly compression routines. Monitors `log_compression.log` for errors. |
| **System** | Cron automation triggers scheduled compression. |

## Definitions

| Term | Meaning |
|------|---------|
| **Hot** | 0-7 day window — full detail retained, FTS5 searchable |
| **Warm** | 8-30 day window — details compressed to max 200ch (tasks) or 300ch (observations) |
| **Cold** | >30 day window — events condensed into ISO-week summaries, originals flagged with `compression_level=2` |
| **Token Juice C2** | ProseCompressor with `intensity="full"` that preserves facts while compressing |

## Rules

1. Data MUST NEVER be deleted — only compressed or flagged.
2. Handoff files MUST NEVER be compressed (append-only, audit-intact).
3. Active tasks MUST NOT be compressed (only tasks past the age threshold).
4. Warm compression MUST preserve facts. Token Juice C2 with `intensity="full"` compresses content; observations shorter than 100 characters MUST be marked without recompression.
5. Cold compression MUST group events by ISO week and condense into SummaryEvent/SummaryData tables. Original observations remain in DB with `compression_level=2`.
6. Original detail MUST be retrievable via preserved `handoff_path` fields pointing to original handoff files.
7. After every major upgrade of compression tools, all tests in `tests/test_log_compression.py` MUST pass.

## Procedure

### 1. Compression policy table

| Level | Window | Task events | Session observations |
|-------|--------|-------------|---------------------|
| **Hot** | 0-7 days | Full detail | Full observations, FTS5 searchable |
| **Warm** | 8-30 days | `details` compressed to max 200ch via Token Juice C2 | `content` compressed to max 300ch, FTS5 functional |
| **Cold** | >30 days | Events condensed into SummaryEvent per ISO week | Observations flagged `compression_level=2`, weekly summary in `summaries` table (level 3) |

### 2. Execute task compression

```bash
# Dry-run: show what would be compressed, no modifications
uv run python -m tools.taskmanager compress --cold --dry-run

# Apply cold compression (>30 days)
uv run python -m tools.taskmanager compress --cold --apply

# Warm compression (8-30 days)
uv run python -m tools.taskmanager compress --warm --apply

# Custom age override
uv run python -m tools.taskmanager compress --warm --apply --age-days 14
```

### 3. Execute session compression

```bash
# Dry-run
uv run python -m tools.session_memory compress --warm --dry-run

# Apply
uv run python -m tools.session_memory compress --warm --apply
```

### 4. Scheduled cron automation

```bash
# Weekly warm compression (every Monday)
uv run python -m tools.log_compressor weekly

# Monthly cold compression (1st of month)
uv run python -m tools.log_compressor monthly

# Check last run status
uv run python -m tools.log_compressor status
```

Log output is written to `Library/System/Poros/log_compression.log`.

### 5. Recovery

If original detail is needed after cold compression: the `handoff_path` field is always preserved → retrieve from the original handoff file.

### 6. Maintenance

- Run `weekly` every Monday (or via cron if configured).
- Run `monthly` on the 1st of each month.
- After every major tool upgrade, execute: `pytest tests/test_log_compression.py -v`
- Monitor `Library/System/Poros/log_compression.log` for errors.

## References

- `tools/taskmanager.py` — Task compression commands
- `tools/session_memory.py` — Session observation compression
- `tools/log_compressor.py` — Cron automation
- `tests/test_log_compression.py` — Compression test suite

## Revision History

| Version | Date | Author | Description of Change |
|---------|------|--------|----------------------|
| v1.0 | 2026-06-05 | Poros | Adopted to OLM-SOP format. Added Purpose, Scope, Responsibilities, Definitions. Restructured into Rules + Procedure. |