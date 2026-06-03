# AGENTS.md - Team Olimpo

Guidance for OpenCode on this repository.

## What is this

PKM of **Team Olimpo** — AI agent system with Greek mythological identities. Markdown knowledge base defining roles, profiles, workflows.

## Architecture

**Orchestrator-workers**: Hermes routes → best agent via IntentGate.  
New agent flow: Hermes → Proteo (domain analysis) → Hermes → Atena (persona) → `.opencode/agents/<name>.md`.

## PUBLIC / PRIVATE

- **PUBLIC** (`TeamOlimpo/` → GitHub): templates, skills, configs, tool code, SOPs
- **PRIVATE** (`lib/` → local git, no remote): handoff diaries, system state, wiki, emails, deliverables

`lib/` is gitignored, symlinked to separate local repo.

## Key Paths

| Path | Use |
|------|-----|
| `.opencode/agents/` | Agent prompt files (canonical) |
| `Team/Members/` | Agent identity SOUL.md |
| `Team/SOPs/` | Standard operating procedures |
| `Team/Fucina/` | Working files (gitignored) |
| `tools/` | Python tools (synapsis, email_processor, executor, etc.) |
| `opencode.json` | Main OpenCode config |
| `lib/System/Hermes/` | Hermes state, scratchpad |
| `Library/Handoff/YYYY/MM/` | Worker handoff files |
| `Library/Wiki/` | Knowledge wiki |
| `Library/deliverables/` | Final outputs |

## Conventions

- Agent profiles in `.opencode/agents/`: standard OpenCode frontmatter
- Names: Greek mythological figures

## Handoff Protocol

Every worker **must** write a handoff file before returning to Hermes. No exceptions.  
Full spec: `Team/SOPs/handoff-guide.md`
