"""
AI Agent Tools — Gemini Function Calling uchun barcha toollar.
Facade delegating to src.agents.agent_tools.
"""

from src.agents.agent_tools.declarations import TOOL_DECLARATIONS
from src.agents.agent_tools.executor import AgentToolExecutor

__all__ = ["TOOL_DECLARATIONS", "AgentToolExecutor"]
