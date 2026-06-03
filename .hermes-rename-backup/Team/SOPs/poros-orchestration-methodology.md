---
title: Hermes — Orchestration Methodology
aliases: [hermes-orchestration-methodology, hermes-methodology]
tags: [sops, hermes, orchestration]
---

# Hermes — Orchestration Methodology

Reference document. Hermes loads this for detailed operational guidance.

---

## Briefing Template

Four mandatory sections:
1. **Objective** — what to produce
2. **Anti-patterns** — what not to do, known errors
3. **Output format** — exact structure (path, frontmatter, sections)
4. **Acceptance criteria** — how to verify correctness

Missing section = briefing not ready.

### Three questions before delegating
1. *Does the agent have all information?* (paths, conventions, context)
2. *Does the agent know what NOT to do?* (constraints, errors, anti-patterns)
3. *Can I verify without re-running?* (measurable criteria)
3b. *Are subtasks independent?* Yes → parallel. No → serialize.

No → complete briefing first.

### "Briefing + reference" pattern
Don't explain all conventions inline — point to reference document, highlight only critical points.

### Route handoffs, don't rewrite them — MANDATORY

**Every handoff IS the brief for the next actor.** Hermes never writes a new brief when a handoff exists from the previous step.

**Mechanism:** the brief to the next agent contains only:
1. The file path of the previous handoff
2. What to do with it ("fix everything", "verify", "review")
3. Which SOP to follow (e.g. `agent-review-flow.md`)

Examples:
- Proteo produces gap analysis → tell Atena: "Read `path/to/proteo-handoff.md`. Fix everything it flags. Specs: `agent-design-methodology.md`"
- Clio produces FAIL verification → tell Atena: "Read `path/to/clio-handoff.md`. Fix remaining gaps. Same specs."
- Atena produces fix handoff → tell Clio: "Read `path/to/atena-handoff.md`. Verify all fixes. Use `agent-review-flow.md`"

This applies to every delegation in a multi-step flow. Hermes only writes original briefs for the **first** actor in a chain.

**Anti-pattern:** Hermes summarizing, filtering, rephrasing, or prioritizing a prior handoff. Route it whole. No exception.

### Agent brief — flow selection
- **New agent**: use `agent-creation-flow.md`
- **Modify existing agent**: use `agent-modification-flow.md`
- **Review / verify**: use `agent-review-flow.md`
- All file specs in `agent-design-methodology.md`

### Mandatory inclusions for agent briefs
- **Two files**: `.opencode/agents/<name>.md` + `Team/Members/<name>.md`
- **English only**
- **Prompt Minimal Standard** — no filler, no decorative language
- **Dependencies** list tools/SOPs only — never other agents
- **`Team/Members/Registro.md`** updated

---

## Task Decomposition

Decompose by dependency, not topic. Independent subtasks require:
1. Output of A not needed as input for B
2. No shared exclusive resources
3. Can run with different members in parallel
4. Final synthesis possible after all complete

**All met** → parallel (`task` tool). **Any fails** → serialize.

### Scratchpad before parallel launch
- Add entry per subtask in `active_tasks` (same parent task, different `T-NNN` IDs).
- Set all to `in_progress`. Annotate `[PARALLEL]` before title.

---

## Output Evaluation
- **Completeness**: all briefing points present?
- **Conformance**: follows format and conventions?
- **Plausibility**: makes sense on quick read?

---

## Structured Feedback

Non-conformant output → specify: what's wrong, where, what expected, which convention violated. "Try again" is not feedback.

---

## Recurring Error Log

Never repeat briefing errors. Include precedent as anti-pattern in every related briefing.

Past errors:
- Serial delegations for independent tasks → apply decomposition criteria
- Scratchpad stale during corrections → mechanical trigger before every action

---

## Technical Literacy

Don't write code. Recognize "smelly" output to ask the right questions in briefings and routing.

**Python traps:**
- `Path.relative_to()` doesn't handle `..` — use `os.path.relpath` or `walk_up=True` (Python 3.12+). Every briefing with file ops: "did you handle `..` paths?"
- `ModuleNotFoundError` = environment (missing dep), `ValueError` from `relative_to()` = logic bug. Route accordingly.
- Third-party imports → auto question: "in `requirements.txt`?"
- `__init__.py` defines package, `__main__.py` enables `python -m`, `pyproject.toml` declares deps.
- Windows `\` vs Unix `/`. `pathlib` abstracts; hardcoded strings don't. Backslash in output → ask about portability.

**YAML silent errors:**
- Date-like strings (`2026-03-25`) → `datetime` objects
- `yes`/`no` → booleans
- Duplicate keys → silently overwritten

**Dumbest test rule:** simplest base case must pass before declaring a tool working. Include in briefings.

---

## References
- `Team/SOPs/agent-creation-flow.md`
- `Team/SOPs/agent-modification-flow.md`
- `Team/SOPs/agent-review-flow.md`
- `Team/SOPs/agent-design-methodology.md`
- `Team/SOPs/obsidian-vault-conventions.md`
- `Team/SOPs/handoff-guide.md`
- `Team/Members/Registro.md`
