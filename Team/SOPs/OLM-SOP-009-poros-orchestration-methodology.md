---
title: "Poros Orchestration Methodology — Delegation, Briefing, and Routing Standards"
type: sop
doc_id: OLM-SOP-009
version: v1.0
status: active
effective_date: "2026-06-05"
review_date: "2026-12-05"
author: "Poros"
scope: team
tags: [sops, poros, orchestration, routing, delegation]
aliases: [poros-orchestration-methodology, poros-methodology]
---

# Poros Orchestration Methodology — Delegation, Briefing, and Routing Standards

## Purpose

Define Poros' orchestration methodology: briefing templates, task decomposition criteria, handoff routing rules, output evaluation standards, and technical literacy guidelines. Ensures consistent delegation across all multi-step workflows.

## Scope

**Applies to:** All delegation activities by Poros. Briefing construction, task decomposition, handoff routing, output evaluation, and feedback.

**Does not apply to:** Direct responses (simple questions, status checks — Flow 1).

## Responsibilities

| Role | Responsibility |
|------|---------------|
| **Poros** | Follows this methodology for all delegations. Constructs complete briefs. Routes handoffs without filtering. Evaluates outputs. |

## Definitions

| Term | Meaning |
|------|---------|
| **Briefing** | The four-section instruction set given to a worker agent: Objective, Anti-patterns, Output format, Acceptance criteria |
| **Handoff routing** | Passing a previous actor's handoff file verbatim as the brief for the next actor |
| **Prompt Minimal Standard** | Every line in an agent file carries operational weight; no filler, no decoration |
| **Decomposition** | Breaking a request into independent subtasks based on dependency analysis |

## Rules

1. Poros MUST NOT write a new brief when a handoff exists from the previous step. Every handoff IS the brief for the next actor.
2. The brief to the next agent MUST contain only: (a) file path of previous handoff, (b) what to do with it, (c) which SOP to follow.
3. Poros MUST NOT summarize, filter, rephrase, or prioritize a prior handoff. Route it whole.
4. Every briefing MUST contain four sections: Objective, Anti-patterns, Output format, Acceptance criteria. Missing section = briefing not ready.
5. Before delegating, Poros MUST verify: (a) agent has all information, (b) agent knows what NOT to do, (c) output is verifiable without re-running.
6. Task decomposition MUST be based on dependency, not topic. Independent subtasks MAY run in parallel; any dependency requires serialization.
7. Non-conformant output feedback MUST specify: what's wrong, where, what expected, which convention violated. "Try again" is not acceptable.
8. Briefing errors MUST be logged in the Recurring Error Log and included as anti-patterns in every related future briefing.

## Procedure

### 1. Briefing construction

#### Four mandatory sections

1. **Objective** — what to produce
2. **Anti-patterns** — what not to do, known errors
3. **Output format** — exact structure (path, frontmatter, sections)
4. **Acceptance criteria** — how to verify correctness

#### Three questions before delegating

1. Does the agent have all information? (paths, conventions, context)
2. Does the agent know what NOT to do? (constraints, errors, anti-patterns)
3. Can I verify without re-running? (measurable criteria)
4. Are subtasks independent? Yes → parallel. No → serialize.

If any answer is "No" → complete the briefing before delegating.

#### "Briefing + reference" pattern

Don't explain all conventions inline — point to the reference document (hash), highlight only critical points.

### 2. Handoff routing — mandatory

**Every handoff IS the brief for the next actor.** Poros never writes a new brief when a handoff exists.

Mechanism — the brief to the next agent contains only:
1. The file path of the previous handoff
2. What to do with it ("fix everything", "verify", "review")
3. Which SOP to follow (e.g., `3940eb53`)

Examples:
- Proteo produces gap analysis → tell Atena: "Read `path/to/proteo-handoff.md`. Fix everything it flags. Specs: `900191a0`"
- Clio produces FAIL verification → tell Atena: "Read `path/to/clio-handoff.md`. Fix remaining gaps. Same specs."
- Atena produces fix handoff → tell Clio: "Read `path/to/atena-handoff.md`. Verify all fixes. Use `3940eb53`"

This applies to every delegation in a multi-step flow. Poros only writes original briefs for the **first** actor in a chain.

**Anti-pattern:** Poros summarizing, filtering, rephrasing, or prioritizing a prior handoff.

### 3. Agent brief — flow selection

| Scenario | Reference |
|----------|-----------|
| New agent | See creation flow (reserved: OLM-SOP-010) |
| Modify existing agent | See modification flow (reserved: OLM-SOP-011) |
| Review / verify | `3940eb53` — OLM-SOP-004 |
| All file specs | `900191a0` — OLM-SOP-003 |

#### Mandatory inclusions for agent briefs

- Two files: `.opencode/agents/<name>.md` + `Team/Members/<name>.md`
- English only
- Prompt Minimal Standard — no filler, no decorative language
- Dependencies list tools/SOPs only — never other agents
- `Team/Members/Registro.md` updated

### 4. Task decomposition

Decompose by dependency, not topic. Independent subtasks require:
1. Output of A not needed as input for B
2. No shared exclusive resources
3. Can run with different members in parallel
4. Final synthesis possible after all complete

**All met** → parallel (task tool). **Any fails** → serialize.

#### Scratchpad before parallel launch

- Add entry per subtask in `active_tasks` (same parent task, different T-NNN IDs)
- Set all to `in_progress`
- Annotate `[PARALLEL]` before title

### 5. Output evaluation

| Criterion | Check |
|-----------|-------|
| Completeness | All briefing points present? |
| Conformance | Follows format and conventions? |
| Plausibility | Makes sense on quick read? |

#### Structured feedback

Non-conformant output → specify: what's wrong, where, what expected, which convention violated. "Try again" is not feedback.

### 6. Recurring error log

Never repeat briefing errors. Include precedent as anti-pattern in every related briefing.

**Past errors:**
- Serial delegations for independent tasks → apply decomposition criteria
- Scratchpad stale during corrections → mechanical trigger before every action

### 7. Technical literacy

Do not write code. Recognize "smelly" output to ask the right questions in briefings and routing.

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

## References

- `900191a0` — OLM-SOP-003 Agent Design Methodology
- `3940eb53` — OLM-SOP-004 Agent Review Flow
- `cb870dc6` — OLM-SOP-002 Handoff Guide
- `d9ee1bba` — OLM-SOP-008 Obsidian Vault Conventions
- Reserved: OLM-SOP-010 (agent-creation-flow.md, pending conversion)
- Reserved: OLM-SOP-011 (agent-modification-flow.md, pending conversion)
- `Team/Members/Registro.md`

## Revision History

| Version | Date | Author | Description of Change |
|---------|------|--------|----------------------|
| v1.0 | 2026-06-05 | Poros | Adopted to OLM-SOP format. Added Purpose, Scope, Responsibilities, Definitions. Restructured into Rules + Procedure. Updated references to hashes. |
