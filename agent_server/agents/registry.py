"""
Agent registry.

Add every agent to AGENT_BUILDERS.  Each entry is a zero-argument callable
that returns an :class:`agno.agent.Agent`.  Callables may raise
:class:`~agents.config.NotConfigured` to opt out gracefully when a required
environment variable is absent.

``build_agents()`` is the single entry point used by ``main.py``.  It:
- calls every builder,
- logs a warning and skips agents that raise ``NotConfigured``, and
- raises ``RuntimeError`` if no agents can be loaded (AgentOS requires at
  least one).
"""
import logging
import warnings
from collections.abc import Callable
from typing import TypeAlias

from agno.agent import Agent

from agents.book_sync import build_agent as build_book_sync
from agents.config import NotConfigured
from agents.db_review import build_server_agent as build_db_review

log = logging.getLogger(__name__)

AgentFactory: TypeAlias = Callable[[], Agent]

AGENT_BUILDERS: list[AgentFactory] = [
    build_db_review,
    build_book_sync,
]


def build_agents() -> list[Agent]:
    """Return all configured agents.

    Raises ``RuntimeError`` when no agent can be loaded so the server fails
    fast with a clear message instead of a confusing AgentOS error.
    """
    agents: list[Agent] = []
    for factory in AGENT_BUILDERS:
        try:
            agents.append(factory())
        except NotConfigured as exc:
            warnings.warn(str(exc), stacklevel=2)
    if not agents:
        raise RuntimeError(
            "No agents could be loaded.  Set at least one agent's required "
            "environment variable (e.g. DB_REVIEW_URL) and try again."
        )
    return agents
