---
name: book-sync
description: >
  Audit, update news, and refresh stats for any MkDocs book that carries a
  book.yml contract. Trigger phrases: "audit the book", "update the news",
  "refresh stats", "run book-sync", "check versions", "sync the docs",
  "apply news draft", "validate book.yml".
when_to_use: >
  Use when the user wants to audit link health, update the News page, refresh
  stat counters, or validate the book.yml contract for any book repository
  (flink-studies, eda-studies, ML-studies, db-play, python-code, etc.).
  The book must have a book.yml file (run book-init first if it does not).
  Do NOT use for writing chapter content, creating new tutorials, or tasks
  unrelated to the book-sync tooling.
---

# Book Sync Skill

## Purpose

Keep a book's "Updates" section, news page, and stat counters accurate.
All writes go through a human review step — no file is changed without your
explicit approval.

## Pre-requisites

- `book-sync` CLI installed: `cd agent_server && uv pip install -e .`
- The target book has a `book.yml` (run `book-sync init <path>` if missing).
- `book-sync validate <path>` passes before any other command.

## Workflow

### 1. Validate

```sh
book-sync validate <book-root>
```

Fix any reported errors before continuing.

### 2. Audit (links and versions)

```sh
book-sync audit <book-root>
# add --fix to rewrite broken GitHub branch links and stale version strings
book-sync audit --fix <book-root>
```

Review the output.  Errors must be resolved before applying news.

### 3. Collect news draft

```sh
book-sync news <book-root>
# or specify a start commit explicitly
book-sync news --since <commit-sha> <book-root>
```

The draft is written to `<book-root>/.context/news-draft.md`.
**Review the draft** — edit bullets, remove noise, improve wording.
News is curated: every item must be traceable to a commit.

### 4. Apply approved draft

Only after you have reviewed and edited the draft:

```sh
book-sync apply <book-root>
```

This rewrites the `<!-- book:news-site:start/end -->` region, prepends a line
to `<!-- book:news-log:start/end -->`, and updates the `book:sync` marker.

### 5. Stats

```sh
book-sync stats <book-root>
# add --write to update the stats region in index.md
book-sync stats --write <book-root>
```

## Rules

- **Never invent news items.** Every bullet must come from a real commit.
- **Show a diff** (or the draft content) before applying any write.
- **Do not commit or push** — that is the user's responsibility.
- Markers owned by the tool: `<!-- book:updates:start/end -->`,
  `<!-- book:stats:start/end -->`, `<!-- book:news-site:start/end -->`,
  `<!-- book:news-log:start/end -->`.  Never edit text outside them.
- If a marker is missing, run `book-sync init <path>` to add it.
