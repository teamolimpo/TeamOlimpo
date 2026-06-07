# TeamOlimpo

<div align="center">

**Kubernetes for AI agents — a meta-orchestrator that coordinates specialist agents with structured handoffs, SOPs, and quality gates.**

[![MCP-native](https://img.shields.io/badge/MCP-native-6C5CE7?style=flat-square)](https://modelcontextprotocol.io)
[![OpenCode](https://img.shields.io/badge/OpenCode-config-00B894?style=flat-square)](https://opencode.ai)
[![Python 3.12+](https://img.shields.io/badge/Python-3.12+-2D7D46?style=flat-square)](https://python.org)
[![MIT License](https://img.shields.io/badge/License-MIT-6366F1?style=flat-square)](LICENSE)
[![Status: Alpha](https://img.shields.io/badge/Status-Alpha-F97316?style=flat-square)]()
[![Handoffs](https://img.shields.io/badge/Handoffs-777+-FF6B6B?style=flat-square)]()

⭐ **Star the repo if you find this useful** — it helps others discover it too.

</div>

---

## The Problem

CrewAI, LangGraph, and AutoGen solve multi-agent *prototyping* fast. But once you have 5-10 agents, the real problem emerges: **how do they hand work to each other reliably?** How do you audit a 7-agent pipeline? How do you know which agent produced what, with what confidence?

Existing tools give you agents. They don't give you an **operating system** to coordinate them.

TeamOlimpo is that OS.

---

## Try It (2 minutes)

```bash
git clone https://github.com/teamolimpo/TeamOlimpo.git
cd TeamOlimpo
uv sync
opencode .
```

Then ask Poros (the orchestrator):

> *"Research async Python patterns and write a technical summary."*

Poros will:
1. Route to **Proteo** (research) → produces structured handoff
2. Route handoff to **Hermione** (technical writing) → produces document
3. Return the result

Every step writes an auditable handoff file. No output is delivered without one.

---

## What Makes This Different

### The Handoff Protocol

No other multi-agent system has this. Every time an agent finishes work, it writes a structured handoff before returning control. Status, priority, deviation reports, quality scores — all in one file.

```
Handoff { st: done | fail | hold, devi: { cause, corrective_action }, quality_score: 1-5, refs: [...] }
```

No handoff = task incomplete. Enforced at the agent level.

👉 [Full handoff protocol spec →](Team/SOPs/cb870dc6.md)

### SOP-Driven Architecture

Standard operating procedures define *how* work gets done, not just *what*:

- **`cb870dc6`** — Handoff protocol
- **`900191a0`** — Agent creation standards
- **`5f609a1a`** — Routing and delegation

SOPs are versioned and referenced, never duplicated.

### MCP-Native from Day One

All tools are MCP servers — not REST wrappers, not SDK abstractions. Frameworks like LangGraph and CrewAI are adding MCP support. TeamOlimpo started with it.

### Quality Gates

- **Efesto** (Python dev): `ruff check → ruff format → mypy → pytest` before delivery
- **Hermione** (writer): confidence markers, gap declarations
- **Proteo** (researcher): minimum 2-3 independent sources per key claim

---

## The Team (11 Agents)

| Agent | Role |
|-------|------|
| **Poros** | Orchestrator — routes, tracks, synthesizes |
| **Atena** | Agent designer — builds the agents that build |
| **Proteo** | Multi-source domain researcher |
| **Pythagoras** | Academic researcher (peer-reviewed sources) |
| **Efesto** | Python developer — production-ready code |
| **Hermione** | Technical writer — structured documentation |
| **Euterpe** | Italian essay writer |
| **Clio** | Vault archivist — PDF, cataloging, verification |
| **Dike** | Risk analyst (Emerson DeltaV) |
| **Metis** | Strategic thinking partner |
| **Eunomia** | Contextual analyst (email vault) |

---

## Quick Comparison

| Feature | LangGraph | CrewAI | AutoGen | **TeamOlimpo** |
|---------|-----------|--------|---------|----------------|
| Category | State machine | Role-based | Conversation | **Meta-orchestrator** |
| Handoff protocol | ❌ | ❌ | ❌ | **✅ Mandatory + auditable** |
| SOP-driven | ❌ | ❌ | ❌ | **✅ Versioned SOPs** |
| MCP-native | 🛠 Adding | 🛠 Adding | 🛠 Adding | **✅ Day one** |
| Quality gates | ❌ | ❌ | ❌ | **✅ Per-agent** |

**TeamOlimpo is not a framework for building agents — it coordinates them after you have them.**

---

## Project Structure

```
TeamOlimpo/
├── .opencode/agents/     # Agent prompt files
├── Team/
│   ├── Members/          # Agent identity profiles
│   └── SOPs/             # Standard operating procedures
├── tools/                # MCP servers (Python)
│   ├── synapsis/         # Search, task, handoff, session
│   ├── executor/         # Shell execution with Token Juice
│   └── email_processor/  # Email vault processing
└── Library/              # Private data (gitignored)
```

---

## Status

**Alpha** — 777+ handoffs executed, 11 agents operational, core protocol solid.

### ✅ Works Now
- Poros orchestration with IntentGate routing (17 categories)
- Structured handoff protocol (11 types, 4 statuses, deviation reporting)
- Synapsis tool suite (search, task, session, handoff, admin)
- All 11 agent profiles with SOP enforcement
- Quality gates for code and documentation

### 🔜 Coming
- AutoGen-to-TeamOlimpo migration tooling
- Visual handoff graph (auto-generated Mermaid)
- Pluggable agent SDK adapters
- Runtime quality analytics
- PyPI package

---

## Contributing

- **No handoff, no merge** — every PR must include handoff specs
- **SOPs before code** — new workflows start with an SOP proposal
- **Quality gates** — code must pass ruff, mypy, pytest

Start with `Team/SOPs/` — read the handoff protocol (`cb870dc6`) and the agent methodology (`900191a0`).

---

<div align="center">

⭐ **Star on GitHub** — it helps the project grow  
📖 [Read on Substack](https://tensormill.substack.com/p/i-built-a-multi-agent-system-that) — full story behind the system

MIT License — [LICENSE](LICENSE)

</div>