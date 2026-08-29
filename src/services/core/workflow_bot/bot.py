"""
WorkflowTelegramBot main class composing user and admin command mixins.
"""
from __future__ import annotations

import logging
from typing import Any, Dict, List, Optional
from datetime import datetime

from src.services.core.workflow_bot.user_commands import UserCommandsMixin
from src.services.core.workflow_bot.admin_commands import AdminCommandsMixin

logger = logging.getLogger("WorkflowTelegramBot")


class WorkflowTelegramBot(UserCommandsMixin, AdminCommandsMixin):
    """
    Workflow boshqaruvi uchun Telegram bot interfeysi.
    """

    ADMIN_USERS: List[int] = [
        # Admin user IDs
    ]

    def __init__(self):
        self.workflow = get_mandatory_workflow()
        self.enforcer = get_daily_enforcer()
        self.admins = []  # Admin telegram IDs

    async def handle_command(
        self, user_id: str, command: str, args: list, is_admin: bool = False
    ) -> str:
        """Komandani qayta ishlash"""

        # User commands
        if command == "start":
            return await self._cmd_start(user_id, args)

        elif command == "my_tasks":
            return await self._cmd_my_tasks(user_id)

        elif command == "start_task":
            return await self._cmd_start_task(user_id, args)

        elif command == "complete_task":
            return await self._cmd_complete_task(user_id, args)

        elif command == "status":
            return await self._cmd_status(user_id)

        elif command == "report":
            return await self._cmd_report(user_id)

        elif command == "help":
            return await self._cmd_help(is_admin)

        # Admin commands
        elif is_admin:
            if command == "admin_panel":
                return await self._cmd_admin_panel()

            elif command == "team_status":
                return await self._cmd_team_status()

            elif command == "block_user":
                return await self._cmd_block_user(args)

            elif command == "unblock_user":
                return await self._cmd_unblock_user(args)

            elif command == "broadcast":
                return await self._cmd_broadcast(args)

            elif command == "force_morning":
                await self.enforcer._morning_routine()
                return "✅ Ertalabki rejim qo'lda ishga tushirildi"

            elif command == "force_evening":
                await self.enforcer._evening_routine()
                return "✅ Kechki rejim qo'lda ishga tushirildi"

        return "❌ Unknown command. Use /help"


_workflow_bot: Optional[WorkflowTelegramBot] = None


def get_workflow_bot() -> WorkflowTelegramBot:
    """Singleton WorkflowTelegramBot olish."""
    global _workflow_bot
    if _workflow_bot is None:
        _workflow_bot = WorkflowTelegramBot()
    return _workflow_bot

