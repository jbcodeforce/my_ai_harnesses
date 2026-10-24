from agno.os import AgentOS
from agents.db_review import build_agent

agent = build_agent()
agent_os = AgentOS(
    id="Quick Start AgentOS",
    agents=[
        agent,
    ],
    tracing=True
)
app = agent_os.get_app()

# ---------------------------------------------------------------------------
# Run AgentOS
# ---------------------------------------------------------------------------
if __name__ == "__main__":
    agent_os.serve(app="agent_server.main:app", reload=True)

