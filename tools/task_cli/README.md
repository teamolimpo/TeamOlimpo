# task_cli — Task State Management CLI

Sostituto zero-MCP del server `taskmanager`. Stessa macchina a stati, stesso data model, zero daemon.

## Filosofia

- **Niente MCP** — è un CLI invocato via `bash` tool
- **Niente server** — ogni comando è un processo che muore subito
- **SQLite** — `lib/data/tasks.db`, veloce e indicizzato
- **Stesso data model** del taskmanager design (pending → in_progress → completed/blocked/cancelled)
- **Stesse regole** — auto-promozione parent, ID counter per area, event logging

## Architettura

```
task_cli/
├── __init__.py
├── __main__.py          # Entry point: uv run python -m tools.task_cli
├── cli.py               # Typer CLI (create, status, log, query, summary, export)
├── db.py                # SQLite — init, CRUD, query
├── models.py            # Task dataclass, stato enum
└── state.py             # State machine (transizioni valide, auto-promozione)
```

## Comandi

### `task create <descrizione> [flags]`

Crea un nuovo task.

```bash
uv run -m tools.task_cli create "Analisi framework X" --priority high --owner Proteo
uv run -m tools.task_cli create "📝 Log" --parent T-001
```

Flags:
- `--priority`: low | medium (default) | high | critical
- `--owner`: nome agente (default: Hermes)
- `--parent`: T-ID del parent (per subtask)
- `--tags`: lista tag separati da virgola

**Output**: `T-AREA-042 created ✓`

### `task status <id> <new_status> [flags]`

Transizione di stato con validazione.

```bash
uv run -m tools.task_cli status T-042 in_progress
uv run -m tools.task_cli status T-042 completed --note "Fatto tutto"
uv run -m tools.task_cli status T-042 blocked --note "Bloccato su API key"
```

Stati validi: `pending`, `in_progress`, `completed`, `cancelled`, `blocked`, `standby`

Transizioni:
- `pending` → tutto
- `in_progress` → completed | cancelled | blocked | standby
- `blocked` → in_progress | completed | cancelled
- `standby` → pending | in_progress | completed | cancelled | blocked
- `completed` / `cancelled` = **terminali**

Auto-promozione: se tutti i subtask di un parent sono completed → parent completed.

### `task log <id> <type> <details> [flags]`

Registra un evento su un task.

```bash
uv run -m tools.task_cli log T-042 note "Delegato a Proteo"
uv run -m tools.task_cli log T-042 handoff_ref "Report consegnato" --handoff Team/Handoff/2026/05/report.md
```

Tipi evento: `note`, `decision`, `deviation`, `handoff_ref` (richiede `--handoff`)

### `task query [flags]`

Ricerca task con filtri.

```bash
uv run -m tools.task_cli query                          # ultimi 20
uv run -m tools.task_cli query --status in_progress      # attivi
uv run -m tools.task_cli query --owner Proteo            # per owner
uv run -m tools.task_cli query --priority high           # priorità
uv run -m tools.task_cli query --limit 5                 # ultimi 5
uv run -m tools.task_cli query --parent T-001            # subtask
```

### `task summary [--owner <nome>]`

Statistiche aggregate: totali per stato, per priorità, WIP.

### `task export [--pretty]`

Export completo in YAML (per audit, backup, migrazione).

### `task help`

Mostra la guida completa con tabella delle transizioni.

## Stato (SQLite Schema)

```sql
CREATE TABLE tasks (
    id TEXT PRIMARY KEY,          -- T-AREA-NNN
    description TEXT NOT NULL,     -- max 200 char
    status TEXT NOT NULL DEFAULT 'pending',
    priority TEXT NOT NULL DEFAULT 'medium',
    owner TEXT NOT NULL DEFAULT 'Hermes',
    parent TEXT,                   -- REFERENCES tasks(id)
    tags TEXT,                     -- JSON array
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL
);

CREATE TABLE events (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    task_id TEXT NOT NULL REFERENCES tasks(id),
    type TEXT NOT NULL,            -- note | decision | deviation | handoff_ref
    details TEXT NOT NULL,
    handoff_path TEXT,
    timestamp TEXT NOT NULL
);

CREATE TABLE counter (
    area TEXT PRIMARY KEY,         -- uppercase, e.g. "ANALISI"
    value INTEGER NOT NULL DEFAULT 0
);
```

## Migrazione

```bash
# Dump dal vecchio server
taskmanager_task_export() → taskmanager state

# Import nel nuovo db
uv run -m tools.task_cli migrate taskmanager state
```

Sostituisce: `tools/taskmanager/` + entry MCP in `opencode.json`
