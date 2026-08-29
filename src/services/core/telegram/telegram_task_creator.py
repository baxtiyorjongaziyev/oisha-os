"""
Facade for Telegram Task Creator.
Delegates to modular subpackage in src.services.core.telegram.task_creator.
"""
from src.services.core.telegram.task_creator import (
    TelegramTaskCreator,
    _maybe_await,
)

__all__ = [
    "TelegramTaskCreator",
    "_maybe_await",
]
