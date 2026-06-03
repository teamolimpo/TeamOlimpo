# TeamOlimpo

<div align="center">

**The orchestration layer for AI agent teams**

[![MCP-native](https://img.shields.io/badge/MCP-native-6C5CE7?style=flat-square)](https://modelcontextprotocol.io)
[![OpenCode](https://img.shields.io/badge/OpenCode-config-00B894?style=flat-square)](https://opencode.ai)
[![Python 3.12+](https://img.shields.io/badge/Python-3.12+-2D7D46?style=flat-square)](https://python.org)
[![MIT License](https://img.shields.io/badge/License-MIT-6366F1?style=flat-square)](LICENSE)
[![Status: Alpha](https://img.shields.io/badge/Status-Alpha-F97316?style=flat-square)]()

</div>

---

## What Is This?

TeamOlimpo is a **meta-orchestration layer for AI agent teams** — not an agent framework. If you've tried CrewAI, LangGraph, or AutoGen and hit the ceiling where coordinating multiple agents becomes more complex than building the agents themselves, this is for you.

Existing tools solve the *single-agent* problem well:
- PydanticAI, LangChain, and Vercel AI SDK are excellent for building one agent.
- CrewAI and AutoGen give you role-based multi-agent prototyping fast.
- LangGraph gives you precise state-machine control over complex branching.

But none of them solve the problem that emerges *after* you have multiple agents: **how do they hand work to each other reliably?** How do you audit what happened across a 7-agent pipeline? How do you know which agent produced what, with what confidence, and what deviations occurred?

TeamOlimpo answers those questions. It is not a framework for building agents — it is an **operating system for coordinating them**.

```text
┌─────────────────────────────────────────────┐
│           TeamOlimpo Meta-Orchestrator        │
│  ┌─────────┐  ┌──────────┐  ┌─────────────┐ │
│  │  Poros   │→ │IntentGate│→ │Specialized  │ │
│  │(Router)  │  │(Selector)│  │  Agents     │ │
│  └─────────┘  └──────────┘  └──────┬──────┘ │
│                                     │        │
│  ┌──────────────────────────────┐   │        │
│  │   Structured Handoff File    │←──┘        │
│  │   (st, prio, devi, score)    │            │
│  └──────────────────────────────┘            │
│                   │                           │
│  ┌──────────────────────────────┐            │
│  │   Next Agent / Synthesis     │            │
│  └──────────────────────────────┘            │
└─────────────────────────────────────────────┘
```

Built on three non-negotiables:

- **MCP-native** — every tool is an MCP server. OpenCode integration day one. No wrappers, no adapters.
- **Mandatory handoff protocol** — every agent boundary produces a structured, auditable handoff file. No output is delivered without one.
- **SOP-driven** — standard operating procedures define how agents are created, how they work, and how they hand off. Consistency is enforced, not hoped for.

---

## Architecture in 30 Seconds

The orchestration flow is a linear pipeline with a feedback loop:

```
Request → Poros (orchestrator)
           ↓
         IntentGate (classify → route)
           ↓
         Specialized Agent (execute → produce handoff)
           ↓
         Handoff File (structured audit record)
           ↓
         Poros (evaluate → synthesize → respond)
           ↓
         Next Agent (reads previous handoff as its brief)
           ↓
         ... chain continues
```

**Poros** (the orchestrator) never executes work directly. It receives requests, classifies intent via **IntentGate** (a 17-category routing table), delegates to the right specialist, reads the resulting handoff, and synthesizes for the user.

**IntentGate** covers 17 fixed routing categories — from "new agent creation" (routes to Proteo → Atena) to "bug fix" (routes to Efesto) to "technical document writing" (routes to Hermione). Ambiguous intent? Poros asks for clarification. Multi-intent? Decomposed and executed in sequence.

Every delegation ends with a **handoff file** — a structured Markdown document with YAML frontmatter containing status, priority, deviation reports, and quality scores. The handoff *is* the audit trail.

---

## The Team

Each agent is a Greek mythological figure with a corresponding function. Agents are defined in two files: an `.opencode/agents/<name>.md` prompt file and a `Team/Members/<name>.md` identity profile.

| Agent | Role | Function |
|-------|------|----------|
| **Poros** | Orchestrator | Entry point. Routes, tracks, synthesizes. Never executes directly. |
| **Atena** | Agent Designer | Designs, regenerates, audits agent system prompts. Builds the agents that build. |
| **Proteo** | Senior Researcher | Multi-source domain research. Declares gaps, never invents data. |
| **Pythagoras** | Academic Researcher | Institutional-source-first research. Sciences, humanities, economics. |
| **Efesto** | Python Developer | Production-ready Python: CLI tools, automations, pipelines, API integrations. |
| **Hermione** | Technical Writer | Synthesizes multi-source materials into structured, vault-ready documentation. |
| **Euterpe** | Essay Writer | Italian school compositions with rigid structure and level-appropriate register. |
| **Clio** | Vault Archivist | Library management, PDF conversion, cataloging, systematic verification. |
| **Dike** | KBA Risk Analyst | Risk assessment of Knowledge Base Articles for Emerson DeltaV systems. |
| **Metis** | Thinking Partner | Cognitive catalyst: brainstorming, strategic reflection, devil's advocate. |
| **Eunomia** | Contextual Analyst | Email vault analysis: connects every message to its context, project, thread. |

---

## What Makes This Different

### 1. The Handoff Protocol

No other multi-agent system has this. Every time an agent finishes work, it writes a structured handoff file before returning control. This creates a complete, queryable audit trail of every agent interaction.

```json
{
  "handoff": {
    "ref": "hf-a3k9",
    "type": "report",
    "agent": "efesto",
    "st": "done",
    "prio": "high",
    "note": "Fixed loguru import — all 47/50 files converted. 3 skipped due to encoding.",
    "quality_score": 4,
    "devi": {
      "type": "tool_failure",
      "description": "ModuleNotFoundError: loguru in pdf_converter",
      "cause": "Missing dependency in pyproject.toml",
      "corrective_action": "Added loguru via uv add",
      "outcome": "resolved",
      "user_impact": false
    },
    "refs": ["pyproject.toml", "tools/pdf_converter/main.py"]
  }
}
```

**Confidence: CONFIRMED** — verified against the handoff protocol implementation in `tools/synapsis/hf.py` and `Team/SOPs/handoff-guide.md`.

Every field matters:
- `st: done | fail | hold | kill` — immediate status signal for the orchestrator
- `devi` — structured deviation report when something went wrong
- `quality_score: 1-5` — self-assessed quality by the producing agent
- `refs` — paths to all produced artifacts

No handoff = task incomplete. This is enforced at the agent level — every agent's operating rules mandate a handoff before returning control.

### 2. SOP-Driven Architecture

Standard operating procedures define *how* work gets done, not just *what*. Key SOPs in `Team/SOPs/`:

- **`handoff-guide.md`** — the handoff protocol specification
- **`poros-orchestration-methodology.md`** — routing, delegation, and task decomposition
- **`agent-design-methodology.md`** — agent creation and structure standards
- **`obsidian-vault-conventions.md`** — Markdown formatting and vault organization

SOPs are versioned and referenced, never duplicated. Every agent's prompt file points to the relevant SOPs rather than inlining their content.

### 3. MCP-Native from Day One

All tools are [MCP (Model Context Protocol)](https://modelcontextprotocol.io) servers — not REST wrappers, not SDK abstractions. The Synapsis tool suite (`synapsis_search`, `synapsis_task`, `synapsis_hf`, `synapsis_session`, `synapsis_admin`) provides:

- Unified search across knowledge, tasks, memory, entities, sessions, handoffs
- Task lifecycle management with status tracking
- Handoff file creation, reading, and wiki auto-generation
- Session context management for long-running interactions
- System health checks, checkpointing, and diagnostics

Frameworks like LangGraph and CrewAI are adding MCP support. TeamOlimpo started with it.

### 4. Quality Gates

Every agent has built-in quality checks:
- **Efesto**: `ruff check → ruff format → mypy → pytest` before every delivery
- **Hermione**: frontmatter validation, confidence markers, gap declarations
- **Clio**: systematic verification — no operation declared complete without verification
- **Proteo**: minimum 2-3 independent sources per key claim

---

## Working Code Example

Here is a complete agent (Efesto, the Python developer) showing the architecture in action. This is the actual prompt file at `.opencode/agents/efesto.md` (simplified):

```yaml
# .opencode/agents/efesto.md
description: "Python developer for Team Olimpo. Use when Python code is needed."
mode: subagent
model: openrouter/deepseek/deepseek-v4-flash
permission:
  bash: allow
  edit:
    "tools/**": "allow"
    "pyproject.toml": "allow"
    "tests/**": "allow"
  read: allow
  write: allow
```

When Poros delegates a task to Efesto, the workflow looks like this:

1. **Receive brief** — Poros sends the task description with requirements, acceptance criteria, and references
2. **Create task** — `synapsis_task(act="create", owner="efesto", desc="Build CSV validator", prio="high")`
3. **Build** — Write code with type hints, error handling, logging (loguru), CLI (Typer)
4. **Quality gate** — `ruff check . && ruff format . && mypy tools/ && pytest -v`
5. **Register artifact** — `synapsis_d_set(p="tools/csv_validator/")` → returns hash like `7aa85572`
6. **Write handoff** — `synapsis_hf(act="new", type="report", agent="efesto", st="done", ...)`
7. **Return** — Control goes back to Poros with the handoff reference

The handoff becomes the brief for the next agent in the chain — Poros never rewrites it.

---

## Comparison: When to Use What

This is not a competition — each tool excels in a specific niche. Here is how to choose:

| Feature | LangGraph | CrewAI | AutoGen | **TeamOlimpo** |
|---|---|---|---|---|
| **Category** | Graph-based state machine | Role-based framework | Conversation framework | **Meta-orchestrator** |
| **Best for** | Complex branching logic, stateful workflows | Rapid multi-agent prototyping | Agent-to-agent conversation | **Coordinating agent teams with audit trails** |
| **Structured handoff protocol** | ❌ | ❌ | ❌ | **✅ Mandatory + auditable** |
| **SOP-driven architecture** | ❌ | ❌ | ❌ | **✅ Versioned SOPs govern all workflows** |
| **MCP-native** | 🛠 Adding | 🛠 Adding | 🛠 Adding | **✅ Day one** |
| **Identity system** | ❌ Custom nodes | ✅ Roles | ❌ | **✅ 11 specialized agents, Greek mythology** |
| **Quality gates** | ❌ | ❌ | ❌ | **✅ Per-agent quality checks before delivery** |
| **AutoGen migration path** | N/A | N/A | Fragmented (v0.4 broke compat) | **✅ Structured handoff makes migration feasible** |
| **Single-agent focus** | ❌ | ❌ | ❌ | **❌ Not for building individual agents** |

**Confidence: CONFIRMED** — based on our own analysis of LangGraph, CrewAI, and AutoGen documentation. AutoGen's fragmentation across v0.1–v0.4 is widely reported in the community.

### Decision Guide

| You want to... | Use |
|---|---|
| Build a single chatbot with tool calling | PydanticAI, Vercel AI SDK |
| Prototype a multi-agent system fast | CrewAI |
| Model complex branching logic with state | LangGraph |
| Run agent-to-agent conversations | AutoGen |
| **Orchestrate a team of agents with audit trails** | **TeamOlimpo** |
| **Implement a handoff protocol across custom agents** | **TeamOlimpo** |
| **Enforce SOPs and quality gates automatically** | **TeamOlimpo** |

Think of it this way: LangGraph is a state machine, CrewAI is a role-playing framework, AutoGen is a conversation framework, and TeamOlimpo is **Kubernetes for agents** — it doesn't build them, it coordinates them.

---

## Quickstart

### Prerequisites

- [OpenCode](https://opencode.ai) (AI-native editor)
- Python 3.12+
- `uv` (Python package manager)

### Setup

```bash
# Clone the repository
git clone https://github.com/teamolimpo/TeamOlimpo.git
cd TeamOlimpo

# Install dependencies
uv sync

# Verify the setup
uv run python -m tools.synapsis.server --help
```

### Configure

The main configuration file is `opencode.json`:

```json
{
  "$schema": "https://opencode.ai/config.json",
  "default_agent": "poros",
  "mcp": {
    "synapsis": {
      "type": "local",
      "command": ["uv", "run", "python", "-m", "tools.synapsis"],
      "enabled": true,
      "env": {
        "SYNAPSIS_DB_PATH": "Library/System/Poros/synapsis.db"
      }
    }
  }
}
```

### Run Your First Delegation

Open the project in OpenCode and ask Poros:

> "Research best practices for async Python and write a technical summary."

Poros will:
1. Classify the intent → research (Proteo) + technical writing (Hermione)
2. Delegate to Proteo for research → Proteo produces a handoff
3. Route Proteo's handoff to Hermione for synthesis → Hermione produces a document
4. Poros reads Hermione's handoff and returns the result

Each step creates an auditable handoff file in `Library/Handoff/YYYY/MM/DD/`.

---

## Project Status

**Alpha** — working but evolving. The core handoff protocol, orchestration flow, and 11 agents are operational. Here is what to expect:

### ✅ What Works

- Poros orchestration with IntentGate routing
- Structured handoff protocol (11 valid types, 4 statuses, deviation reporting)
- Synapsis tool suite (search, task management, session, handoff, admin)
- All 11 agent profiles with SOPs
- MCP-native tool architecture
- Quality gates for code and documentation agents

### 🔜 What's Coming

- [ ] AutoGen-to-TeamOlimpo migration tooling
- [ ] Visual handoff graph (Mermaid diagrams auto-generated from handoff chains)
- [ ] Pluggable agent SDK adapters (use any agent framework as a worker)
- [ ] Runtime quality score analytics
- [ ] Public package on PyPI

### ⚠️ What's Experimental

- Cross-agent conflict resolution (Metis integration)
- Automatic wiki generation from handoff content
- Parallel task execution optimization

---

## Community & Contributing

### How to Contribute

All standard operating procedures live in `Team/SOPs/`. Start there.

1. **Read the handoff protocol** — `Team/SOPs/handoff-guide.md`. Every contribution must produce handoffs.
2. **Explore the agent methodology** — `Team/SOPs/agent-design-methodology.md` for agent creation standards.
3. **Understand the orchestration flow** — `Team/SOPs/poros-orchestration-methodology.md` for routing and delegation.
4. **Follow the conventions** — agent profiles go in `.opencode/agents/`, identity files in `Team/Members/`.

### Project Structure

```
TeamOlimpo/
├── .opencode/agents/        # Agent prompt files (canonical)
├── Team/
│   ├── Members/             # Agent identity profiles (SOUL.md)
│   ├── SOPs/                # Standard operating procedures
│   └── Fucina/              # Working files (gitignored)
├── tools/                   # Python tools (MCP servers)
│   ├── synapsis/            # Unified search, task, handoff, session
│   ├── executor/            # Shell command execution with Token Juice
│   └── email_processor/     # Email vault processing
├── Library/                 # Private data (gitignored/symlinked)
│   ├── Handoff/             # Handoff audit trail
│   ├── Wiki/                # Knowledge wiki
│   └── deliverables/        # Final outputs
└── opencode.json            # Main OpenCode configuration
```

### Guidelines

- **No handoff, no merge** — every PR that adds agent logic must include the corresponding handoff specification.
- **SOPs before code** — new workflows start with an SOP proposal before implementation.
- **Quality gates required** — code contributions must pass ruff, mypy, and pytest.
- **Confidence markers** — use CONFIRMED / PARTIALLY CONFIRMED / UNCONFIRMED for comparative claims in documentation.

### Getting Help

- Open a GitHub issue for bugs or feature requests
- Read the SOPs in `Team/SOPs/` for detailed operational guidance
- Review the agent profiles in `Team/Members/` to understand each agent's boundaries

---

## License

MIT License — see [LICENSE](LICENSE) for details.

---

*Team Olimpo*
