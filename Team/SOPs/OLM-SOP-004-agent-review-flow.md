---
title: "Agent Review Flow — Standards for Agent File Quality Review"
type: sop
doc_id: OLM-SOP-004
version: v1.0
status: active
effective_date: "2026-06-05"
review_date: "2026-12-05"
author: "Clio, Metis"
scope: team
tags: [sops, flow, agents, review, audit]
aliases: [agent-review-flow, review-flow, gap-analysis-flow]
---

# Agent Review Flow — Standards for Agent File Quality Review

## Purpose

Define the review, gap analysis, and conformity check process for agent files. Used by creation pipeline, modification pipeline, and as a standalone audit. Ensures every agent file meets the OLM-SOP-003 standard before deployment.

## Scope

**Applies to:** All agent review activities: research review (after Proteo domain analysis), design review (after Atena draft), gap analysis (in modification flow), conformity checks (after changes applied).

**Does not apply to:** Orchestrator-level files (Poros), tool configurations, SOPs, or handoff files.

## Responsibilities

| Role | Responsibility |
|------|---------------|
| **Metis** | Conducts research review and design review for new agents. Produces gap analysis handoffs. |
| **Proteo** | Conducts gap analysis for modification flows. |
| **Clio** | Conducts conformity checks after Atena applies changes. |
| **Poros** | Routes handoffs verbatim. Does not filter, summarize, or rephrase. Escalates if max retry cycles reached. |

## Definitions

| Term | Meaning |
|------|---------|
| **Gap analysis** | Review comparing agent file against the OLM-SOP-003 standard, identifying missing or non-conforming sections |
| **Conformity check** | Structured verification that all checklist criteria pass before deployment |
| **PASS** | Zero failures; may include non-blocking notes |
| **FAIL** | One or more blocking criteria not met; must be fixed |

## Rules

1. Reviews MUST reference `900191a0` (OLM-SOP-003) as the truth source for agent file structure.
2. Every gap found MUST be addressed. Unexplained omission is a protocol violation.
3. Gap analysis handoffs MUST be routed verbatim to the next actor. Poros MUST NOT filter, summarize, or rephrase.
4. In modification flow, a maximum of 2 FAIL cycles per gap analysis is permitted before escalation to the user.
5. Verdicts MUST follow the PASS/PASS WITH NOTES/FAIL classification.
6. The reviewer MUST check both `.opencode/agents/<name>.md` and `Team/Members/<name>.md`.
7. Decorative adjectives (comprehensive, accurate, professional, seamless, polished) MUST be flagged as non-conforming.
8. YAML frontmatter MUST parse correctly for both agent and member files.

## Procedure

### 1. Determine review trigger

| Phase | Trigger | Reviewer | Output |
|-------|---------|----------|--------|
| Research review (creation) | After Proteo domain research | Metis | Gap analysis handoff |
| Design review (creation) | After Atena draft | Metis | Gap analysis handoff |
| Gap analysis (modification) | After Proteo reads existing files | Proteo | Gap analysis handoff |
| Conformity check (both) | After Atena applies changes | Clio | Verification handoff |

### 2. Run the full checklist

#### `.opencode/agents/<name>.md`

- `description:` present, operational, ~150-200 chars, English, no agent names
- `mode:` present
- `model:` present and valid
- `permission:` present, proportional to role
- NO custom frontmatter fields
- Header comment: 2-3 lines describing who/does/doesn't
- Operative instructions in body
- Prompt Minimal Standard — no decorative lines, self-reviewed
- Sections per 10-point template (frontmatter, header, identity, comm style, rules, competencies, workflows, interactions, limitations, references)
- No agent names referenced in body

#### `Team/Members/<name>.md`

- Frontmatter: `type: member`, `agent: <name>`, `role: <role>` (lowercase, hyphenated)
- Title: `# <Name> — Team Olimpo`
- Sections: `## Identity`, `## Values`, `## Boundaries`, `## Dependencies`
- Written in English
- Dependencies list tools, SOPs, data sources — never other agents by name
- One file per agent

#### `Team/Members/Registro.md`

- Row present with Date, Agent, Version, Notes
- Notes describe what changed

#### Cross-checks

- No overlap between Rules and Limitations sections
- No decorative adjectives (comprehensive, accurate, professional, seamless, polished, etc.)
- YAML frontmatter parses correctly
- Language: English throughout (domain-specific non-English terms are acceptable)

### 3. Produce review handoff

Use `synapsis_hf(act="new", type="analysis"|"report", title="<Agent> review — <phase>")`.

Body structure:

```markdown
## Summary
[Verdict: PASS / FAIL / PASS WITH NOTES]
[Total gaps found: N]

## Per-file results
### `.opencode/agents/<name>.md`
- ✅ [criterion] — passes
- ❌ [criterion] — what's wrong, where, what expected

### `Team/Members/<name>.md`
...

### `Team/Members/Registro.md`
...

## Notes
[Additional observations, non-blocking items]
```

### 4. Classify verdict

- **PASS**: zero failures. May have minor notes. → proceed to next step.
- **PASS WITH NOTES**: zero failures, N non-blocking observations. → proceed, notes documented.
- **FAIL**: one or more criteria fail. Blocking — must be fixed. → route back to designer for iteration.

In modification flow: max 2 FAIL cycles per gap analysis, then escalate to user.

### 5. Standalone usage

Request "verify agent X" → reviewer runs full checklist → reports verdict.

- PASS/PASS WITH NOTES → done, user informed.
- FAIL → user decides: enter modification flow or dismiss.

## References

- `900191a0` — OLM-SOP-003 Agent Design Methodology
- `cb870dc6` — OLM-SOP-002 Handoff Guide
- Reserved: OLM-SOP-00X (agent-creation-flow.md, pending conversion)
- Reserved: OLM-SOP-00Y (agent-modification-flow.md, pending conversion)

## Revision History

| Version | Date | Author | Description of Change |
|---------|------|--------|----------------------|
| v1.0 | 2026-06-05 | Clio, Metis | Adopted to OLM-SOP format. Purpose, Scope, Responsibilities, Definitions added. Restructured into Rules + Procedure. |
