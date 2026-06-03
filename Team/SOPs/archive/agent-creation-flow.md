---
title: Agent Creation Flow — Team Olimpo
aliases: [agent-creation-flow, member-creation-flow]
tags: [sops, flow, agents, creation]
---

# Agent Creation Flow — Team Olimpo

For **new agents only**. For modifications, see `agent-modification-flow.md`.

---

## Flow

| Step | Actor | Action | Output | User Gate |
|------|-------|--------|--------|-----------|
| 1 | User | Request new agent to Poros | — | — |
| 2 | Poros | Clarify: domain, boundaries, team gaps | — | ✅ User approves direction |
| 3 | Researcher | Domain research | handoff `type:profile` `slug:research-<name>` | — |
| 4 | Reviewer | Review research (gaps, quality, coverage) | handoff `type:analysis` `slug:review-research-<name>` | — |
| 5 | Poros | Route research handoff + review handoff to user for discussion | — | ✅ User approves research |
| 6 | Designer | Design agent — create both files | handoff `type:profile` `slug:design-<name>` | — |
| 7 | Reviewer | Review design (structure, coherence, boundaries) | handoff `type:analysis` `slug:review-design-<name>` | — |
| 7b | Designer ↔ Reviewer | Iterate if needed (max 2 cycles) | handoff per cycle | — |
| 8 | Poros | Present final design to user | — | ✅ User approves design |
| 9 | Designer | Create `.opencode/agents/<name>.md` + `Team/Members/<name>.md` + update `Team/Members/Registro.md` | handoff `type:report` `slug:agent-<name>-created` | — |
| 10 | Poros | Activate agent, update Scratchpad | — | — |

## Handoff naming

All handoffs follow `Team/SOPs/handoff-guide.md`:

```
YYYY-MM-DD_HHMM_<agent>_<type>_<slug>.md
```

Example for agent "Apollo":
```
2026-05-19_1030_proteo_profile_research-apollo.md
2026-05-19_1145_metis_analysis_review-research-apollo.md
2026-05-19_1400_atena_profile_design-apollo.md
2026-05-19_1500_metis_analysis_review-design-apollo.md
2026-05-19_1600_atena_report_agent-apollo-created.md
```

## Routing rules

**Every handoff IS the brief for the next actor.** Poros does not write a new brief — he passes the previous handoff's file path to the next agent.

- Step 3→4: tell Metis: "Read `path/to/research-handoff.md` — review for gaps"
- Step 6→7: tell Metis: "Read `path/to/design-handoff.md` — review for issues"  
- Step 7→7b (iteration): tell Atena: "Read `path/to/review-handoff.md` — address every issue"

## Iteration rules

- Gaps in research (step 4) → re-brief researcher, new handoff `-v2`
- Issues in design (step 7) → route to designer with review handoff, revised design handoff `-v2`
- Max 2 cycles per step, then escalate to user

## What each actor produces

See the referenced SOP for full specs:

| File | Specs in |
|------|----------|
| `.opencode/agents/<name>.md` | `agent-design-methodology.md` — Agent file structure + Prompt Minimal Standard |
| `Team/Members/<name>.md` | `agent-design-methodology.md` — Member identity file |
| Gap analysis / review handoff | `agent-review-flow.md` — Review checklist + reporting format |

## References
- `Team/SOPs/agent-design-methodology.md`
- `Team/SOPs/agent-review-flow.md`
- `Team/SOPs/agent-modification-flow.md`
- `Team/SOPs/handoff-guide.md`
- `Team/Members/Registro.md`
