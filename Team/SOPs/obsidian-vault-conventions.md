---
title: Obsidian Vault Conventions
aliases: [obsidian-vault-conventions, obsidian-vault]
tags: [sops, obsidian, conventions]
---

# Library — Obsidian Vault

`lib/` is an **Obsidian vault**. Every `.md` file written here must follow the conventions in this document to ensure that links, images, and metadata work correctly when the vault is opened in Obsidian.

This document is the operational reference for all team members that produce output in the Library.

---

## Vault structure

```
lib/
├── .obsidian/          # Obsidian configuration (do not edit manually)
├── assets/
│   └── images/         # Images extracted from PDFs, organized by slug
│       └── <slug>/     # One folder per document
├── data/               # SQLite databases and logs (NOT Markdown — ignored by Obsidian)
│   └── kba_catalog/    # KBA records
├── documents/          # Markdown files converted from PDFs
├── Meta/               # Tool guides, templates, and system docs
└── SOPs/               # Operational procedures referenced by agents
```

> **Note**: the `data/` folder contains non-Markdown files (SQLite, YAML, logs). Obsidian sees it but does not index it as notes. Do not create `.md` files in `data/` unless explicitly required.

---

## Internal link rules

Obsidian uses **wikilinks** as its native format. Always use this syntax for internal vault links:

```
[[filename]]                  → link to a note
[[filename|text]]             → link with alternative text
[[filename#Section]]          → link to a specific section
[[filename#Section|text]]     → link to section with text
[[filename#^block-id]]        → link to a specific block
[[#Section]]                  → link to heading in the current note
```

**Block IDs** are added at the end of a paragraph with the syntax ` ^name-id` (one space before `^`). May contain only Latin letters, numbers, and hyphens.

**Link resolution**: Obsidian searches the entire vault using the shortest unique path. If only one `report.md` exists, `[[report]]` finds it anywhere. If duplicates exist, specify the minimum path needed to disambiguate (e.g. `[[folder/report]]`).

**Avoid** standard Markdown for internal links:
```
❌ [text](../documents/report.md)   → works but not native Obsidian
✓  [[report|text]]                  → correct form
```

Standard Markdown links `[text](url)` should be used **only for external URLs**.

---

## Image rules

Images in the vault follow a precise convention. Two valid syntaxes:

### Wikilink syntax (preferred for vault images)

```
![[image.png]]           → embed image
![[image.png|300]]       → fixed width 300px (proportional height)
![[image.png|300x200]]   → width x height in pixels
![[doc.pdf]]             → embed entire PDF
![[doc.pdf#page=3]]      → embed specific PDF page
![[other-note]]          → embed content of another note
![[other-note#Section]]  → embed a specific section
```

Obsidian searches the entire vault for the image file. Works if the filename is unique in the vault. If duplicates exist, specify the path: `![[assets/images/slug/img.png]]`.

### Standard Markdown syntax (required for explicit paths)

```
![alt text](../assets/images/<slug>/image.png)
```

The path must be **relative to the `.md` file location**. Documents in `lib/documents/` use `../assets/images/<slug>/` to reference extracted images.

> **Operational rule**: the `pdf_converter` tool automatically produces the correct relative path. If writing a `.md` file manually with images, use the relative path `../assets/images/<slug>/name.png` — never absolute paths, never paths relative to the project root.

### Image folder per document

Each document has its own dedicated image folder:
```
lib/assets/images/<document-slug>/
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
tags: [kba, deltav, security]
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
  - kba
  - deltav
  - security

# Correct — inline list
tags: [kba, deltav, security]

# Wrong — single string
tags: kba deltav security
```

---

## Naming conventions

| File type | Convention | Example |
|-----------|------------|---------|
| PDF-converted docs | `pdf-slug.md` | `nk-2400-0150.md` |
| KBA records | `kba-slug.md` | `nk-2400-0150.md` |
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
- **No CWD-relative paths** (e.g. `lib/assets/...`) — breaks in Obsidian because the viewer resolves them relative to the file location, not the project root
- **No non-Markdown files in `documents/`** — that folder is reserved for converted `.md` files
- **Do not edit `.obsidian/` manually** — use Obsidian to change settings

---

## Quick reference — 10 rules

1. **Frontmatter always at top** — `---` delimiters on line 1. No blank line before, no BOM.
2. **Plural form** for special fields — `tags`, `aliases`, `cssclasses` (not singular forms).
3. **Wikilinks for internal links** — `[[note]]`, `[[note|alias]]`, `[[note#section]]`.
4. **Wikilinks for embeds** — `![[img.png]]`, `![[img.png|300]]`, `![[note#section]]`.
5. **Markdown links only for external URLs** — `[text](https://...)`.
6. **Minimum paths** in links — filename only if unique in vault.
7. **Unique filenames** — avoid duplicates across folders; use hyphens instead of spaces.
8. **Images in centralized folder** — `lib/assets/images/<slug>/`.
9. **Dates in ISO 8601** without quotes — `data: 2026-03-25`.
10. **Never touch `.obsidian/`** — it's Obsidian's internal configuration.

---

## Notes per team role

**Cataloger (library management)** — verify that every converted file has valid frontmatter and images with correct relative path before considering the conversion complete.

**KBA analyst** — KBA records go in `lib/data/kba_catalog/records/`. Frontmatter must include at least `title` and `tags`. Links to source documents use wikilink syntax `[[document-slug]]`.

**Developer (scripts writing `.md` to vault)** — every script must produce: (1) valid frontmatter, (2) images with path relative to the `.md` file, (3) wikilinks for internal vault links. No absolute paths in output.
