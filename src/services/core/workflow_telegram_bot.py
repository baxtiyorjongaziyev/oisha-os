"""
Facade for Workflow Telegram Bot.
Delegates to modular subpackage in src.services.core.workflow_bot.
"""
from src.services.core.workflow_bot import (
    WorkflowTelegramBot,
    get_workflow_bot,
)

__all__ = [
    "WorkflowTelegramBot",
    "get_workflow_bot",
]
