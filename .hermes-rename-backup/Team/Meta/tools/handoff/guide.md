# handoff tool — Quick Reference

## USE — Generate a handoff

**1. Write body file** → `Team/<you>/hf.md`

Required frontmatter:
```yaml
type: report          # report | analysis | profile | spec | test | note | bug | feedback
title: "max 60 chars"
```

Optional: `task_id`, `status` (default: completed), `priority` (default: medium), `next_action`, `completion_notes`, `output_refs`, `deviation`, `quality_score`.

Body is free Markdown after the `---`.

**2. Run tool** → `uv run python -m tools.handoff main --body Team/<you>/hf.md`

What happens:
- filename built from date/time/agent/type/slug
- handoff written to `Team/Handoff/YYYY/MM/`
- body file deleted

---

## Procedure — full SOP

The canonical step-by-step procedure (body → tool → done) is in `Team/SOPs/handoff-guide.md`.

---

## CONSUME — List existing handoffs

```
uv run python -m tools.handoff list
uv run python -m tools.handoff list --agent efesto --type report
uv run python -m tools.handoff list --task T-HANDOFF-001
uv run python -m tools.handoff list --since 2026-05-01 --until 2026-05-15
```

Filters: `--agent`, `--type`, `--task`, `--search`, `--since`/`--until`, `--year`/`--month`/`--day`.

Output formats: table (default), `--json`, `--paths` (one path per line, pipe-friendly).

---

## Example

Body file `Team/efesto/hf.md`:
```yaml
---
type: report
title: "Fixed loguru import in pdf_converter"
task_id: T-042
completion_notes: "Added loguru to pyproject.toml, test pass"
---
47/50 files converted. 3 skipped: encoding issue in nk-2400-*.md.
Root cause: file uses latin-1, pdf_converter expects utf-8.
```

Run:
```
uv run python -m tools.handoff main --body Team/efesto/hf.md
```

Result: `Team/Handoff/2026/05/2026-05-20_1432_efesto_report_fixed-loguru-import-in-pdf-converter.md`
