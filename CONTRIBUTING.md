# Contributing to TeamOlimpo

##  Welcome

Thanks for checking out TeamOlimpo.

Reality check: we have about six commits and zero GitHub stars. The API will change, the architecture will evolve. If you need stability for production, check back at beta.

But if you want to see how an MCP-native, SOP-driven meta-orchestrator works under the hood — and help shape it before it hardens — you are in the right place.

TeamOlimpo has strong opinions:

- **Every agent boundary produces a structured handoff.** No exceptions.
- **SOPs govern everything.** Workflows start with a procedure document, not with code.
- **MCP is the only protocol.** No REST wrappers, no SDK abstractions.

If those resonate, read on. If they sound like overhead, no hard feelings — the process bet is not for everyone.

---

##  Getting Started

### Prerequisites

- **OpenCode** — the project runs on OpenCode's MCP runtime.
- **Python 3.12+** — the entire toolchain targets it.
- **uv** — Python package manager ([install guide](https://docs.astral.sh/uv/#installation)).

### Setup

```bash
# Fork the repository on GitHub, then:
git clone https://github.com/YOUR_USERNAME/TeamOlimpo.git
cd TeamOlimpo

# Install all dependencies (including dev)
uv sync --group dev

# Verify your setup
uv run python -m tools.synapsis.server --help
```

If that prints the Synapsis MCP server help output, you are ready.

### Required Reading

Before your first pull request, skim these:

- **`Team/SOPs/handoff-guide.md`** — the central protocol. Every contribution touches this.
- **`Team/SOPs/obsidian-vault-conventions.md`** — formatting and structure for documentation.

You do not need to memorize them. Just know they exist.

---

##  The Rules (Non-Negotiable)

These apply to every contribution. Pull requests that violate them will not be merged.

### No Handoff, No Merge

Every agent contribution produces a structured handoff file via `synapsis_hf(act="new", ...)` before returning control. The handoff is the audit trail — the orchestrator uses it to decide what happens next. Without it, the chain breaks.

**Exception:** typo fixes and trivial doc corrections (one paragraph or less) do not need a handoff. Mention "no handoff needed" in the PR description.

### SOPs Before Code

New workflows start with an SOP proposal — write it, get it reviewed, then implement. The SOP defines the contract; code without one is untestable against project standards.

### Quality Gates Are Local

Before committing Python code:

```bash
ruff check . && ruff format . && mypy tools/ && pytest -v
```

All must pass. No exceptions. CI does not exist yet — quality is your responsibility.

### Confidence Markers

Documentation with factual or comparative claims must use explicit markers:

- `CONFIRMED` — multiple reliable sources
- `PARTIALLY CONFIRMED` — supported with caveats
- `UNCONFIRMED` — single source or indirect evidence

### OpenCode First

The project runs on OpenCode's MCP runtime. Contributions with non-MCP patterns must include a migration path or strong justification in the SOP proposal.

---

##  First Contribution Ideas

Not sure where to start:

### Documentation (no handoff needed for small fixes)

- Fix a typo, broken link, or formatting issue in any `.md` file
- Improve an SOP's clarity or add a worked example
- Write a worked example of the handoff protocol with real commands

### Python (requires quality gates + handoff)

- Add type annotations to functions that lack them
- Write test cases for uncovered modules in `tests/`
- Improve error messages — make them actionable

### Architecture (requires issue discussion first)

- Propose new IntentGate routing categories
- Review existing SOPs for gaps or contradictions
- Suggest improvements to the handoff specification

### For Everyone

- Star the repository — it helps others find the project
- Open an issue when something breaks or confuses
- Tell us what you expected versus what you found — that shapes the project

---

##  FAQ

**Do I really need OpenCode?**

To run the full system, yes — agent profiles, MCP servers, and routing depend on it. But Python tool contributions (`tools/`) can be developed independently.

**One-character typo — do I need a handoff?**

No. Small doc fixes (one paragraph or less) do not need a handoff. Note "no handoff needed" in the PR.

**Can I contribute without knowing Greek mythology?**

Yes. It is a naming convention, not a prerequisite. The README's team table tells you everything you need.

**Why so much process for an alpha project?**

Because the process *is* the product. Coordination, handoffs, and SOPs are not overhead — they are the core mechanism. If the process does not work for contributors, it will not work for the system. Easier to start with discipline than add it later.

**I want to add a feature. Where do I start?**

Open an issue first. Feature work flows through IntentGate routing, so we need to understand how it fits before implementation starts. Issue discussion prevents wasted effort.

---

## Code of Conduct

This project is governed by the [Contributor Covenant v2.1](https://www.contributor-covenant.org/version/2/1/code_of_conduct/). By participating, you agree to uphold its standards. Be professional, be constructive, and assume good intent.

---

*Team Olimpo*
