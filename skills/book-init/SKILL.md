---
name: book-init
description: >
  Adopt the book-sync standard in an existing MkDocs book repository: adds
  book.yml, AGENTS.md and HTML comment markers.  Trigger phrases: "init the
  book", "adopt the book standard", "add book.yml", "set up book-sync",
  "initialize book-sync", "add markers to the index".
when_to_use: >
  Use when the user wants to onboard a new book repository onto the book-sync
  standard.  The book must already exist with an mkdocs.yml and a docs/ folder.
  Do NOT use when the book already has a valid book.yml (use book-sync instead).
---

# Book Init Skill

## Purpose

Adopt the book-sync standard in an existing MkDocs book without overwriting
any hand-written content.

## Pre-requisites

- `book-sync` CLI installed: `cd agent_server && uv pip install -e .`
- The target book has `mkdocs.yml` and `docs/index.md`.

## Workflow

### 1. Dry run first

```sh
book-sync init --dry-run <book-root>
```

Review what would be created or changed.

### 2. Apply

```sh
book-sync init <book-root>
```

This creates (non-destructively):
- `book.yml` — fill in `repo.url`, `repo.branch`, and optional sections.
- `AGENTS.md` — fill in the one-sentence description.
- `.context/` — scratch directory for drafts (add to `.gitignore`).
- Inserts `<!-- book:updates:start/end -->` markers inside the existing
  Updates admonition in `docs/index.md` (or appends a new admonition if none
  exists).

### 3. Edit book.yml

Open `book.yml` and fill in at minimum:

```yaml
repo:
  url: https://github.com/<owner>/<repo>
  branch: main   # or master, code, …
```

Add `paths.news` if the book has a news page.
Add `sections` for meaningful news grouping.

### 4. Validate

```sh
book-sync validate <book-root>
```

Fix any reported errors, then run `book-sync audit` to establish a baseline.

## Rules

- `book-sync init` never overwrites existing files.
- `book.yml` is hand-written and is never rewritten by any tool.
- Add `.context/` to the book's `.gitignore`.
- See `BOOK_STANDARD.md` for the full schema and marker syntax.
