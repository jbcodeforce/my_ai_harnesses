from agno.os import AgentOS

from agents.registry import build_agents

agent_os = AgentOS(
    id="My AI AgentOS",
    agents=build_agents(),
    tracing=True,
)
app = agent_os.get_app()

# ---------------------------------------------------------------------------
# Run AgentOS
# ---------------------------------------------------------------------------
if __name__ == "__main__":
    agent_os.serve(app="main:app", host="127.0.0.1", reload=True)
