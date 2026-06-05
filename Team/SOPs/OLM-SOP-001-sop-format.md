---
title: "SOP Format — Standard for Writing Standard Operating Procedures"
type: sop
doc_id: "OLM-SOP-001"
version: "v2.0"
status: active
effective_date: "2026-06-05"
review_date: "2026-12-05"
author: "Poros"
scope: team
tags: [sops, meta, format, convention, sop-format]
aliases: [meta-sop, sop-standard]
supersedes: "c643ae7e"
---

# SOP Format — Standard for Writing Standard Operating Procedures

## Purpose

Define the format, structure, and conventions every SOP in Team Olimpo must follow — whether team-wide or private. Use this SOP as a template when creating or revising any SOP. Following it guarantees consistency, searchability, and verifiability across all procedures.

## Scope

**Applies to:** All Standard Operating Procedures created or revised after the effective date of this SOP. Both team SOPs (`Team/SOPs/`) and private SOPs (`Library/SOPs/`).

**Does not apply to:** Agent prompt files (`.opencode/agents/`), which follow `900191a0`; handoff files, which follow `OLM-SOP-002-handoff-guide.md`; or one-off notes.

## Responsibilities

| Role | Responsibility |
|------|---------------|
| **Author** | Writes the SOP following this format. Ensures technical accuracy of content. |
| **Poros** | Owns this SOP. Reviews for format compliance before approving. Updates on process changes. |
| **Reader (any agent)** | Follows the SOP. Logs suggested improvements or deviations. |

## Definitions

| Term | Meaning |
|------|---------|
| **SOP** | Standard Operating Procedure — a documented, repeatable process instruction |
| **team scope** | SOP stored in `Team/SOPs/`, git-tracked, visible to all team members |
| **private scope** | SOP stored in `Library/SOPs/`, not git-tracked, for individual use |
| **MUST** | Absolute requirement (RFC 2119). Violation = SOP not followed |
| **SHOULD** | Recommended. Deviation requires documented justification |
| **MAY** | Optional. Entirely at reader's discretion |

## File Naming

Every SOP file MUST follow this convention:

```
{doc_id}-{slug}.md
```

| Part | Rule | Example |
|------|------|---------|
| `doc_id` | The document ID from frontmatter | `OLM-SOP-001` |
| `slug` | Lowercase, hyphens, describes procedure not role | `sop-format` |

Full examples:
- `OLM-SOP-001-sop-format.md` (this file)
- `OLM-SOP-002-handoff-guide.md`
- `900191a0`

**Why:** The doc_id prefix makes every SOP findable by filename alone. `ls Team/SOPs/` shows every SOP with its ID. No cross-reference index needed.

## Frontmatter

Every SOP MUST start with YAML frontmatter containing these fields:

| Field | Required | Value | Notes |
|-------|----------|-------|-------|
| `title` | ✅ | Human-readable string | H1 must match exactly |
| `type` | ✅ | `sop` | Always `sop` |
| `doc_id` | ✅ | Hierarchical ID | Prefix defines domain |
| `version` | ✅ | semver | `v1.0`, `v2.1` — MAJOR.MINOR |
| `status` | ✅ | `draft`, `active`, `review`, `retired` | Lifecycle state |
| `effective_date` | ✅ | ISO date `YYYY-MM-DD` | Date SOP becomes valid |
| `review_date` | ✅ | ISO date `YYYY-MM-DD` | ≤12 months from effective |
| `author` | ✅ | Agent or person name | Who wrote this version |
| `scope` | ✅ | `team` or `private` | Determines storage directory |
| `tags` | ✅ | List of keywords | Always include `sops` |
| `aliases` | — | List of strings | Alternative names for search |
| `supersedes` | — | doc_id of previous version | Links to replaced version |

## Rules

1. Every SOP MUST have a unique `doc_id` following the numbering convention defined in this document.
2. Every SOP MUST have a `version` field in semver format (`v1.0`, `v1.1`, `v2.0`).
3. Every SOP MUST have an `effective_date` and a `review_date`. Review date MUST be within 12 months of effective date.
4. The H1 title MUST match the frontmatter `title` field exactly.
5. Every section listed under Required Sections MUST appear in the defined order. Empty sections are not permitted.
6. Every rule inside the SOP MUST use MUST/SHOULD/MAY consistently (RFC 2119) and MUST be independently verifiable.
7. All procedure steps MUST use imperative mood, active voice.
8. Definitions section MUST be present when the SOP contains technical terms, acronyms, or abbreviations.
9. References section MUST be present when the SOP cites other SOPs, standards, or external documents.
10. Revision History MUST be present as the final section and MUST contain at least the current version entry.
11. Every SOP SHOULD be concise. If a procedure exceeds 200 lines, consider splitting into multiple SOPs.
12. Vague language (periodically, as needed, normally, typically) SHOULD NOT appear in procedure steps.
13. Every SOP SHOULD have a changelog entry when any modification is made, including "Reviewed, no changes required."
14. The YAML frontmatter MUST be the first line of the file — no blank lines before `---`.

## Procedure — How to Write an SOP

### Step 1: Assign identifiers

1. Determine the `doc_id` using the convention: `{PREFIX}-SOP-{NNN}` where:
   - `OLM` for Team Olimpo core
   - `HND` for handoff protocols
   - `TLS` for tool-specific procedures
   - Other prefixes as needed for new domains
2. Determine the filename: `{doc_id}-{slug}.md` where `slug` is a short English description in lowercase-hyphens.
   - Example: doc_id `OLM-SOP-002` + slug `handoff-guide` → `OLM-SOP-002-handoff-guide.md`
3. Set `version` to `v1.0` for new SOPs.
4. Set `status` to `draft` until the SOP is ready for use, then `active`.

### Step 2: Write frontmatter

Use the following template. Fields marked with `*` are required. Save the file as `{doc_id}-{slug}.md`.

```yaml
---
title: "Descriptive SOP Title"              # * H1 must match exactly
type: sop                                     # * Always sop
doc_id: "OLM-SOP-XXX"                        # * Unique document ID — also used as filename prefix
version: "v1.0"                              # * semver MAJOR.MINOR
status: "active"                             # * draft | active | review | retired
effective_date: "2026-06-05"                 # * Date SOP becomes valid
review_date: "2026-12-05"                    # * Scheduled review date
author: "Agent Name"                         # * Who wrote it
scope: team|private                          # * team → Team/SOPs/, private → Library/SOPs/
tags: [sops, domain-tag]                     # * Always include sops
aliases: [alt-name]                          # Alternative names for search
supersedes: ""                               # doc_id of previous version
---
```

### Step 3: Write required sections

In this exact order:

| # | Section | Content | Required |
|---|---------|---------|----------|
| 1 | **Title (H1)** | Matches frontmatter `title` | ✅ Always |
| 2 | **Purpose** | 1-3 lines: why this SOP exists, when to use it | ✅ Always |
| 3 | **Scope** | What it covers, what it doesn't, who it applies to | ✅ Always |
| 4 | **Responsibilities** | Who does what (by role, never by name) | ✅ Always |
| 5 | **Definitions** | Clarify terms, acronyms | ✅ If terms need clarification |
| 6 | **Rules** | Numbered MUST/SHOULD/MAY constraints | ✅ Always |
| 7 | **Procedure** | Step-by-step, active voice, numbered steps | ✅ If procedure is applicable |
| 8 | **References** | Related SOPs, standards, documents | ✅ If SOP cites external sources |
| 9 | **Revision History** | Changelog table (last 3-4 entries minimum) | ✅ Always |

### Step 4: Apply writing rules

1. **Imperative mood, active voice.** "Record the temperature." NOT "The temperature should be recorded."
2. **One action per step.** Break compound steps into numbered sub-steps.
3. **Specify measurable parameters.** Include exact values, tolerances, units. "Maintain between 35°C and 40°C." NOT "Keep at moderate temperature."
4. **Use tables** for structured data — thresholds, options, comparisons, parameter specs.
5. **Use code blocks** for file templates, command sequences, YAML/JSON configuration.
6. **No vague language.** Replace "Inspect periodically" with "Inspect before each batch (see Appendix A)."
7. **No philosophical justification.** State the rule, give an example, move on.
8. **Operational over descriptive.** Tell the reader what to do, not what to think.
9. **One topic per SOP.** Unrelated procedures belong in separate files.

### Step 5: Write Revision History

Record every change. Keep the last 3-4 entries visible.

```markdown
## Revision History

| Version | Date | Author | Description of Change |
|---------|------|--------|----------------------|
| v2.0 | 2026-06-05 | Poros | Updated to align with pharma GMP/ISO 9001 conventions |
| v1.0 | 2026-06-05 | Poros | Initial version |
```

### Step 6: Review and finalize

1. Run through the Review Checklist (see below).
2. If all checks pass, set `status: active` and `effective_date` to today.
3. Set `review_date` to 6 months from effective date (default) or 12 months maximum.

## Language

English only, regardless of scope. No code-switching.

## SOP Location Rules

| Scope | Directory | Git-tracked | Audience |
|-------|-----------|-------------|----------|
| `team` | `Team/SOPs/` | ✅ Yes (public) | All team members |
| `private` | `Library/SOPs/` | ❌ No (local) | Individual user |

## References

- `OLM-SOP-002` — Handoff Guide (`Team/SOPs/OLM-SOP-002-handoff-guide.md`)
- `OLM-SOP-003` — Agent Design Methodology (`Team/SOPs/900191a0`)
- RFC 2119 — Key words for use in RFCs to Indicate Requirement Levels
- ICH Q10 — Pharmaceutical Quality System (section 4 — documentation)
- FDA 21 CFR Part 211.100 — Written procedures; deviations
- ISO 9001:2015 — Clause 7.5 (Documented Information)
- ISPE GAMP 5 — Good Automated Manufacturing Practice

## Review Checklist

Before activating an SOP, verify:

- [ ] Frontmatter: doc_id, version, effective_date, review_date, author, scope, title all present?
- [ ] H1 title matches frontmatter `title` exactly?
- [ ] Purpose present and 1-3 lines?
- [ ] Scope present with both inclusion and exclusion?
- [ ] Responsibilities present with clear role-to-action mapping?
- [ ] Definitions present if the SOP uses technical terms?
- [ ] Rules numbered and use MUST/SHOULD/MAY consistently?
- [ ] Procedure steps use imperative mood, active voice?
- [ ] Revision History present as final section?
- [ ] References present if external sources are cited?
- [ ] Max 200 lines (split if longer)?
- [ ] English only, no code-switching?
- [ ] File naming: `{doc_id}-{slug}.md` format, lowercase, hyphens?
- [ ] Review date set to ≤12 months from effective date?

## Revision History

| Version | Date | Author | Description of Change |
|---------|------|--------|----------------------|
| v2.0 | 2026-06-05 | Poros | Full rewrite based on pharma GMP/ISO 9001 research by Proteo (T-GMP-001). Added doc_id, version, status, effective_date, review_date, author, supersedes fields. Added Scope, Responsibilities, Definitions, References, Revision History as required sections. Codified active voice, imperative mood, measurable parameters. Removed 150-line hard limit. File renamed to `OLM-SOP-001-sop-format.md` — filename includes doc_id prefix. |
| v1.0 | 2026-06-05 | Poros | Initial version |
