"""Allow-listed finance analysis registry."""
from __future__ import annotations

from .base import BaseFinanceAgent
from .cashflow import CashflowAnalysisAgent

_AGENT_REGISTRY: dict[str, type[BaseFinanceAgent]] = {
    "cashflow": CashflowAnalysisAgent,
}


def get_agent(name: str) -> type[BaseFinanceAgent]:
    try:
        return _AGENT_REGISTRY[name]
    except KeyError:
        raise KeyError(f"Unknown finance agent: {name}") from None


def create_agent(name: str) -> BaseFinanceAgent:
    return get_agent(name)()


__all__ = ["BaseFinanceAgent", "CashflowAnalysisAgent", "create_agent"]
