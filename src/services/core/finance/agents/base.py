"""Base definitions for FinanceAI agents.

All finance management agents should inherit from :class:`BaseFinanceAgent` and
implement the ``process`` method which receives a generic ``payload`` and
returns a result.  The interface is deliberately minimal to keep the example
self‑contained and testable without external services.
"""

from abc import ABC, abstractmethod
from typing import Any, Dict


class BaseFinanceAgent(ABC):
    """Abstract base class for finance agents.

    Sub‑classes must implement :meth:`process` which performs the agent's
    primary operation.  The method receives a ``payload`` dictionary that can
    contain arbitrary data – in a real system this would be a request body
    describing the operation (e.g., retrieve balance, create transaction).
    """

    @abstractmethod
    def process(self, payload: Dict[str, Any]) -> Any:
        """Execute the agent logic.

        Args:
            payload: Arbitrary input data for the agent.
        Returns:
            Any result produced by the agent.
        """
        raise NotImplementedError
