"""Command registry for self_command_handler."""
from __future__ import annotations

import logging
from typing import Callable, Awaitable, Any

logger = logging.getLogger(__name__)

CommandHandler = Callable[..., Awaitable[None]]
_registry: dict[str, CommandHandler] = {}


def register_command(*prefixes: str):
    """Decorator to register a command handler for given prefixes."""
    def decorator(func: CommandHandler) -> CommandHandler:
        for prefix in prefixes:
            _registry[prefix] = func
        return func
    return decorator


def get_command_handler(cmd: str) -> tuple[CommandHandler | None, str]:
    """Return (handler, matched_prefix) for a command string."""
    for prefix, handler in _registry.items():
        if cmd.startswith(prefix):
            return handler, prefix
    return None, ""


def list_commands() -> list[str]:
    """Return all registered command prefixes."""
    return list(_registry.keys())
