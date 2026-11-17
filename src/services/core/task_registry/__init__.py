"""Shared task registry for Oisha, Amina and Mr.Jon."""
from src.services.core.task_registry.store import (
    KNOWN_BOTS,
    STATUSES,
    TaskRegistry,
    TaskRegistryError,
)

__all__ = ["KNOWN_BOTS", "STATUSES", "TaskRegistry", "TaskRegistryError", "get_registry"]

_registry = None


def get_registry() -> TaskRegistry:
    """Process-wide registry backed by the Turso pool."""
    global _registry
    if _registry is None:
        from src.database_pool import DatabasePool

        _registry = TaskRegistry(DatabasePool().execute)
    return _registry
