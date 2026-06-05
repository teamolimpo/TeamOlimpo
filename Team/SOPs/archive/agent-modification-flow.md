---
title: Agent Modification Flow — Team Olimpo
aliases: [agent-modification-flow, member-modification-flow, agent-update-flow]
tags: [sops, flow, agents, modification]
---

# Agent Modification Flow — Team Olimpo

For **existing agents only**. For new agents, see `agent-creation-flow.md`.

**Trigger**: direct user request ("modify agent X") OR a standalone audit (via `3940eb53`) that returns FAIL.

---

## Flow

| Step | Actor | Action | Output | User Gate |
|------|-------|--------|--------|-----------|
| 1 | User | Request agent modification to Poros | — | — |
| 2 | Poros | Clarify scope: what changed, what needs updating | — | ✅ User approves direction |
| 3 | **Proteo** | Gap analysis: read both files, compare against current specs | handoff `type:analysis` `slug:gap-<name>` | — |
| 4 | Poros | Route the gap analysis handoff verbatim to Atena | — | — |
| 5 | **Atena** | Fix every gap in both files + update `Team/Members/Registro.md` | handoff `type:report` `slug:fix-<name>` | — |
| 6 | **Proteo** | Verify content gaps addressed, no regressions | handoff `type:report` `slug:verify-content-<name>` | — |
| 7 | **Clio** | Verify format/conformity per `3940eb53` checklist | handoff `type:report` `slug:verify-format-<name>` | ✅ Both verdicts determine next step |
| 8 | Poros | Present result to user | — | ✅ User approves / requests changes |

---

## Verdict handling

Steps 6 and 7 each produce a verdict. Both must pass.

| Proteo (content) | Clio (format) | Result | Next step |
|------------------|---------------|--------|-----------|
| PASS | PASS | ✅ Full pass | → Step 8 |
| PASS | PASS WITH NOTES | ✅ Pass with notes | → Step 8, notes documented |
| PASS | FAIL | ❌ Format issues | → Step 5 (Atena fixes format) |
| FAIL | any | ❌ Content issues | → Step 5 (Atena fixes content) |

Max 2 cycles of Step 5→6→7 per gap analysis. After 2 fails → escalate to user.

---

## Routing rules

**Every handoff IS the brief for the next actor.** Poros never writes a new brief when a handoff exists.

- **Step 4**: Tell Atena: "Read `path/to/gap-handoff.md` — fix everything it flags"
- **Step 5→6**: Tell Proteo: "Read `path/to/fix-handoff.md` — verify content gaps addressed"
- **Step 6→7**: Tell Clio: "Read `path/to/atena-fix-handoff.md` and `path/to/proteo-verify-handoff.md` — check format conformity"
- **FAIL → Step 5**: Tell Atena: "Read `path/to/fail-handoff.md` — fix remaining gaps"

---

## What each actor produces

| File | Specs in |
|------|----------|
| Gap analysis handoff | `3940eb53` — Review checklist + reporting format |
| `.opencode/agents/<name>.md` | `900191a0` — Agent file structure + Prompt Minimal Standard |
| `Team/Members/<name>.md` | `900191a0` — Member identity file |
| Content verification handoff | `3940eb53` — Proteo checks all original gaps addressed |
| Format verification handoff | `3940eb53` — Clio runs full checklist |

---

## References
- `900191a0` — OLM-SOP-003 Agent Design Methodology
- `3940eb53` — OLM-SOP-004 Agent Review Flow
- `Team/SOPs/agent-creation-flow.md`
- `cb870dc6`
- `Team/Members/Registro.md`
