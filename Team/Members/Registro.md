---
title: Agent Registry — Team Olimpo
tags: [registry, agents]
---

# Agent Registry

Updates to agent profiles.

| Date | Agent | Version | Notes |
|------|-------|---------|-------|
| 2026-05-20 | Atena | v2 | Full structural revision — added Identity, Interactions, anti-patterns, review methodology. Self-consistency fix. 97 lines. |
| 2026-05-20 | Tutti | SOUL v1 | SOUL files created in Team/Members/ for all 11 agents. Declarative identity, values, boundaries, dependencies. Minimalist prompts (-33.5% lines). |
| 2026-05-20 | Euterpe | v2 | Revisione post-Chimera: inglese, dipendenze agente rimosse, Prompt Minimal Standard |
| 2026-05-21 | Euterpe | v3 | Fix post-audit Clio: added References section, merged Core Rules/Guiding Principles into Operating Rules, separated Interactions/Limitations, removed Competency 6 (folded into rules + workflow) |
| 2026-05-21 | Clio | v1 | Post-audit Proteo: bash permission removed, Identity section added, `write` permission added, member file converted to English (type/title/dependencies), registry row added |
| 2026-05-21 | Proteo | v1 | Member file: type: soul → type: member, title SOUL → Team Olimpo, Italian → English, dependencies agent names removed. .opencode: description expanded (139→173 chars), "Professional" removed, header/comm style/competencies/interactions/limitations sections added. |
| 2026-05-21 | Poros | v1 | Member file: type/title/language/dependencies fixed. .opencode: description expanded (130→174 chars), permission bash removed, header/competencies/interactions/limitations sections added, agent names removed from body. |
| 2026-05-21 | Pythagoras | v1 | Member file: type/title/language/dependencies fixed. .opencode: full restructure — added comm style, operating rules, workflows (numbered + I/O), interactions, limitations, references. |
| 2026-05-21 | Hermione | v1 | Member file: type/title/language/dependencies fixed. .opencode: description trimmed (217→186 chars), Core Rules + Guiding Principles merged into Operating Rules, added comm style/interactions/references, removed "Clio" from body. |
| 2026-05-21 | Efesto | v1 | Member file: type/title/language/dependencies fixed. .opencode: added Identity, Interactions, References sections. |
| 2026-05-21 | Eunomia | v1 | Member file: type/title/language/dependencies fixed. .opencode: added header comment, Communication Style section. |
| 2026-05-21 | Metis | v1 | Member file: type/title/language/dependencies fixed. .opencode: added Communication Style section. |
| 2026-05-22 | Metis | v2 | Audit compliance: Red Flags aggiunte (2 tabelle, 16 righe), Limitations riscritte (6 confini strutturali), process optimization claim rimosso, contraddizioni risolte (decisions→options, no-names paradox), References pulito (1/3), HARD GATE awareness aggiunta, permessi → nuovo standard (lib/System/Metis/ + Team/Fucina/). 34/34 specifiche passanti. |
| 2026-05-22 | Efesto | v3 | Revisione completa pipeline Atena: permessi riscritti (deprecato Team/Efesto/ → lib/System/efesto/ + Team/Fucina/, write + task aggiunti), Red Flags 11 righe process-violation, Competencies 11 domini con contesto when/how (aggiunti tool lifecycle + refactoring + docs), 4 workflow tabellari con I/O (New Tool, Bug Fix, One-Shot, Maintenance), Operating Rules unificate con escalation triggers, Limitations 9 confini strutturali (con Hermione exception + overlap boundary), References puliti (5 riferimenti usati, rimossi obsidian-vault-conventions + agent-design-methodology). Member file sincronizzato. 24/24 specifiche passanti. |
| 2026-05-22 | Efesto | v2 | Revisione completa: permessi aggiornati (deprecato Team/Efesto/ → lib/System/efesto/ + Team/Fucina/, aggiunto write), Red Flags inserite (10 righe process-violation), Competencies arricchite con contesto when/how, Workflows riscritti con I/O (3 flussi: nuovo tool, bug fix, manutenzione), Standards fuso in Operating Rules, References corrette (rimosso obsidian-vault-conventions, aggiunti agent-design-methodology + config.yaml), Limitations espanse (7 confini). Member file sincronizzato. |
| 2026-05-21 | Dike | v1 | Member file: type/title/language/dependencies fixed. .opencode: added Communication Style section. |
| 2026-05-22 | Clio | v2 | Post-audit fix: permission path, member dependencies, Red Flags, header alignment |
| 2026-05-22 | Proteo | v2 | Post-audit fix: permission path, Red Flags, confidence framework, quality rubric, framework definitions, references cleanup |
| 2026-05-22 | Poros | v2 | Revisione completa — IntentGate (agent revision→Atena), Red Flags 8→13, HARD GATE qualificato, references aggiornate, permissions path-specific, GAP-1→8 fixati. Verificato da Clio. |
| 2026-05-28 | Efesto | v4 | Post-audit modification pipeline (Atena→Proteo→Clio→Metis). 7 findings: F-1 handoff enforcement (3-tier), F-2 deliverable tracking (synapsis_d_set), F-4 efesto-original.md archived, F-5 working dir initialized (lib/System/efesto/), F-6 task ownership (Step 0 + RF-13 + Limitation 9), F-7 self-audit (WF5, 20 invocations). +4 Operating Rules, +2 Red Flags (RF-12/13), 5 workflows (4 updated + WF5 new). MCP Variable Layer added. task:allow removed (leaf agent). Member names removed from Limitation 6. Path Library→lib fixed. 238 lines, 21KB. |
