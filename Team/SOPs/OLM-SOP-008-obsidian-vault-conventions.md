---
title: "Obsidian Vault Conventions — Library Structure and Formatting"
type: sop
doc_id: OLM-SOP-008
version: v1.0
status: active
effective_date: "2026-06-05"
review_date: "2026-12-05"
author: "Clio"
scope: team
tags: [sops, obsidian, conventions, vault]
aliases: [obsidian-vault-conventions, obsidian-vault]
---

# Obsidian Vault Conventions — Library Structure and Formatting

## Purpose

Define the structure, formatting, and linking conventions for `Library/` as an Obsidian vault. Ensures that every `.md` file, image, wikilink, and frontmatter block renders correctly when the vault is opened in Obsidian.

## Scope

**Applies to:** All `.md` files and assets written to `Library/`. Applies to any agent or tool that creates files in the vault (Clio cataloger, Efesto scripts, document converters).

**Does not apply to:** `Team/` directory, `.opencode/` directory, handoff files (outside vault scope).

## Responsibilities

| Role | Responsibility |
|------|---------------|
| **Clio** | Verifies every converted file has valid frontmatter, correct relative image paths, and valid wikilinks. |
| **Efesto** | Ensures all scripts writing `.md` to the vault produce valid frontmatter, relative image paths, and wikilinks for internal vault links. |
| **Any agent writing to Library/** | Follows all vault conventions. |

## Definitions

| Term | Meaning |
|------|---------|
| **Vault** | An Obsidian workspace — a directory of Markdown files with cross-linking, tags, and graph view |
| **Wikilink** | Obsidian-style internal link: `[[filename]]` or `[[filename|display text]]` |
| **Frontmatter** | YAML metadata block between `---` delimiters at the top of a file |
| **Slug** | Lowercase filename with spaces/special characters replaced by hyphens |

## Rules

1. Every `.md` file in `Library/` MUST have a valid frontmatter block with at minimum a `title` field.
2. All paths to images MUST be relative to the `.md` file location. Absolute paths (e.g., `C:\Users\...`, `/home/...`) and CWD-relative paths (e.g., `Library/assets/...`) are PROHIBITED.
3. Tags MUST use the plural form: `tags`, `aliases`, `cssclasses`. Singular forms (`tag`, `alias`, `cssclass`) are deprecated since Obsidian 1.4 and MUST NOT be used.
4. Image folders MUST use the document slug as directory name, placed under `Library/assets/images/<slug>/`.
5. Files with non-native extensions (`.xlsx`, `.db`, `.log`, `.yaml`) are treated as non-indexable attachments — they exist in the vault but are not opened as notes.
6. The `.obsidian/` directory MUST NOT be touched — it is Obsidian's internal configuration.
7. Dates in frontmatter MUST be ISO 8601 without quotes (e.g., `date: 2026-03-25`).

## Procedure

### 1. Frontmatter — required format

Every `.md` file in the vault MUST start with:

```yaml
---
title: Document title
tags: [tag1, tag2]
aliases: [alternative name]
---
```

#### Standard fields for PDF-converted documents

```yaml
---
title: Title extracted from PDF
source_pdf: original-name.pdf
converted_at: '2026-03-25 10:00:00'
num_pages: 10
author: Author Name
num_images: 3
tags: [engineering, deltav, security]
---
```

#### Obsidian special fields

| Field | Type | Use |
|-------|------|-----|
| `title` | string | Title shown in graph view |
| `tags` | YAML list | Tags searchable with `#tag` in Obsidian |
| `aliases` | YAML list | Alternative names for wikilinks |
| `cssclasses` | YAML list | CSS classes for note rendering |
| `publish` | boolean | Controls publication on Obsidian Publish |

#### Correct tag formats

```yaml
# Correct — YAML list
tags:
  - engineering
  - deltav
  - security

# Correct — inline list
tags: [engineering, deltav, security]

# Wrong — single string
tags: engineering deltav security
```

### 2. Naming conventions

| File type | Convention | Example |
|-----------|------------|---------|
| PDF-converted docs | `pdf-slug.md` | `nk-2400-0150.md` |
| Meta/SOP files | `descriptive-name.md` | `d9ee1bba` |
| Image folders | `document-slug/` | `nk-2400-0150/` |

The slug is the original filename in lowercase, with spaces and special characters replaced by hyphens. The `pdf_converter` tool calculates it automatically.

### 3. Image paths

Images MUST use paths relative to the `.md` file location. Documents in `Library/documents/` use:

```markdown
![alt text](../assets/images/<slug>/image.png)
```

The image directory structure is:

```
Library/assets/images/<document-slug>/
```

Example: for `documents/nk-2400-0150.md`, images go in `assets/images/nk-2400-0150/`.

### 4. Supported file formats

| Type | Extensions |
|------|-----------|
| Notes | `md`, `canvas` |
| Images | `png`, `jpg`, `jpeg`, `gif`, `bmp`, `svg` |
| Audio | `mp3`, `wav`, `m4a`, `ogg`, `flac` |
| Video | `mp4`, `webm`, `ogv` |
| Documents | `pdf` |

### 5. Forbidden patterns

- Absolute paths in images — breaks on any other machine
- CWD-relative paths (e.g., `Library/assets/...`) — breaks in Obsidian because the viewer resolves them relative to the file, not the project root
- Singular tag/alias/cssclass fields — deprecated since Obsidian 1.4
- Modifying `.obsidian/` directory — internal configuration

## References

- `cb870dc6` — OLM-SOP-002 Handoff Guide (handoff file format when writing to vault)
- `900191a0` — OLM-SOP-003 Agent Design Methodology (file output standards)
- `Library/assets/images/` — Centralized image storage

## Revision History

| Version | Date | Author | Description of Change |
|---------|------|--------|----------------------|
| v1.0 | 2026-06-05 | Clio | Adopted to OLM-SOP format. Cleaned up broken formatting. Added Purpose, Scope, Responsibilities, Definitions. Restructured into Rules + Procedure. |
