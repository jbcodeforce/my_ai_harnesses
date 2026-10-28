"""
Agent to help query an existing database.
"""
import argparse
import sys
from pathlib import Path
from typing import Optional

from agents.config import (
    DEFAULT_LLM_API_KEY,
    DEFAULT_LLM_BASE_URL,
    DEFAULT_LLM_MODEL,
    DEFAULT_LLM_TEMPERATURE,
    DB_REVIEW_URL,
    NotConfigured,
)
from agno.agent import Agent
from agno.models.openai.like import OpenAILike
from agno.tools.sql import SQLTools

WRSPC_ROOT = Path(__file__).resolve().parent.parent


def _assess_db_url(db_url: str) -> str:
    """Normalise *db_url* to a SQLAlchemy URL string.

    - If it already contains ``://`` it is returned unchanged.
    - Otherwise it is treated as a file-system path to a SQLite database.
      The path is resolved to an absolute path; a ``ValueError`` is raised if
      the file does not exist.
    """
    if "://" in db_url:
        return db_url
    path = Path(db_url).resolve()
    if not path.exists():
        raise ValueError(f"SQLite file not found: {path}")
    # Four slashes: sqlite:// (scheme) + // (empty host) + /abs/path
    return f"sqlite:///{path}"


def build_agent(db_url: str) -> Agent:
    """Build the db_review agent for the database at *db_url*.

    For a local SQLite file either pass the path directly or a
    ``sqlite:////abs/path/to/db.db`` URL (four slashes: the third slash is the
    empty host component).  The sync ``sqlite`` driver is required because
    SQLTools uses a synchronous engine.
    """
    model = OpenAILike(
        id=DEFAULT_LLM_MODEL,
        base_url=DEFAULT_LLM_BASE_URL,
        temperature=DEFAULT_LLM_TEMPERATURE,
        api_key=DEFAULT_LLM_API_KEY,
    )
    return Agent(
        name="DB Review",
        model=model,
        tools=[SQLTools(db_url=db_url)],
        markdown=True,
    )


def build_server_agent() -> Agent:
    """Build the db_review agent from the ``DB_REVIEW_URL`` env var.

    Raises :class:`~agents.config.NotConfigured` when the variable is not set,
    so the registry can skip this agent gracefully.
    """
    if not DB_REVIEW_URL:
        raise NotConfigured(
            "DB_REVIEW_URL is not set — db_review agent will not be loaded. "
            "Set it to a SQLAlchemy URL (e.g. sqlite:////abs/path/to/file.db)."
        )
    return build_agent(_assess_db_url(DB_REVIEW_URL))


# ---------------------------------------------------------------------------
# CLI entry point
# ---------------------------------------------------------------------------

def repl(agent: Agent) -> None:
    """Read-Eval-Print Loop."""
    while True:
        print("Question >:")
        question = input()
        if not question or "bye" in question:
            break
        agent.print_response(question, stream=True)
    print("[dim]Goodbye![/dim]")


def parse_args(argv: Optional[list] = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="DB review agent (agno + OpenAI-compatible LLM).")
    parser.add_argument(
        "--workspace", "-w",
        type=Path,
        default=WRSPC_ROOT,
        help="Directory the agent may read (default: this project).",
    )
    parser.add_argument("--query", "-q", default=None, help="Run a single question and exit.")
    parser.add_argument("--dburl", "-d", help="DB URL or path to a SQLite file.")
    return parser.parse_args(argv)


def main(argv: Optional[list] = None) -> int:
    args = parse_args(argv)
    workspace = args.workspace.resolve()
    if not workspace.is_dir():
        print(f"[error] Workspace directory does not exist: {workspace}", file=sys.stderr)
        return 2

    db_url_raw = args.dburl or DB_REVIEW_URL
    if not db_url_raw:
        print("[error] Provide --dburl or set DB_REVIEW_URL.", file=sys.stderr)
        return 2

    try:
        db_url = _assess_db_url(db_url_raw)
    except ValueError as exc:
        print(f"[error] {exc}", file=sys.stderr)
        return 2

    agent = build_agent(db_url)
    if args.query:
        agent.print_response(args.query, stream=True)
    else:
        repl(agent)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
