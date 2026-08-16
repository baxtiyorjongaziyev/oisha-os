'''FinanceAI Agent Registry.

This module provides a simple registry for finance management agents.
Agents inherit from :class:`BaseFinanceAgent` defined in ``base.py`` and
implement a ``process`` method.

The registry allows dynamic lookup and instantiation by name.
'''  

from .base import BaseFinanceAgent
from .fin_gpt import FinGPTAgent

# Registry mapping agent identifiers to their implementing classes.
_AGENT_REGISTRY: dict[str, type[BaseFinanceAgent]] = {
    "fin_gpt": FinGPTAgent,
    # Future agents can be added here, e.g., "pla_id_ai": PlaidAIAgent,
}


def get_agent(name: str) -> BaseFinanceAgent:
    """Return an instance of the requested finance agent.

    Args:
        name: The registry key for the desired agent.
    Raises:
        KeyError: If the agent name is not registered.
    """
    cls = _AGENT_REGISTRY[name]
    return cls()

__all__ = ["BaseFinanceAgent", "FinGPTAgent", "get_agent", "_AGENT_REGISTRY"]
