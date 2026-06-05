---
title: "Handoff — Agent Output Specification & Procedure"
type: sop
doc_id: OLM-SOP-002
version: v1.0
status: active
effective_date: "2026-06-05"
review_date: "2026-12-05"
author: "Poros"
scope: team
tags: [sops, handoff, workflow]
aliases: [handoff-guide, handoff]
---

# Handoff — Agent Output Specification & Procedure

## Purpose

Define the handoff protocol every agent must follow when returning results to Poros. Every agent invocation ends with a handoff file — no exceptions. This SOP ensures consistent structure, complete metadata, and machine-parseable output across all agents.

## Scope

**Applies to:** Every agent in Team Olimpo, every invocation. Both successful completions and failed/blocked executions.

**Does not apply to:** Orchestrator responses directly to the user (Poros synthesizes, doesn't write handoffs). External communications.

## Responsibilities

| Role | Responsibility |
|------|---------------|
| **Worker agent** | Writes the handoff before returning control. Sets accurate status and deviation fields. |
| **Poros** | Reads the handoff, evaluates status, synthesizes results for the user. Routes failed handoffs to the correct fix path. |

## Definitions

| Term | Meaning |
|------|---------|
| **Handoff** | Structured Markdown file produced by an agent upon task completion. Contains summary, deliverables, findings, and optional wiki section. |
| **Deviation** | Any situation where the agent could not execute the task as specified — blocker, error, incomplete output, or unexpected result. |

## Rules

1. Every agent invocation MUST write exactly one handoff file before returning control. No exceptions.
2. Every handoff MUST use `synapsis_hf(act="new", ...)` — never write handoff files with `Write` or `edit`.
3. The `st` field MUST be set to `done`, `fail`, or `hold`. `kill` is reserved for Poros only.
4. `st: fail` or `st: hold` MUST include a `note` explaining why.
5. If `deviation.outcome == 'open'`, the `st` field MUST be `fail`.
6. If `st: hold`, the handoff MUST include a `next_action` sentence addressed to Poros.
7. All handoffs MUST include a `## Summary` section (3-5 lines, self-contained).
8. Parameter values (`type`, `agent`, `prio`, etc.) MUST use valid options from the tables below. Custom values are not permitted.
9. The `## Wiki` section MAY be omitted. When present, `kind`, `title`, `path`, and `summary` are required.

## Procedure

### 1. Create the handoff

Use `synapsis_hf(act="new", ...)` with these parameters:

| Parameter | Required | Notes |
|-----------|----------|-------|
| `act` | ✅ | `"new"` to create, `"get"` to read |
| `type` | ✅ | See [Valid types](#2-valid-types) |
| `title` | ✅ | Max 60 characters |
| `body` | ✅ | Free Markdown content |
| `agent` | ✅ | Lowercase agent name (e.g. `efesto`, `proteo`) |
| `task` | — | Assigned by Poros at task start (e.g. `T-042`) |
| `note` | — | What was done, deviations, operational notes |
| `st` | — | `done` / `fail` / `hold` / `kill`. Default: `done` |
| `prio` | — | `high` / `med` / `low` / `crit`. Default: `med` |
| `refs` | — | File paths to artifacts produced |
| `devi` | — | See [Deviation block](#6-deviation-block) |

**Do not set:** `ref`, `data`, `timestamp`, `agent` in the body — the tool adds these automatically.

### 2. Valid types

| Type | Content |
|------|---------|
| `report` | Completed operation results, statistics |
| `profile` | Competency profile for a role or AI agent |
| `spec` | Technical specification, design decision |
| `test` | Test scenarios, acceptance criteria |
| `analysis` | Research output, strategic analysis |
| `note` | Non-actionable information, announcements |
| `bug` | Bug detected during execution — routes to Efesto |
| `feedback` | Non-bug quality signal: limitation, degradation |

### 3. Valid statuses

| st | Who | When |
|----|-----|------|
| `done` | Agent | Invocation finished with usable output |
| `fail` | Agent | Unresolvable blocker — output absent or partial |
| `hold` | Agent | Blocked but recoverable — awaiting dependency |
| `kill` | **Poros only** | Never write this yourself |

### 4. Write the body

Every handoff body MUST follow this structure:

```markdown
## Summary

[3-5 lines: what was done, for whom, main result. Must be self-contained.]

## Deliverable

- [file/output created with relative path]

## Key Findings

- [Concrete verifiable finding]
- [Max 5 findings]

## Wiki                             # optional — see specification below

kind: concept
title: Wiki Page Name
path: concepts/2026/05/short-slug
summary: >-
  2-3 sentence summary, self-contained, readable out of context.
tags: [tag1, tag2]
sources:
  - "Library/Handoff/2026/06/03/handoff-code.md"
confidence: CONFIRMED

## Deviations                       # optional — only if deviation from spec

- [deviation description]

## Next Steps                        # optional

- [recommended next action]
```

### 5. Wiki section specification

The `## Wiki` section is optional but strongly recommended for `report`, `analysis`, `profile`, and `spec` handoffs. When present, the MCP handoff server parses it to create or update a wiki page in `Library/Wiki/`.

**Fields:**

| Field | Required | Values | Notes |
|-------|:-------:|--------|-------|
| `kind` | ✅ | `concept` / `entity` / `comparison` / `overview` / `decision` / `research` | Classifies content |
| `title` | ✅ | String (max 60 chars) | Wiki page title |
| `path` | ✅ | `{kind}s/YYYY/MM/short-slug` | Relative to `Library/Wiki/` |
| `summary` | ✅ | 2-3 sentences (max 300 chars recommended) | Must be self-contained |
| `tags` | — | Array of strings | For FTS5 search |
| `sources` | — | Array of handoff paths | Provenance |
| `confidence` | — | `CONFIRMED` / `PARTIALLY_CONFIRMED` / `UNCONFIRMED` | Default: CONFIRMED |

**When to include:**

| Handoff type | Wiki recommended? | Notes |
|:-----------:|:----------------:|-------|
| `report` | ✅ Recommended | If it generates new knowledge |
| `analysis` | ✅ Recommended | Research = knowledge to preserve |
| `profile` | ✅ Recommended | Agent/competency profiles |
| `spec` | 🔶 If relevant | Only architectural decisions |
| `test` | ❌ | Unless it discovers unexpected patterns |
| `note` | ❌ | Announcements, unstructured info |
| `bug` | ❌ | Unless it documents a workaround |
| `feedback` | ❌ | Quality signals, not knowledge |

**Rules:**
- `## Wiki` is optional. Its absence does not cause errors.
- If present, `kind`, `title`, `path`, and `summary` are required.
- The wiki path must not overwrite existing pages (non-blocking warning).
- Not all handoffs produce wiki knowledge — use judgment.

### 6. Deviation block

Include when execution hit a blocker, error, or incomplete output.

```yaml
deviation:
  type: "tool_failure | output_incomplete | missing_input | other"
  description: "brief description"
  cause: "identified cause"
  corrective_action: "what was done to resolve"
  outcome: "resolved | workaround | open"
  user_impact: false
```

If `outcome: open` → `st` MUST be `fail`.

### 7. `next_action`

One sentence addressed to Poros. Required when `st: hold`.

```yaml
# Route to specialist
next_action: "Poros: suggest delegating encoding fix to Efesto before resuming T-042"

# Return to user
next_action: "Output ready for user. No further action needed."

# Blocked with recovery hint
next_action: "Poros: blocked on missing loguru — requires Efesto fix before T-038 can resume"
```

### 8. `quality_score`

Self-assessed by the producing agent.

| Score | Meaning |
|-------|---------|
| 1 | Unusable output |
| 2 | Partial or significantly flawed |
| 3 | Functional but improvable |
| 4 | Meets expectations |
| 5 | Exceeds expectations |

## Examples

### A — Standard completed report

```yaml
# synapsis_hf(act="new", ...):
act: new
type: report
title: "Fixed loguru import in pdf_converter"
body: "47/50 files converted. 3 skipped: encoding issue in nk-2400-*.md."
agent: efesto
task: T-042
note: "Added loguru to pyproject.toml, all tests pass"
st: done
prio: med
```

### B — Blocked with bug

```yaml
# synapsis_hf(act="new", ...):
act: new
type: bug
title: "ModuleNotFoundError: loguru in pdf_converter"
body: "See deviation block for details."
agent: clio
st: fail
prio: high
note: "Blocked on missing dependency — delegate fix to Efesto before T-038 resumes"
devi: '{"type": "tool_failure", "description": "ModuleNotFoundError", "cause": "Missing dependency", "corrective_action": "None", "outcome": "open", "user_impact": true}'
```

## References

- `OLM-SOP-001-sop-format.md` — SOP format standard
- `900191a0` — agent file conventions
- `synapsis_hf` tool documentation

## Revision History

| Version | Date | Author | Description of Change |
|---------|------|--------|----------------------|
| v1.0 | 2026-06-05 | Poros | Adopted to OLM-SOP format standard. Added Purpose, Scope, Responsibilities, Definitions. Translated Italian to English. Restructured into Rules + Procedure sections. |
