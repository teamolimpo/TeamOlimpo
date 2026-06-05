---
title: "Agent Design Methodology — Standard for Agent File Structure"
type: sop
doc_id: OLM-SOP-003
version: v1.0
status: active
effective_date: "2026-06-05"
review_date: "2026-12-05"
author: "Atena"
scope: team
tags: [sops, agenti, design, agent-file]
aliases: [agent-design-methodology, agent-design]
---

# Agent Design Methodology — Standard for Agent File Structure

## Purpose

Define the structure, conventions, tools, and patterns every Team Olimpo agent file must follow. Used by any agent that creates or modifies agents (currently Atena). Ensures all agents share a consistent design language, regardless of role.

## Scope

**Applies to:** All agent files in `.opencode/agents/` and their corresponding member identity files in `Team/Members/`. Both new agent creation and revisions to existing agents.

**Does not apply to:** Orchestrator-level files (Poros), handoff files, SOPs, or tool configuration files.

## Responsibilities

| Role | Responsibility |
|------|---------------|
| **Atena** | Creates and modifies agent files following this SOP. Runs the design pipeline. |
| **Proteo** | Provides domain analysis input for new agents (research phase). |
| **Poros** | Routes requests to the correct designer. Validates agent files on deployment. |

## Definitions

| Term | Meaning |
|------|---------|
| **Agent file** | The `.opencode/agents/<name>.md` file that defines an agent's prompt, tools, and behavior |
| **Member file** | The `Team/Members/<name>.md` file that provides a human-readable agent identity |
| **Red Flags** | Situational "what NOT to do" rules — process violations, not boundaries |
| **Limitations** | Invariant structural boundaries — what the agent never does |
| **IntentGate** | A Routing Table that maps incoming requests to delegated agents |

## Rules

1. Every agent file MUST contain exactly these sections in order: frontmatter, header comment, Identity, Communication style, Operating rules, Red Flags (optional), Competencies, Workflows, IntentGate (MANDATORY if `task: allow`), Interactions, Limitations, References.
2. The mandatory sections are: frontmatter, header comment, Identity, Communication style, Operating rules, Competencies, Workflows, Limitations.
3. The `description` field MUST contain both role AND usage trigger ("Use when..."), be operational not poetic, 150-200 chars, and uniquely distinguish the agent from all others.
4. `Red Flags` and `Limitations` MUST NOT overlap. If a boundary fits both, put it in Limitations only.
5. Agents with `task: allow` MUST have an `## IntentGate — Routing Table` section. Without it, delegation is ungoverned.
6. References MUST only list SOPs, tools, and docs the agent **actually uses** — determined by analyzing workflows. No boilerplate, no "just in case" entries.
7. All agent files MUST use `opencode/big-pickle` as the default model. Change only if explicitly specified in the brief.
8. Shell commands MUST use `executor_run` first. `bash: allow` permission only when explicitly justified.
9. Every Team Olimpo agent MUST have an `## MCP Tool Priority` section with Base Layer (mandatory for all) and Variable Layer (per role) tables.
10. The `## IntentGate — Routing Table` MUST NOT include creative interpretation. If intent doesn't clearly match a row, ask for clarification.
11. Member files MUST NOT list other agents by name in Dependencies. List tools, data paths, SOPs, technologies.

## Procedure

### 1. Agent file structure

In this exact order:

| # | Section | Required | Notes |
|---|---------|----------|-------|
| 1 | Frontmatter | ✅ | `description`, `mode`, `model`, `permission`. No custom fields |
| 2 | Header comment | ✅ | 2-3 lines: who the agent is, what they do, what they don't do |
| 3 | Identity | ✅ | Mission in the team (2-4 sentences) |
| 4 | Communication style | ✅ | Tone, rhythm, language rule |
| 5 | Operating rules | ✅ | Non-negotiable constraints, protocols |
| 5.5 | Red Flags | — | "What NOT to Do" table — process violations, situational |
| 6 | Competencies | ✅ | By domain, not flat list. Each with context for when/how |
| 7 | Workflows | ✅ | Numbered steps with input/output per step |
| 8 | IntentGate | ⚠️ If `task: allow` | Maps requests → delegated agent |
| 9 | Interactions | — | Direction (receive/produce) and format. No agent names |
| 10 | Limitations | ✅ | Structural boundaries. Must not overlap with Red Flags |
| 11 | References | ✅ | Only SOPs/tools/docs actually used |

### 2. Description field

The `description` selects which agent to invoke. Rules:
- Contains role AND usage trigger ("Use when...")
- Operational, not poetic
- One line, ~150-200 chars
- Uniquely distinguishes this agent from all others
- Never mention specific agent names

**Anti-patterns:** vague ("Helps with various things"), too restrictive ("Only for YAML files"), duplicate of another agent's description.

### 3. Permission / tool selection

| Role type | Recommended permissions |
|-----------|------------------------|
| Writes code/files | `read`, `write`, `edit` |
| Research and analysis | `read`, `write`, `websearch`, `webfetch` |
| Delegates to other agents | `read`, `write`, `edit`, `task` |
| Read-only consultation | `read` |

**Standard permission block:**
```yaml
permission:
  edit:
    "Library/System/<agent-name>/**": "allow"
    "Team/Fucina/**": "allow"
  read: allow
```

Add additional paths only when the agent's role explicitly requires it (e.g., `.opencode/agents/**` for Atena, `Library/Handoff/**` for handoff-writers). `Team/<agent-name>/` is deprecated.

### 4. MCP Tool Priority section

Every agent MUST have this section with two tables:

**Base Layer — MANDATORY (all agents):**

| Purpose | MCP Tool | Don't Use |
|---------|----------|-----------|
| Context retrieval | `synapsis_search(query, scope="auto", l=2, n=3)` | Glob/Grep/Read for context. Legacy tools |
| Task lifecycle | `synapsis_task(act="create"\|...\|"summary")` | Edit for task mgmt. File-based state |
| Agent handoff | `synapsis_hf(act="new"\|"get", ...)` | Write for handoff files |
| Session context | `synapsis_session(act="init"\|...\|"summarize")` | Relying on memory alone |
| Hash resolution | `synapsis_d_get(h=..., l=2)` | Treating hashes as file paths |

**Variable Layer — by role:**

| Role | executor_run | synapsis_admin | synapsis_d_set |
|------|-------------|----------------|----------------|
| **Research** | REQUIRED | — | — |
| **Code** | REQUIRED | — | — |
| **Design** (Atena) | REQUIRED | — | REQUIRED |
| **Audit** (Clio) | RECOMMENDED | — | — |
| **Writing** | — | — | — |
| **Strategy** | — | — | — |
| **Orchestrator** (Poros) | RECOMMENDED | REQUIRED | REQUIRED |

After the table, include: "**Exception:** Native tools (Read, Edit, Write, Glob, Grep, Bash, WebFetch, websearch) are primary for file I/O and web fetching — these have no direct MCP equivalent. For shell execution, prefer `executor_run` over native `bash`."

### 5. IntentGate — Routing Table design

Every agent with `task: allow` MUST have this section.

| Identified Intent | Route | Action |
|---|---|---|
| Request type A | Agent X | Delegate with parameters |
| Request type B | Agent Y | Delegate with parameters |

**Rules:**
1. One row = one distinct intent. Two requests with same routing can share a row separated by "|".
2. No creative interpretation. If unclear, ask clarification.
3. Direct route — call the specialist, don't do it yourself.
4. Last row: "Ambiguous / not catalogued" → ask clarification / escalate to Poros.
5. Must align with Poros' IntentGate. Don't invent categories.

### 6. Prompt Minimal Standard

Every line carries operational weight. Self-review:
- Does this sentence tell the agent what to do or how to decide? No → remove.
- Can I say the same in fewer words? Yes → compress.
- Decorative adjectives ("comprehensive", "accurate")? → remove.
- Legacy tool references? → replace with `synapsis_*`.
- Path uses wrong base? Agent dirs → `Library/System/<name>/`.

**Final check:** Run Token Juice (`python -m tools.token_juice process cat <file>`). Apply compressions. Revert if readability breaks.

### 7. Member identity file

Every agent has two files created together and kept in sync:

| File | Purpose |
|------|---------|
| `.opencode/agents/<name>.md` | Operational, system-facing prompt |
| `Team/Members/<name>.md` | Human-facing identity |

**Member file structure:**
1. Frontmatter — `type: member`, `agent: <name>`, `role: <role>` (all lowercase, hyphenated)
2. `# <Name> — Team Olimpo` — title
3. `## Identity` — mission in one paragraph
4. `## Values` — 3-5 operational decision-making rules
5. `## Boundaries` — explicit list of what the agent does NOT do
6. `## Dependencies` — tools, data paths, SOPs. **No agent names.**

### 8. Depth calibration

- Narrow, procedural domain: detailed and concise instructions.
- Wide domain requiring judgment: richer instructions with principles, frameworks, anti-patterns.
- Prompt length consumes context. Same meaning in fewer words, always.

## Common anti-patterns

| Anti-pattern | Problem | Fix |
|---|---|---|
| Decorative personality | Tone described without operative instructions | "Concise" in prompt must match concise output |
| Vague limitations | "Don't do things outside your scope" | List explicitly what is excluded |
| Process without steps | "Analyze and produce output" | Each step needs input, action, output |
| Competency list | Capabilities without context | Explain how and when to use each |
| Custom frontmatter | Non-standard YAML fields | Put in body, not frontmatter |
| Member name references | Agent files naming other agents | Poros manages routing. Exceptions: Poros, Atena pipeline |
| Legacy tools | `task_*`, `knowledge_*`, `session_*` | Use only `synapsis_*` tools |
| Path confusion | Wrong base prefix | Use `Library/System/<name>/`, `Library/Handoff/`, `Library/deliverables/` |
| Missing IntentGate | `task: allow` without routing table | Agent doesn't know whom to call |

## References

- `OLM-SOP-001-sop-format.md` — SOP format standard
- `cb870dc6` — Handoff protocol (OLM-SOP-002)
- `.opencode/` agent file directory structure
- `Team/Members/` member identity file directory

## Revision History

| Version | Date | Author | Description of Change |
|---------|------|--------|----------------------|
| v1.0 | 2026-06-05 | Atena | Adopted to OLM-SOP format standard. Added Purpose, Scope, Responsibilities, Definitions. Restructured into Rules + Procedure. Hash references for cross-SOP links. |
