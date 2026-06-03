---
type: report
title: Synapsis HF implementato e integrato
task_id: T-HF-001
status: done
priority: high
---

## Summary

Synapsis HF implementato e integrato in Synapsis. Rimpiazzato il vecchio MCP server handoff separato (tools/handoff/) con il nuovo tool `synapsis_hf` direttamente in Synapsis. ~150K token risparmiati all'avvio, ~23 token per chiamata.

## Changes

### tools/synapsis/hf.py (nuovo, ~740 righe)
- `generate_ref()` — genera ref univoci hf-XXXX con secrets.token_hex
- `build_frontmatter()` — frontmatter YAML compatto (ref, type, title, agent, st, prio, task...)
- `build_filename()` — filename canonico YYYY-MM-DD_HHMM_agent_type_slug.md (stessa logica del vecchio)
- `write_handoff_file()` — scrittura diretta in Library/Handoff/YYYY/MM/ (niente temp file, niente subprocess)
- `parse_wiki_section()` — portato da tools/handoff/server.py con _finalize_wiki_value, _validate_wiki_section
- `write_wiki_page()` — portato da tools/handoff/server.py con _update_wiki_index, _update_wiki_log
- `hf_new()` — orchestrazione: genera ref, scrive file, indicizza DB, processa ## Wiki, chunking immediato
- `hf_get()` — lettura handoff per ref con compressione Token Juice e FTS5 chunk extraction

### tools/synapsis/store.py
- Aggiunta tabella `hf` (DDL con 6 indici: ref PK, idx su type/agent/task/st/ts)
- Metodi: `hf_insert()`, `hf_get()`, `hf_search()`, `hf_exists()`
- Aggiunto scope `'hf'` a `unified_search()` per `synapsis_search(scope="hf")`
- Aggiunto dominio `'hf'` al seeding DDL

### tools/synapsis/server.py
- Nuovo tool `hf(act="new"|"get", ...)` — 6° tool MCP in Synapsis

### Eliminato
- `tools/handoff/server.py` (721 righe)
- `tools/handoff/cli.py` (915 righe)
- `tools/handoff/main.py`, `__main__.py`, `__init__.py`
- Entry `handoff` in `.mcp.json`
- Sezione `handoff` in `tools/config.yaml`
- Entry `handoff` in `opencode.json`

### Aggiornato
- `tools/sync_agents.py`: `handoff_create` → `synapsis_hf`, `handoff_list` → `synapsis_search`

## Quality Gate

- `ruff check .` — my new code: 0 errors (only pre-existing in server.py)
- `ruff format .` — my new code: ok
- `mypy tools/synapsis/hf.py` — ok
- Integration tests: 4/4 pass (new, get, wiki, search)

## Token Impact

- -1 MCP server (handoff) = ~150K token risparmiati all'avvio
- -23 token per chiamata (parametri compressi: act, st, prio, tk)
- ~750 righe eliminate, ~850 righe aggiunte
