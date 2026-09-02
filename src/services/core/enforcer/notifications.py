"""
Notification delivery, director alerts, and manual force-checks mixin.
"""
from __future__ import annotations

import logging
from typing import Any, Dict, Optional

logger = logging.getLogger("DailyEnforcer")


class NotificationsMixin:
    """Handles dispatching Telegram notifications to team members and directors."""

    async def _send_notification(
        self, user_id: Optional[str], message: str, priority: str = "normal"
    ):
        """Xabar yuborish (Telegram)"""
        if not user_id:
            logger.warning("No telegram_id for user to send daily enforcer message.")
            return

        logger.info(f"Sending daily enforcer msg to user {user_id}")
        if self.bot and hasattr(self.bot, "send_message"):
            try:
                await self.bot.send_message(user_id, message, parse_mode="html")
            except Exception as e:
                logger.error(f"Failed to send enforcer notification to {user_id}: {e}")
                # Fallback
                try:
                    await self.bot.send_message(user_id, message)
                except Exception:
                    logger.warning(
                        "Failed to send enforcer notification (plain text fallback)",
                        user_id=user_id,
                        exc_info=True,
                    )

    async def _send_to_director(self, message: str):
        """Direktorga xabar yuborish"""
        import src.config as config
        owner_id = getattr(config, "OWNER_ID", None)
        logger.info(f"Sending daily enforcer report to director: {owner_id}")
        if owner_id and self.bot and hasattr(self.bot, "send_message"):
            try:
                await self.bot.send_message(owner_id, message, parse_mode="html")
            except Exception as e:
                logger.error(f"Failed to send enforcer report to director {owner_id}: {e}")
                try:
                    await self.bot.send_message(owner_id, message)
                except Exception:
                    logger.warning(
                        "Failed to send enforcer report to director (plain text fallback)",
                        owner_id=owner_id,
                        exc_info=True,
                    )

    async def force_check_now(self) -> Dict[str, Any]:
        """Qo'lda tekshirish (admin uchun)"""
        await self._check_warnings()

        results = {}
        for user_id, member in self.team_members.items():
            results[user_id] = self.workflow.get_user_status(user_id)

        return results
