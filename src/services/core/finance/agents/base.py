"""Contracts for deterministic, auditable finance analysis agents."""
from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any, Mapping


class BaseFinanceAgent(ABC):
    @abstractmethod
    def process(self, payload: Mapping[str, Any]) -> dict[str, Any]:
        """Analyze validated finance input without mutating financial data."""
