# Book standard

A "book" is a git repository that publishes an MkDocs site (flink-studies, eda-studies, ML-studies, spark-studies, db-play, python-code, jbcodeforce.github.io, ...). This standard gives every book the same machine-readable contract, so one tool (`book-sync`), one chat agent and a few skills can keep it accurate without hardcoding any book's paths.

Nothing in this standard replaces existing content. A book adopts it by adding one file (`book.yml`), a short `AGENTS.md`, and HTML comment markers around the parts a tool may rewrite.

## 1. Layout

```
<book>/
  AGENTS.md            agent entry: purpose, layout, rules, pointer to book.yml
  book.yml             the contract read by every tool (hand-written, never rewritten by tools)
  mkdocs.yml
  TASKS.md             optional backlog
  docs/
    index.md           contains the `updates` region (and optionally `stats`)
    news/index.md      optional; contains `news-site`, `news-log` and the sync marker
    <chapters>/        concepts, architecture, coding, cookbook, techno, methodology, labs
    images/
  code/                tutorials and small samples
  e2e-demos/           optional, larger demonstrations
  deployment/          optional
  .context/            gitignored scratch and agent handoff (drafts are written here)
  <harness>/skills/    installed skill links (.bob, .claude, .pi, ...)
```

Only `book.yml`, `AGENTS.md`, `mkdocs.yml` and `docs/index.md` are required. Every other folder is optional and is only used if `book.yml` mentions it.

## 2. `book.yml`

Plain YAML, loaded with `yaml.safe_load`. Tools never write to it, so comments and ordering are preserved. State that changes (the last synced commit) lives in a marker in the docs, see section 4.

| Key | Required | Meaning |
|-----|----------|---------|
| `schema` | yes | Integer, currently `1`. |
| `name` | yes | Short book name. |
| `repo.url` | yes | GitHub URL without `.git`. Used to recognise `blob/` and `tree/` links in docs. |
| `repo.branch` | yes | Branch used in those links (`master`, `main`, ...). |
| `site_url` | no | Published site URL. |
| `paths.docs` | no | Docs folder. Default `docs`. |
| `paths.mkdocs` | no | Default `mkdocs.yml`. |
| `paths.index` | no | Default `docs/index.md`. |
| `paths.news` | no | News page. If absent, news features are skipped and the sync marker lives in the index file. |
| `paths.changelog` | no | Generated changelog page. If absent, `changelog` is not available. |
| `paths.scratch` | no | Draft folder. Default `.context`. |
| `sections` | for `news` | Ordered list of `{title, paths}`. A changed file goes to the first section whose path prefix matches. Files that match none go to `Other`. |
| `ignore_commits` | no | Regular expressions on the commit subject. Matching commits are left out of drafts. |
| `stats` | no | List of counters, see below. |
| `versions` | no | List of version checks, see below. |
| `fix_rules` | no | List of `{match, replace}` regexes that rewrite a broken repo path to a new one, applied only if the target exists. |

`stats` entry:

```yaml
- id: sql_scripts            # unique, used in the stats region
  label: SQL scripts         # text shown in the region
  count: files               # files | dirs
  include: ["code/**/*.sql", "e2e-demos/**/*.sql"]
  exclude: ["**/.venv/**", "**/node_modules/**"]
```

`versions` entry (replaces the hardcoded Confluent Platform check):

```yaml
- id: cp-kafka
  source:                    # where the canonical value is declared
    file: deployment/docker/docker-compose.yaml
    pattern: 'confluentinc/cp-kafka:(\d+\.\d+\.\d+)'   # group 1 is the version
  docs_pattern: 'confluentinc/cp-(?:kafka|schema-registry|control-center|kafka-rest|connect|ksqldb)[^:]*:(\d+\.\d+\.\d+)'
  fix: true                  # allow audit --fix to rewrite docs to the canonical value
```

Rules:
- All paths are relative to the book root. Absolute paths and `..` are rejected by `validate`.
- Regexes use Python `re` syntax. Quote them in single quotes in YAML.
- A key a tool does not need is ignored, so a minimal book can start with `schema`, `name` and `repo`.

## 3. Marked regions

A tool may only rewrite text between a start and an end marker. Everything outside is hand-written and is never touched.

```
<!-- book:updates:start -->
...
<!-- book:updates:end -->
```

| Region | File | Content |
|--------|------|---------|
| `updates` | index file | One line per release or milestone, newest last. Inside the book's "Updates" admonition. |
| `stats` | index file | Measured counters from `stats`. |
| `news-site` | news file | "Updates to this web site", grouped by section title. |
| `news-log` | news file | One line per sync, newest last. |

Rules:
- Markers are exact lowercase strings. A region has exactly one start and one end, in that order.
- The tool keeps the indentation of the start-marker line on every line it writes, so a region can sit inside an indented MkDocs admonition (`???- info "Updates"`).
- If a needed marker is missing, the tool stops with a message. `book-sync init` adds markers without changing the text around them.
- Content between markers is replaced as a whole after the user approves a draft. Edits made by hand between markers are lost on the next apply, so hand-written lines belong outside the markers.

## 4. Sync marker

The last synced position is stored where the content is, not in `book.yml`:

```
<!-- book:sync commit=1d6e082 date=2026-08 -->
```

- Lives in the news file if `paths.news` is set, otherwise in the index file.
- `commit` is the abbreviated hash of the newest commit covered. `date` uses the date format below.
- `book-sync news` lists commits after `commit`. `--since` overrides it. The apply step rewrites this one line.
- If the marker is missing, `news` asks for `--since` instead of guessing.

## 5. Date format

All dates in update logs use `YYYY-MM` (for example `2026-08`). `YYYY-MM-DD` is allowed when a day matters. Existing lines in other formats (`07/2026`, `06/11/2026`, `[06/26]`) are left as they are. Tools only write the new format.

## 6. Front matter

Pages may carry the front matter already used in flink-studies:

```yaml
---
title: ...
source: <book>/docs/<path>.md
ingested:
tags: []
type: article
compiled: false
---
```

It is optional and `book-sync` does not require it or change it. No second manifest is introduced. ML-studies keeps its own `docs/.manifest.json`; the standard does not touch it.

## 7. `AGENTS.md` template

Keep it short; details belong in `book.yml`.

```markdown
# <Book name>

<One sentence: what this book teaches and for whom.>

## Layout
- `docs/` MkDocs content (chapters listed in `mkdocs.yml`)
- `code/` samples, `e2e-demos/` larger demos (only if present)
- `.context/` gitignored scratch for agent drafts

## Contract
Machine-readable settings live in `book.yml`. Run `book-sync validate` after changing structure.

## Rules for agents
- Edit only between `<!-- book:... -->` markers when a tool owns the text.
- News is curated: summarize and group, never invent items, drop anything not traceable to a commit.
- Show a diff and wait for approval before committing.
- Python: use `uv`.
```

## 8. Compatibility notes (checked on existing books)

Seven books were looked at: flink-studies, eda-studies, ML-studies, spark-studies, jbcodeforce.github.io, db-play, python-code.

- `mkdocs.yml` in four of the five books tested with `yaml.safe_load` (flink-studies, eda-studies, ML-studies, jbcodeforce.github.io) uses `!!python/name:` tags that it rejects; spark-studies parses. db-play and python-code were not tested with `safe_load`. Tools must read `mkdocs.yml` with a loader that maps those tags to plain strings. `book.yml` itself never uses tags.
- With such a loader, nav `.md` entries resolve in flink-studies (44), eda-studies (38), spark-studies (8) and db-play (12). Three nav entries do not: ML-studies lists a GitHub URL as a page, jbcodeforce.github.io lists `leadership/release_it.md`, python-code lists `coding/building-cli.md`. The nav check must skip anything starting with `http`; the other two are real findings for the audit.
- Only flink-studies, eda-studies and ML-studies set `site_url` in `mkdocs.yml`, plus jbcodeforce.github.io. spark-studies, db-play and python-code do not. It is optional in `book.yml`.
- Default branches differ: `master` in flink-studies, spark-studies, db-play and python-code; `main` in eda-studies and ML-studies; the branch in jbcodeforce.github.io is `code`. Hence `repo.branch` is required.
- jbcodeforce.github.io sets `docs_dir: docs` explicitly. Other books rely on the default.
- Update blocks differ: flink-studies uses `???- info "Site updates"`, db-play uses `!!!- "info"`, ML-studies uses `!!! info "Update"`, and python-code has none. `init` inserts the `updates` region inside an existing block if it finds one, otherwise it adds a new admonition and asks first.
