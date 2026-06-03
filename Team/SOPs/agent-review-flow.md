---
title: Agent Review Flow — Team Olimpo
aliases: [agent-review-flow, review-flow, gap-analysis-flow]
tags: [sops, flow, agents, review]
---

# Agent Review Flow — Team Olimpo

Used by creation flow (`agent-creation-flow.md`), modification flow (`agent-modification-flow.md`), and **as a standalone audit**.

**Standalone usage**: request "verify agent X" → reviewer runs full checklist → reports verdict.
- PASS / PASS WITH NOTES → done, user informed.
- FAIL → user decides: enter modification flow or dismiss.

---

## When review is needed

| Phase | Trigger | Reviewer | Output |
|-------|---------|----------|--------|
| Research review (creation) | After Proteo domain research | Metis | Gap analysis handoff |
| Design review (creation) | After Atena draft | Metis | Gap analysis handoff |
| Gap analysis (modification) | After Proteo reads existing files | Proteo | Gap analysis handoff |
| Conformity check (both) | After Atena applies changes | Clio | Verification handoff |

---

## What to check

All checks reference `agent-design-methodology.md` and `agent-creation-flow.md` as truth. Run the full checklist:

### `.opencode/agents/<name>.md`
- [ ] `description:` present, operational, ~150-200 chars, English, no agent names
- [ ] `mode:` present
- [ ] `model:` present and valid
- [ ] `permission:` present, proportional to role
- [ ] NO custom frontmatter fields
- [ ] Header comment: 2-3 lines, who/does/doesn't
- [ ] Operative instructions in body
- [ ] **Prompt Minimal Standard** — no decorative lines, self-reviewed
- [ ] Sections per 10-point template (frontmatter, header, identity, comm style, rules, competencies, workflows, interactions, limitations, references)
- [ ] No agent names referenced in body

### `Team/Members/<name>.md`
- [ ] Frontmatter: `type: member`, `agent: <name>`, `role: <role>` (lowercase, hyphenated)
- [ ] Title: `# <Name> — Team Olimpo`
- [ ] Sections: `## Identity`, `## Values`, `## Boundaries`, `## Dependencies`
- [ ] Written in English
- [ ] Dependencies list tools, SOPs, data sources — never other agents by name
- [ ] One file per agent

### `Team/Members/Registro.md`
- [ ] Row present with Date, Agent, Version, Notes
- [ ] Notes describe what changed

### Cross-checks
- [ ] No overlap between Core Rules and Guiding Principles sections
- [ ] No decorative adjectives (comprehensive, accurate, professional, seamless, polished, etc.)
- [ ] YAML frontmatter parses correctly
- [ ] Language: English throughout (domain-specific terms in Italian are acceptable)

---

## How to report

Produce a handoff via `synapsis_hf(act="new", ...)` with:

- **type**: `analysis` (gap analysis) or `report` (conformity check)
- **title**: `<Agent name> review — <phase>`

### Body structure

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

### Verdicts
- **PASS**: zero failures. May have minor notes. → proceed to next step.
- **PASS WITH NOTES**: zero failures, but N non-blocking observations. → proceed, notes documented.
- **FAIL**: one or more criteria fail. Blocking — must be fixed. → route back to designer for iteration.

In modification flow: max 2 FAIL cycles per gap analysis, then escalate to user. See `agent-modification-flow.md`.

---

## Routing rules

- Gap analysis handoffs go **verbatim** to the next actor (see `agent-creation-flow.md` — Routing principle & Gap analysis handoff rule)
- Poros does not filter, summarize, or rephrase
- Every gap must be addressed. Unexplained omission = protocol violation

## References
- `Team/SOPs/agent-design-methodology.md`
- `Team/SOPs/agent-creation-flow.md`
- `Team/SOPs/agent-modification-flow.md`
- `Team/SOPs/handoff-guide.md`
