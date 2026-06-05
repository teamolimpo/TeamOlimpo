---
title: OpenCode Permissions — Official Reference
aliases: [opencode-permissions]
tags: [reference, opencode, permissions]
source: https://opencode.ai/docs/permissions
retrieved: 2026-05-20
---

# OpenCode Permissions

Source: https://opencode.ai/docs/permissions

Verified against official docs at retrieval date. If in doubt, check the source.

---

## Permission States

Each permission resolves to one of:

| Value | Behavior |
|-------|----------|
| `"allow"` | Run without approval |
| `"ask"` | Prompt for approval |
| `"deny"` | Block the action |

---

## Available Permission Keys

| Key | Description | Pattern matching |
|-----|-------------|-----------------|
| `read` | Reading a file | file path |
| `edit` | **All** file modifications (covers `edit`, `write`, `patch`) | file path |
| `glob` | File globbing | glob pattern |
| `grep` | Content search | regex |
| `bash` | Running shell commands | parsed commands (e.g. `git status --porcelain`) |
| `task` | Launching subagents | subagent type |
| `skill` | Loading a skill | skill name |
| `lsp` | Running LSP queries | currently non-granular |
| `question` | Asking the user questions during execution | — |
| `webfetch` | Fetching a URL | URL |
| `websearch` | Web search | query |
| `external_directory` | Accessing paths outside the project directory | path |
| `doom_loop` | Prevents identical repeated tool calls | — |

**Critical: `write` is NOT a separate permission key.** `edit` covers all file modifications — creation, editing, patching, deletion. Using `write: allow` in frontmatter has no effect.

---

## Defaults

If unspecified, OpenCode starts from permissive defaults:

- Most permissions default to `"allow"`.
- `doom_loop` and `external_directory` default to `"ask"`.
- `.env` and `.env.*` files are denied by default for `read` (exception: `.env.example`).

---

## Pattern Matching

- `*` — matches zero or more of any character
- `?` — matches exactly one character
- `~` / `$HOME` — home directory expansion (at start of pattern only)
- All other characters match literally

**Last matching rule wins.** Place catch-all (`"*"`) rules first, specific rules after.

---

## Configuration Formats

### Agent Markdown frontmatter (used by Team Olimpo)

```yaml
permission:
  read: allow
  edit:
    "Team/Handoff/**": "allow"
    "Team/<AgentName>/**": "allow"
    "[ROLE_PATH/**]": "allow"
```

Agent-level permissions override global workspace config.

### Global JSON config (`opencode.json`)

```json
{
  "permission": {
    "*": "ask",
    "bash": "allow",
    "edit": "deny"
  }
}
```

You can also set all permissions at once:

```json
{
  "permission": "allow"
}
```

### Granular object syntax (global JSON)

```json
{
  "permission": {
    "bash": {
      "*": "ask",
      "git *": "allow",
      "npm *": "allow"
    },
    "edit": {
      "*": "deny",
      "packages/web/src/content/docs/*.mdx": "allow"
    }
  }
}
```

### Per-agent override (global JSON)

```json
{
  "agent": {
    "build": {
      "permission": {
        "bash": {
          "*": "ask",
          "git *": "allow"
        }
      }
    }
  }
}
```

---

## External Directories

Use `external_directory` to allow tool calls that touch paths outside the working directory.

```json
{
  "permission": {
    "external_directory": {
      "~/projects/personal/**": "allow"
    }
  }
}
```

Paths allowed via `external_directory` inherit the same defaults as the workspace. You can layer additional restrictions:

```json
{
  "permission": {
    "external_directory": {
      "~/projects/personal/**": "allow"
    },
    "edit": {
      "~/projects/personal/**": "deny"
    }
  }
}
```

---

## Team Olimpo — Usage

Every agent must always have at minimum:

```yaml
permission:
  read: allow
  edit:
    "Team/Handoff/**": "allow"
    "Team/<AgentName>/**": "allow"
    "[ROLE_PATH/**]": "allow"
```

- `edit` path restriction is best practice. Flat `edit: allow` only for orchestrators.
- Agent template: `Team/Meta/agent-template-bozza.md`
- Design methodology: `Team/SOPs/900191a0`
- Consult this file during agent creation to set correct permissions.
