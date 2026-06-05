---
title: "Design-First, Test-Gated Development Workflow"
type: sop
doc_id: OLM-SOP-005
version: v1.0
status: active
effective_date: "2026-06-05"
review_date: "2026-12-05"
author: "Efesto"
scope: team
tags: [sop, workflow, design, testing, quality]
---

# Design-First, Test-Gated Development Workflow

## Purpose

Define the mandatory development workflow for every substantial system change: design first, implement second, test incrementally. Prevents code-first shortcuts, ensures each step is verified before the next begins.

## Scope

**Applies to:** All substantial system modifications — new tools (Efesto), new agents (Atena), architectural changes (MCP server, task manager, handoff), significant refactoring.

**Partial applicability:** Minor tool changes require a brief design document. Urgent bugfixes may bypass the flow but MUST document the deviation.

**Excluded from:** Routine operations, documentation edits, configuration changes not affecting system behavior.

## Responsibilities

| Role | Responsibility |
|------|---------------|
| **Efesto** | Follows this workflow for all code/tool changes. Creates design documents. Tests incrementally. |
| **Atena** | Follows this workflow for agent creation/modification. |
| **Poros** | Routes development work to Efesto/Atena with this SOP as reference. |

## Definitions

| Term | Meaning |
|------|---------|
| **Design document** | A structured document defining objective, architecture, implementation checklist with completion criteria, and verification tests |
| **Test gate** | A completion criterion that MUST pass before the next step begins |
| **Deviation** | A documented exception where the standard flow is not followed |

## Rules

1. No code MUST be written before the design document exists. Writing code before designing is a violation.
2. Each implementation step MUST have a completion criterion defined in the design document before work begins.
3. A step MUST NOT start until the previous step is completed AND tested.
4. All steps MUST be completed and tested before the work is reported as finished.
5. Bugfixes may bypass the flow only if the deviation is documented. The design document MUST be written retroactively.
6. Task tracking MUST use `synapsis_task` for all states and events.
7. The design document MUST be stored in `Library/deliverables/`.

## Procedure

### Phase 1: Design Document

Before writing any code, create a design document:

```markdown
## Design: [Title]

### Objective
What we want to achieve. Why. Which problem it solves.

### Architecture
How it works. Components, data flow, interfaces.

### Implementation Checklist
- [ ] Step 1: [what] — *completion criterion: [test/verification]*
- [ ] Step 2: [what] — *completion criterion: [test/verification]*
- [ ] Step N: [what] — *completion criterion: [test/verification]*

### Verification
How each step is verified. What must happen for "done well".
```

Save to `Library/deliverables/<name>.md`.

### Phase 2: Task Creation

Create a parent task via `synapsis_task(act="create", desc="Design: <title>", owner="<agent>")`.

Each checklist step becomes a subtask:

```
T-XXX-001  "Design: [Title]"                    (parent, in_progress)
  ├── T-XXX-002  "Log"                          (subtask, in_progress — NEVER CLOSED)
  ├── T-XXX-003  "Step 1: [what]"               (subtask, pending)
  ├── T-XXX-004  "Step 2: [what]"               (subtask, pending)
  └── T-XXX-005  "Step N: [what]"               (subtask, pending)
```

### Phase 3: Implementation Step-by-Step

For each step:

1. `synapsis_task(act="update", tid="T-XXX-NNN", status="in_progress")`
2. Implement (code, configuration, documentation)
3. Run the test/verification defined in the design document
4. If test fails → fix → retry
5. If test passes → check the checkbox in the design document
6. `synapsis_task(act="update", tid="T-XXX-NNN", status="completed")`
7. `synapsis_task(act="log", tid="T-XXX-NNN", evt="Step N completed: [test result]")`
8. Proceed to next step

**Rule:** Do NOT start step N+1 until step N is completed and tested.

### Phase 4: Closure

Only when ALL steps are completed:

1. Verify all checkboxes are checked
2. Verify all tests pass
3. Report completion to the user
4. User confirms → close the Log subtask → parent auto-completes

### Deviation Procedure

If the flow cannot be followed (urgent bugfix, exploratory prototype):

1. Document deviation: `synapsis_task(act="log", evt="deviation: <reason>")`
2. The design document MAY be written after implementation, but MUST be written
3. Tests REMAIN mandatory

### Trigger Table

| Change Type | Flow Required | Notes |
|---|---|---|
| New tool/automation | ✅ Full flow | Efesto |
| New agent | ✅ Full flow | Atena |
| Architectural change (MCP, task mgmt, handoff) | ✅ Full flow | |
| Significant refactoring | ✅ Full flow | |
| Minor tool change | ⚠️ Brief design doc | Still required but shorter |
| Urgent bugfix | ⚪ Deviation allowed | Must document deviation + write design doc retroactively |

## References

- `900191a0` — OLM-SOP-003 Agent Design Methodology
- `cb870dc6` — OLM-SOP-002 Handoff Guide
- `Library/deliverables/` — Design document storage path

## Revision History

| Version | Date | Author | Description of Change |
|---------|------|--------|----------------------|
| v1.0 | 2026-06-05 | Efesto | Adopted to OLM-SOP format. Translated to English. Updated legacy taskmanager tools to synapsis equivalents. Restructured into Rules + Procedure. |
