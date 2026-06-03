---
title: Agent Design Methodology
aliases: [agent-design-methodology, agent-design]
tags: [sops, agenti, design]
---

# Agent Design Methodology

Design reference for Team Olimpo agent files. Describes structure, conventions, tools, and patterns that every agent file must follow. Used by any agent that creates or modifies agents (currently Atena). Not tied to a specific designer role — the rules are team-wide.

---

## Agent file structure

1. **Frontmatter** — technical identity: `description`, `mode`, `model`, `permission`. No custom fields.
2. **Header comment** — 2-3 lines readable by humans: who the agent is, what they do, what they don't do.
3. **Identity** — mission in the team (2-4 sentences)
4. **Communication style** — tone, rhythm, language rule
5. **Operating rules** — non-negotiable constraints, protocols
5.5 **Red Flags** — "What NOT to Do" table. **Process violations**: when X happens, do NOT Y. One row per known failure mode. Must NOT overlap with Limitations (section 9) — if a boundary fits both, put it in Limitations only. Red Flags = situational, Limitations = invariant. Optional for simple agents, recommended for complex ones.
6. **Competencies** — by domain, not flat list. Each with context for when/how to use.
7. **Workflows** — numbered steps with input/output per step
8. **IntentGate — Routing Table** — **MANDATORY for agents with `task: allow`** (delegation). Optional for others. Maps requests → delegated agent: when agent receives X, it calls Y. Without IntentGate, a delegating agent either does everything itself (violates orchestrator-workers pattern) or calls the wrong agent.
9. **Interactions** — direction (receive/produce) and format. No agent names — Hermes manages routing.
10. **Limitations** — **structural boundaries**: what the agent does NOT do, explicit scope limits. Must NOT overlap with Red Flags (section 5.5). If a boundary fits both, it belongs here, not in Red Flags.
11. **References** — SOPs, tools, and docs this agent **actually uses**. Determined by analyzing the agent's workflows — if a reference doesn't correspond to a tool call, workflow step, or operational dependency, it doesn't belong. No boilerplate, no "just in case" entries.

Mandatory: frontmatter, header comment, identity, communication style, operating rules, competencies, workflows, limitations.

---

## Model

Default: `opencode/big-pickle`. Change only if explicitly specified in the brief.

---

## Description field

The `description` selects which agent to invoke. Critical.

**Rules:**
- Contains role AND usage trigger ("Use when...")
- Operational, not poetic
- One line, ~150-200 chars
- Uniquely distinguishes this agent from all others
- Never mention specific agent names

**Anti-patterns:** vague ("Helps with various things"), too restrictive ("Only for YAML files"), duplicate of another agent's description.

---

## Permission / tool selection

| Role type | Recommended permissions |
|-----------|------------------------|
| Writes code/files | `read`, `write`, `edit` |
| Research and analysis | `read`, `write`, `websearch`, `webfetch` |
| Delegates to other agents | `read`, `write`, `edit`, `task` |
| Read-only consultation | `read` |

`bash` = **avoid.** Use `executor_run` (MCP tool) — Token Juice compression, managed timeout, structured output. Raw `bash` only when `executor_run` isn't enough (rare cases — interactive commands, complex pipes). `task` = agent delegation — orchestrators or collaborators only.

**Rule:** If an agent needs shell commands, first choice is `executor_run`. `bash: allow` permission only when explicitly justified in the brief.

**Standard permission block for every agent:**
```yaml
permission:
  edit:
    "lib/System/<agent-name>/**": "allow"   # own working directory
    "Team/Fucina/**": "allow"                # shared working area
  read: allow
```
`Team/<agent-name>/` is **deprecated** — do not use. Add additional paths only when the agent's role explicitly requires it (e.g., `.opencode/agents/**` for Atena, `lib/Handoff/**` for agents that write handoffs).

---

## Synapsis Tool Reference

### Overview

| Tool | Purpose | Key params |
|------|---------|------------|
| `synapsis_search` | Single entry point for all context — knowledge, tasks, memory, entities, timeline | `query="..."`, `scope="auto"`, `l=2`, `n=3` |
| `synapsis_task` | Task lifecycle | `act="create"\|"query"\|"update"\|"log"\|"summary"\|"export"\|"compress"` |
| `synapsis_session` | Session lifecycle | `act="init"\|"observe"\|"context"\|"summarize"\|"compress"\|"tasks"` |
| `synapsis_hf` | Handoff: create and retrieve handoff files | `act="new"\|"get"`, `type=`, `agent=`, `title=`, `body=` |
| `synapsis_admin` | System administration | `act="health"\|"domain"\|"orphan"\|"vacuum"\|"stats"\|"index"\|"checkpoint"` |
| `synapsis_d_get` | Resolve CRC32 hash (8 char) → file content | `h=...`, `l=2` (500ch summary) / `l=3` (full) |
| `synapsis_d_set` | Register file path → get hash | `p="path/to/file"` |

### Golden retrieval rule

**`synapsis_search` is the ONLY tool for context lookup.** NEVER use Glob, Grep, Read for file discovery. If you see an 8-char hex hash, use `synapsis_d_get(h=...)`. If you see a path like `Library/Handoff/...` or `Library/deliverables/...`, resolve via hash first or use `synapsis_search(scope="auto")`.

Scope auto-detection:
- `T-XXX` → search tasks + observations
- `path:Wiki/topics/...` → load file content
- `hash:7aa85572` → use `d_get(h=...)`
- Default → fan-out across all domains

---

## MCP Tool Priority

Every Team Olimpo agent MUST have an `## MCP Tool Priority` section with a table of the Synapsis tools it uses. Two layers: **Base** (mandatory for all) and **Variable** (per role).

### Base Layer — MANDATORY (present in every agent)

| Purpose | MCP Tool | When to Use | Don't Use |
|---------|----------|------------|-----------|
| Context retrieval | `synapsis_search(query, scope="auto", l=2, n=3)` | First step for ANY context — knowledge, tasks, memory, entities. Layer 2 = sweet spot ~300-500t | Don't use Glob/Grep/Read for context lookup. Don't use legacy tools — they don't exist |
| Task lifecycle | `synapsis_task(act="create"\|"query"\|"update"\|"log"\|"summary")` | Every request that creates work, tracks state, or updates status | Don't use Edit for task management. Don't track state in files |
| Agent handoff | `synapsis_hf(act="new"\|"get", ...)` | Agent completion output, spec/plan files, delegation results | Don't use Write for handoff files. Always use synapsis_hf |
| Session context | `synapsis_session(act="init"\|"observe"\|"context"\|"summarize")` | At session start/end, between delegations, after significant events | Don't rely on memory alone. Persist with synapsis_session |
| Hash resolution | `synapsis_d_get(h=..., l=2)` | When you see an 8-char hex string (hash). Layer 2 = summary, Layer 3 = full | Don't treat hashes as file paths. Don't use Read for hash lookup |

### Variable Layer — by role

| Role | executor_run | email_processor | synapsis_admin | synapsis_d_set |
|------|-------------|-----------------|----------------|----------------|
| **Research** (Proteo, Pythagoras) | **REQUIRED** — grep/ls/rg with compressed output | — | — | — |
| **Code** (Efesto) | **REQUIRED** — build/test/structure analysis | — | — | — |
| **Design** (Atena) | **REQUIRED** — YAML validation, coherence check | — | — | **REQUIRED** |
| **Audit** (Clio, Dike) | **RECOMMENDED** — batch file checks | — | — | — |
| **Writing** (Hermione, Euterpe) | — | — | — | — |
| **Strategy** (Metis) | — | — | — | — |
| **Email** (Eunomia) | — | **REQUIRED** | — | — |
| **Orchestrator** (Hermes) | **RECOMMENDED** | **RECOMMENDED** | **REQUIRED** | **REQUIRED** |

### Validation rules (for Atena in Phase 3)

1. **Missing REQUIRED** → ADD the row to the MCP Tool Priority table, with role-calibrated description
2. **— (N/A) present in table** → REMOVE the row (noise only)
3. **Missing RECOMMENDED** → skip, at agent's discretion
4. "When to Use" and "Don't Use" descriptions must be role-specific
5. The line "**Exception:** Native tools (Read, Edit, Write, Glob, Grep, Bash, WebFetch, websearch) are primary for file I/O and web fetching — these have no direct MCP equivalent. For shell execution, prefer `executor_run` over native `bash` (compression, timeout, structured output)." MUST always appear AFTER the table

### Calibrated tool descriptions

| Tool | Generic description | When to calibrate |
|------|-------------------|-------------------|
| `synapsis_search` | Unified context retrieval | Research: "first step before any read — discover via l=2". Code: "find existing patterns, docs, examples" |
| `executor_run` | Shell command execution with Token Juice compression. **Replaces `bash` for most uses.** | Research: "grep, ls, rg, project structure queries". Design: "YAML linting, coherence checks". Code: "build, test, lint" |
| `email_processor_*` | Email vault operations | Only Hermes and Eunomia. For all others: do not include |
| `synapsis_admin` | System administration | Only Hermes and admin agents |
| `synapsis_d_set` | Register path → get hash | Only file-creating agents: Atena, Hermes |

---

## IntentGate — Routing Table Design

Every agent with `task: allow` (delegation to other agents) MUST have an `## IntentGate — Routing Table` section. This prevents the agent from executing tasks outside its scope by delegating to the right teammate.

### Standard format

| Identified Intent | Route | Action |
|---|---|---|
| Request type A | Agent X | What exactly to do (delegate with which params) |
| Request type B | Agent Y | What exactly to do |

### Rules

1. **One row = one distinct intent.** Two requests with same routing can share a row separated by "|".
2. **No creative interpretation.** If intent doesn't clearly match a row, ask for clarification.
3. **Direct route** — "Do X" → call the specialist for X. Don't do X yourself.
4. **Uncovered cases** — last row: "Ambiguous / not catalogued" → ask clarification / escalate to Hermes.
5. **Team-wide consistency** — table must align with Hermes' IntentGate. If Hermes doesn't route for it, the agent shouldn't invent it.

### Example (Hermes)

| Identified Intent | Route | Action |
|---|---|---|
| New agent creation | Proteo → Atena | Serial: Proteo domain analysis → handoff → Atena builds profile |
| Agent revision | Atena | Direct: no intermediate analysis |
| Research/analysis | Proteo | Delegate, return result |
| Academic research | Pythagoras | Delegate with verifiable sources |
| Code/Python | Efesto | Specify requirements, delegate |
| ... | ... | ... |

### Example (Atena)

| Identified Intent | Route | Action |
|---|---|---|
| Domain research | Proteo | Delegate domain analysis → append to pipeline file |
| Compliance check | Clio | Delegate format/conformity check → append to pipeline file |
| Critical review | Metis | Delegate gap analysis → append to pipeline file |
| Strategy / design decision | Metis | Delegate before making structural choices |
| Code needed | Efesto | Flag to Hermes — Atena doesn't deploy code |

---

## Depth calibration

- Narrow, procedural domain: detailed and concise instructions.
- Wide domain requiring judgment: richer instructions with principles, frameworks, anti-patterns.
- Prompt length consumes context. Same thing in fewer words without precision loss → do it.

---

## Common anti-patterns

- **Decorative personality**: describing tone without operative instructions that reflect it. "Concise" + verbose output = contradiction.
- **Vague limitations**: "Don't do things outside your scope" says nothing. List explicitly.
- **Process without steps**: "Analyze and produce output" is not a process. Each step needs input, action, output.
- **Competency list**: listing capabilities without explaining how and when to use them.
- **Custom frontmatter fields**: non-standard fields belong in the body, not frontmatter.
- **Member name references**: agent files must not reference other team members by name. The orchestrator manages routing.
  *Exception*: agents that orchestrate sub-agents (Hermes, Atena in pipeline mode) reference other agents by name for task delegation. Allowed in operational prompts — files they *produce* still follow the no-names rule.
- **Legacy tool references**: referencing `task_*`, `knowledge_*`, `session_*`, `context`, `timeline`, `entity_search`, `handoff` (old) — these tools DON'T EXIST. Only `synapsis_*` tools are valid.
- **Path confusion**: both `lib/` and `Library/` exist (Library → /home/stra/Library symlink). Agent config paths use `lib/` prefix. Deliverables live under `Library/deliverables/`.
- **Missing IntentGate**: agents with `task: allow` without `## IntentGate — Routing Table` = ungoverned delegation. Agent doesn't know when to call whom, ends up doing everything itself or calling randomly.

---

## Member identity file (`Team/Members/<name>.md`)

Every agent has two files: `Team/Members/<name>.md` (identity, human-facing) and `.opencode/agents/<name>.md` (operational, system-facing). Created together, kept in sync.

### Structure

1. **Frontmatter** — `type: member`, `agent: <name>`, `role: <role>` (all lowercase, hyphenated).
2. **`# <Name> — Team Olimpo`** — title.
3. **`## Identity`** — who this agent is, their mission in a single paragraph.
4. **`## Values`** — 3-5 operational principles. Each is a decision-making rule, not an aspiration.
5. **`## Boundaries`** — explicit list of what this agent does NOT do.
6. **`## Dependencies`** — tools, data sources, SOPs this agent relies on. **Never list other agents by name.** The orchestrator handles routing; agents do not know each other.

### Rules
- **English only**
- **No agent names in Dependencies** — list tools, data paths, SOPs, technologies. Not people.
- One file per agent

---

## Prompt Minimal Standard

Every line in an agent file carries operational weight. No filler, no decoration.

**Self-review after drafting:**
- Does this sentence tell the agent what to do or how to decide? No → remove.
- Can I say the same in fewer words? Yes → compress.
- Decorative adjectives ("comprehensive", "accurate", "professional")? → remove.
- Is `description` operational or descriptive? Must be operational — it selects the agent.
- Legacy tool references? → replace with `synapsis_*` equivalents.
- Path uses wrong base? Agent dirs → `lib/System/<name>/`. Handoff → `lib/Handoff/`. Deliverables → `Library/deliverables/`.

**Final check:** Run Token Juice (`python -m tools.token_juice process cat <file>`) on every new/modified agent file. Apply suggested compressions where they don't sacrifice clarity. Revert if compression breaks readability.

**Prompt length consumes context.** Same meaning in fewer words, always.
