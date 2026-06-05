# AGENTS.md - Team Olimpo

Guidance for OpenCode on this repository.

## What is this

PKM of **Team Olimpo** — AI agent system with Greek mythological identities. Markdown knowledge base defining roles, profiles, workflows.

## Architecture

**Orchestrator-workers**: Poros routes → best agent via IntentGate.  
New agent flow: Poros → Proteo (domain analysis) → Poros → Atena (persona) → `.opencode/agents/<name>.md`.

## PUBLIC / PRIVATE

- **PUBLIC** (`TeamOlimpo/` → GitHub): templates, skills, configs, tool code, SOPs
- **PRIVATE** (`Library/` → local git, no remote): handoff diaries, system state, wiki, emails, deliverables

`Library/` is gitignored, symlinked to separate local repo.

## Key Paths

| Path | Use |
|------|-----|
| `.opencode/agents/` | Agent prompt files (canonical) |
| `Team/Members/` | Agent identity SOUL.md |
| `Team/SOPs/` | Standard operating procedures |
| `Team/Fucina/` | Working files (gitignored) |
| `tools/` | Python tools (synapsis, email_processor, executor, etc.) |
| `opencode.json` | Main OpenCode config |
| `Library/System/Poros/` | Poros state, scratchpad |
| `Library/Handoff/YYYY/MM/` | Worker handoff files |
| `Library/Wiki/` | Knowledge wiki |
| `Library/deliverables/` | Final outputs |

## Conventions

- Agent profiles in `.opencode/agents/`: standard OpenCode frontmatter
- Names: Greek mythological figures

## Handoff Protocol

Every worker **must** write a handoff file before returning to Poros. No exceptions.  
Full spec: `cb870dc6`
