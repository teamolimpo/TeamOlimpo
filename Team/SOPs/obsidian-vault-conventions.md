---
title: Obsidian Vault Conventions
aliases: [obsidian-vault-conventions, obsidian-vault]
tags: [sops, obsidian, conventions]
---

# Library — Obsidian Vault

`Library/` is an **Obsidian vault**. Every `.md` file written here must follow the conventions in this document to ensure that links, images, and metadata work correctly when the vault is opened in Obsidian.

  The path must be **relative to the `.md` file location**. Documents in `Library/documents/` use `../assets/images/<slug>/` to reference extracted images.

Library/assets/images/<document-slug>/
```

Example: for `documents/nk-2400-0150.md` images are in `assets/images/nk-2400-0150/`.

---

## YAML frontmatter

Every `.md` file in the vault must have a frontmatter block at the top:

```yaml
---
title: Document title
tags: [tag1, tag2]
aliases: [alternative name]
---
```

### Standard fields for PDF-converted documents

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

### Fields with special meaning in Obsidian

| Field | Type | Use |
|-------|------|-----|
| `title` | string | Title shown in graph view |
| `tags` | YAML list | Tags searchable with `#tag` in Obsidian |
| `aliases` | YAML list | Alternative names for wikilinks |
| `cssclasses` | YAML list | CSS classes for note rendering |
| `publish` | boolean | Controls publication on Obsidian Publish |

> **Important**: always use the **plural form** — `tags`, `aliases`, `cssclasses`. Singular forms (`tag`, `alias`, `cssclass`) are deprecated since Obsidian 1.4.

### Correct tag format

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

---

## Naming conventions

| File type | Convention | Example |
|-----------|------------|---------|
| PDF-converted docs | `pdf-slug.md` | `nk-2400-0150.md` |

| Meta/SOP files | `descriptive-name.md` | `obsidian-vault-conventions.md` |
| Image folders | `document-slug/` | `nk-2400-0150/` |

The **slug** is the original filename in lowercase, with spaces and special characters replaced by hyphens. The `pdf_converter` tool calculates it automatically.

---

## Natively supported file formats

| Type | Extensions |
|------|-----------|
| Notes | `md`, `canvas` |
| Images | `png`, `jpg`, `jpeg`, `gif`, `bmp`, `svg` |
| Audio | `mp3`, `wav`, `m4a`, `ogg`, `flac` |
| Video | `mp4`, `webm`, `ogv` |
| Documents | `pdf` |

Files with other extensions (e.g. `.xlsx`, `.db`, `.log`, `.yaml`) are treated as non-indexable attachments: Obsidian sees them but does not open them as notes.

---

## What NOT to do in the vault

- **No absolute paths** in images (e.g. `C:\Users\dev\...`) — breaks on any other machine
- **No CWD-relative paths** (e.g. `Library/assets/...`) — breaks in Obsidian because the viewer resolves them relative to the file location, not the project root

  8. **Images in centralized folder** — `Library/assets/images/<slug>/`.
9. **Dates in ISO 8601** without quotes — `data: 2026-03-25`.
10. **Never touch `.obsidian/`** — it's Obsidian's internal configuration.

---

## Notes per team role

**Cataloger (library management)** — verify that every converted file has valid frontmatter and images with correct relative path before considering the conversion complete.

**Developer (scripts writing `.md` to vault)** — every script must produce: (1) valid frontmatter, (2) images with path relative to the `.md` file, (3) wikilinks for internal vault links. No absolute paths in output.
