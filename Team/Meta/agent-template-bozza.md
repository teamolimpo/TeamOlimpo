---
title: Agent Template — Draft
aliases: [agent-template]
tags: [draft, template, agents, design]
draft: true
---

# Agent Template — Draft

> **DRAFT** — validate before promoting to `Team/SOPs/`.
> Based on: EN profile translations, third-party AI audit (2026-05-20), Atena v2 structural revision.

---

## Full Structure

```
---
description: "[ROLE] for [SCOPE]. Use when [TRIGGER INVOCATION]."
mode: subagent
model: opencode/big-pickle
permission:
  read: allow                          # everyone reads everything
  [bash / websearch / webfetch / task] # role-specific
  edit:
    "Team/Handoff/**": "allow"         # everyone writes handoffs
    "Team/<AgentName>/**": "allow"     # everyone writes own folder
    "[ROLE_PATH/**]": "allow"          # role-specific outputs
---

# [Name] — [Role]

[Who I am and what I do — one line.]
Does NOT [X], [Y], [Z].

## Identity

2-4 sentences. Who you are, what you do, how you do it.

## Communication Style

- **Tone**: [adjective1], [adjective2].
- **Style**: [operational description].

## Operating Rules

1. **Rule 1** — explanation.
2. **Rule 2** — explanation.
3. **Rule 3** — explanation.

## Competencies

### [Competency 1]
Operational description: when to use it, how to apply it, what it produces.

### [Competency 2]
Operational description.

### [Competency 3]
Operational description.

## Workflows

### [Workflow Name] — [brief description]

1. **INPUT** — [what you receive / from whom]
   Action: [what you do]
   OUTPUT: [what you produce]

2. **INPUT** — [what you receive / from whom]
   Action: [what you do]
   OUTPUT: [what you produce]

## Interactions   *(optional — for agents with defined I/O contracts)*

**Receive:** [from whom, format]
**Produce:** [artifact, destination path]

## Limitations

- [What you do NOT do — explicit.]
- [What you do NOT do — explicit.]

## References

- Agent design methodology: `Team/SOPs/agent-design-methodology.md`
- Handoff format: `Team/SOPs/handoff-guide.md`
```

---

## Section specs

### 1. Frontmatter

```
description: "[ROLE] for [TEAM/SCOPE]. Use when [TRIGGER INVOCATION]."
```

- ~150-200 characters
- Contains role + trigger ("Use when...")
- Zero agent names
- Unique among all agents

```
permission:
  read: allow
  [bash / websearch / webfetch / task]  # role-specific
  edit:
    "Team/Handoff/**": "allow"          # every agent
    "Team/<AgentName>/**": "allow"      # every agent
    "[ROLE_PATH/**]": "allow"           # role-specific
```

**Base rule** — every agent always gets:
- `read: allow`
- `edit: Team/Handoff/**`
- `edit: Team/<AgentName>/**`

**Role-specific extras:**

| Role | Add permission | Add path |
|------|---------------|----------|
| Code / scripts | `bash: allow` | `tools/**` |
| Web research | `websearch + webfetch: allow` | — |
| Content writing | — | `Library/documents/**`, `Library/deliverables/**` |
| Orchestrator | `task: allow` | full access (no path restriction) |

**Rules:**
- `edit` must be path-restricted for most agents — flat `edit: allow` only for orchestrators with documented justification
- `write` is **not a valid OpenCode permission key** — never use it. `edit` covers all file writes
- Never `bash: deny` / `task: deny` — omission is sufficient
- See `Team/Meta/opencode-permissions-spec.md` for full reference

---

### 2. Header comment

```
# [Name] — [Role]

[Who I am and what I do — one line.]
Does NOT [X], [Y], [Z].
```

Format: **plain text** (not HTML comment), 2 lines after H1, before first `##`.

---

### 3. Identity

2-4 prose sentences. No bullet lists, no decorative Archetype.

---

### 4. Communication Style

Tone, style. Include an explicit language directive (e.g. `Always reply in English.`) in the first bullet — do not rely on implicit context.

---

### 5. Operating Rules

Non-negotiable rules. First rule always:

1. **Reference canonical guides, never duplicate their content.**

---

### 6. Competencies

Each competency in `###` block with operational description. Do not list capabilities without context.

---

### 7. Workflows

Each step: **INPUT → Action → OUTPUT**. Never process without steps.
If the workflow is already in an SOP, reference it — do not rewrite it.

---

### 8. Interactions *(optional)*

Define structured I/O contracts if the agent has fixed interfaces (receive from X, produce Y at path Z).
Skip if the agent's I/O is entirely dynamic (e.g. Poros orchestrator).

Format:
```
**Receive:** [from whom, format]
**Produce:** [artifact, destination path]
```

---

### 9. Limitations

Explicit. No "Don't do things outside your scope".

---

### 10. References

SOP paths only. No content duplication.

**Always consult:**
- `Team/Meta/opencode-permissions-spec.md` — for permission keys, syntax, and rules
- `Team/SOPs/agent-design-methodology.md` — for design methodology
- `Team/SOPs/handoff-guide.md` — for handoff format
