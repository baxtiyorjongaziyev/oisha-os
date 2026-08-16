from .base import BaseFinanceAgent

class FinGPTAgent(BaseFinanceAgent):
    """Placeholder FinGPT agent implementation."""

    def process(self, payload: dict) -> dict:
        # In a real implementation, this would call the FinGPT model.
        return {"agent": "FinGPT", "payload": payload}
