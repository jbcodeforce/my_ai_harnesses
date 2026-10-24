"""
Agent to help query an existing database
"""
import argparse
import sys
from pathlib import Path
from typing import  Optional
from agents.config import DEFAULT_LLM_BASE_URL, DEFAULT_LLM_MODEL, DEFAULT_LLM_TEMPERATURE, DEFAULT_LLM_API_KEY
from agno.agent import Agent
from agno.models.openai.like import OpenAILike
from agno.tools.workspace import Workspace
from agno.tools.sql import SQLTools
from agno.db.sqlite import SqliteDb

WRSPC_ROOT = Path(__file__).resolve().parent.parent

def build_agent(db_url) -> Agent:
    """
    Build the db_review agent for the database at `db_url`.

    For a local SQLite file, note that absolute paths need FOUR slashes after
    the scheme (the 3rd is the empty host): "sqlite:////abs/path/to/db.db".
    Use the sync "sqlite" driver, not "sqlite+aiosqlite" (SQLTools uses a
    sync engine).
    """
    model = OpenAILike(
        id=DEFAULT_LLM_MODEL,
        base_url=DEFAULT_LLM_BASE_URL,
        temperature=DEFAULT_LLM_TEMPERATURE,
        api_key=DEFAULT_LLM_API_KEY,
    )
    agent = Agent(
        name="Agent",
        model=model,
        tools=[SQLTools(db_url=db_url)
            ],
        markdown=True,
    )
    return agent


def _assess_db_url(db_url : str) -> str:
    if db_url.startswith("sqlite"):
        return db_url
    dburl = f"sqlite:////Users/jerome/Documents/Code/MyAIAssistant/workspaces/biz-db/data/biz-assistant.db"
    
    
    
def repl(agent):
    """
    Read-Eval-Print Loop
    """
    done = False
    while not done:
        print("Question >:")
        question = input()
        if not question or "bye" in question:
            done = True
        else:
            agent.print_response(question, stream=True)
    print("[dim]Goodbye![/dim]")
    return 0

def parse_args(argv: Optional[list] = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Quality Assurance code agent (agno + oMLX).")
    parser.add_argument("--workspace", "-w", type=Path,
                        default=WRSPC_ROOT,
                        help="Directory the agent may read (default: this project).")
    parser.add_argument("--query", "-q", default=None,
                        help="Run a single question and exit.")
    parser.add_argument("--dburl", "-d", 
                        help="Db url or file name of the sqlite db")
    return parser.parse_args(argv)

def main(argv: Optional[list] = None) -> int:
    args = parse_args(argv)
    workspace = args.workspace.resolve()
    if not workspace.is_dir():
        print(f"[error] Workspace directory does not exist: {workspace}", file=sys.stderr)
        return 2
    if not args.dburl:
        print(f"[error] DB URL is needed", file=sys.stderr)
        return 2
    dburl = _assess_db_url(args.dburl)
    
    # sqlite+aiosqlite is an async driver and would fail with SQLTools' sync
    # engine; 4 slashes (not 3) are required for an absolute file path.
    agent = build_agent(dburl)
    repl(agent)


if __name__ == "__main__":
    raise SystemExit(main())
   
