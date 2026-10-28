# My AI Agents

A set of locally-hosted Agno agents for focused work on local workspaces and file systems. The server is an AgentOS instance served on `127.0.0.1:7777`.

## Pre-requisites

* [`uv`](https://github.com/astral-sh/uv)
* A running OpenAI-compatible LLM endpoint locally (e.g. `start_omlx.sh`)
* An `.env` file with the variables below, referenced via `ML_ENV_FILE`:

```sh
# point to your env file before starting
export ML_ENV_FILE=$PWD/.env
```

`.env` variables (all optional except `LLM_BASE_URL` / `LLM_MODEL`):

```sh
LLM_BASE_URL=http://127.0.0.1:7999/v1
LLM_MODEL=Qwen3.8-27B-4bit
LLM_TEMPERATURE=0.4
LLM_API_KEY=local-key

# Optional — enables the embedding knowledge-base features
EMBEDDER_MODEL=bge-small-en-v1.5-8bit
EMBEDDER_BASE_URL=http://127.0.0.1:7999/v1

# Required to load the DB Review agent
# SQLAlchemy URL, e.g. sqlite:////abs/path/to/file.db
DB_REVIEW_URL=
```

## Agents

| Agent | Required env var | Description |
|-------|-----------------|-------------|
| `DB Review` | `DB_REVIEW_URL` | Chat with any SQL database. Pass a SQLAlchemy URL. |
| `Book sync` | | |

Agents whose required env var is unset are skipped at startup with a warning. The server refuses to start if **no** agents are configured.

## One Agno OS Server

```sh
cd agent_server
uv run uvicorn main:app --host 127.0.0.1 --port 7777
```

Or with auto-reload during development:

```sh
cd agent_server
uv run python main.py
```

The server binds to `127.0.0.1:7777` only (not `0.0.0.0`).  
Connect via [os.agno.com](https://os.agno.com): add a new local connection pointing to `http://127.0.0.1:7777`.

## Book Sync

```sh
cd agent_server
uv run book-sync init --help
uv run book-sync init ~/Documents/Code/flink-studies
# validate book.yml
uv run book-sync validate ~/Documents/Code/flink-studies
# Audit GitHub URLs, mkdocs nav, and version strings.
uv run book-sync audit ~/Documents/Code/flink-studies
# Version some version  referenced in files
uv run book-sync versions ~/Documents/Code/flink-studies
# Build a draft of news update
uv run book-sync news ~/Documents/Code/flink-studies
# will create a .context/news-draft.md , to review

# Apply the change once draft is modified to the news

# compute stats on the repo
uv run book-sync stats ~/Documents/Code/flink-studies
```

## DB Review agent (CLI)

```sh
cd agent_server
uv run db-review-agent --dburl sqlite:////path/to/file.db
# or pass a plain path and let the tool resolve it:
uv run db-review-agent --dburl /path/to/file.db
# single question mode:
uv run db-review-agent --dburl /path/to/file.db --query "How many rows in orders?"
```
