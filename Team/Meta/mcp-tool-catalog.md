---
title: MCP Tool Catalog — Team Olimpo
aliases: [mcp-tool-catalog]
tags: [meta, tools, mcp, reference]
---

# MCP Tool Catalog — Team Olimpo

Catalogo tecnico di tutti gli MCP tool disponibili per gli agenti Team Olimpo.
Questo file è **referenza pura** — non contiene regole di assegnazione.
Per la matrice ruolo→tool, vedi `Team/SOPs/agent-design-methodology.md` → *MCP Tool Assignment*.

---

## Tool MCP Disponibili

| Tool | Server MCP | Parametri Chiave | Token Juice | Chunked | Edge Case |
|------|-----------|-----------------|-------------|---------|-----------|
| `taskmanager_task_create` | taskmanager | description, priority, owner, parent, task_id, tags, status | — | — | Se description >150 char → auto-truncato con warning |
| `taskmanager_task_update_status` | taskmanager | task_id, new_status, note | — | — | Transizione non valida → errore server; auto-promuove parent se tutti i sibling completati |
| `taskmanager_task_query` | taskmanager | status, owner, priority, task_id, parent, search, tag, since, limit | — | — | Nessun filtro → ultimi `limit` per updated_at |
| `taskmanager_task_summary` | taskmanager | owner (optional) | — | — | Owner vuoto → conteggio globale |
| `taskmanager_task_log_event` | taskmanager | task_id, event_type, details, handoff_path | — | — | `event_type` deve essere uno tra: handoff_ref, note, decision, deviation |
| `taskmanager_task_export` | taskmanager | pretty (bool) | — | — | Usare con parsimonia (alto costo token) |
| `synapsis_hf` | synapsis | act (new/get), type, title, body, agent, task, st, prio, note, refs, devi, ref, tk, q | ✅ Token Juice su get | — | act="new" crea handoff, act="get" legge con compressione. q= usa FTS5 per chunk mirato. |
| `knowledge_search` | synapsis | query, scope, chunked, mode, max_results, context_lines, no_frontmatter, context_chunks | — | ✅ chunked=True → 80-95% risparmio token | **Progressive disclosure**: start con context_lines=0, no_frontmatter=True, max_results=5. Fallback automatico a grep se indice chunk assente. |
| `executor_run` | executor | command, intensity (auto/lite/full/ultra/off), timeout, locale (en/it) | ✅ 73-81% compressione | — | **Utiliy Gate**: se output <128 char o ratio >0.95 → restituisce originale. Errore non-zero → raw output. |
| `session_memory_session_init` | session_memory | topic, resume, task_ids, token_budget | — | — | resume=True → cerca ultima sessione active/interrupted |
| `session_memory_session_observe` | session_memory | session_id, type, content, agent, entities, handoff_path, task_ref | — | — | type: decision, delegation, result, note, handoff, user_message, system |
| `session_memory_session_context` | session_memory | session_id, layer (1/2/3), max_tokens | — | — | Layer 1 ~200 token, Layer 2 ~800, Layer 3 ~1500 |
| `session_memory_session_recall` | session_memory | query, entity, agent, type, session_id, max_results, since | — | ✅ FTS5 BM25 | FTS5 syntax supportata ("phrase queries", AND, OR, NOT) |
| `session_memory_session_summarize` | session_memory | session_id, level, force | — | — | force=True → ricomprime tutto |

---

## Note d'Uso

### executor_run — Intensity Levels

| intensity | Effetto | Quando usare |
|-----------|---------|-------------|
| `auto` | Ultra se rule match specifico, Full per prosa prevalente, Off se Token Juice non disponibile | Default — sempre usare salvo override esplicito |
| `lite` | Compressione leggera | Output già corto ma si vuole un minimo risparmio |
| `full` | Compressione standard (C3 + C2 Prose) | Output medio-lungo (>2KB), prosa bilanciata |
| `ultra` | Massima compressione | Output lungo (>10KB), log, dump |
| `off` | Nessuna compressione | Debug, output deve rimanere verbatim |

### knowledge_search — Progressive Disclosure Pattern

1. **Prima chiamata**: `knowledge_search(query, context_lines=0, no_frontmatter=True, max_results=5)` → solo titoli chunk
2. **Selezione**: l'agente mostra i titoli all'utente (se orchestrato) o valuta quali sono pertinenti
3. **Espansione**: `knowledge_search(stessa_query, chunked=True, context_chunks=2, max_results=3)` → chunk + vicini solo per i match selezionati

### Session Memory — Auto-Capture Pattern

```
1. session_init(topic, resume=True) → all'avvio
2. session_observe(type, content, agent, entities) → dopo ogni azione
3. session_context(layer=2) → prima di delegare
4. session_summarize() → ogni ~20 osservazioni o a chiusura
```