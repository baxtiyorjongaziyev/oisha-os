"""
Helper functions and mixin for state tracking and notification dispatch in background monitor.
"""
from __future__ import annotations

import logging
import os
from datetime import datetime, timezone
from typing import Any, Callable, Dict, Optional, Set

from src.settings import settings

logger = logging.getLogger("BackgroundMonitor")


def _env_enabled(name: str, default: bool = True) -> bool:
    val = os.getenv(name)
    if val is None:
        return default
    return val.strip().lower() in ("1", "true", "yes", "y", "on")


class BaseMonitorHelpersMixin:
    """State tracking, admin notification, and client resolution helpers."""

    def _job_key(self, prefix: str, now: datetime, suffix: str = "") -> str:
        today = now.strftime("%Y-%m-%d")
        return f"{prefix}_{today}" + (f"_{suffix}" if suffix else "")

    def _hour_key(self, prefix: str, now: datetime) -> str:
        return f"{prefix}_{now.hour}_{now.strftime('%Y-%m-%d')}"

    def _already_sent(self, key: str) -> bool:
        return key in self._sent_jobs

    def _mark_sent(self, key: str) -> None:
        self._sent_jobs.add(key)

    async def _notify_admin(self, message: str, parse_mode: Optional[str] = None) -> None:
        admin_id = getattr(self.settings, "OWNER_ID", None) or getattr(
            self.settings, "TELEGRAM_ADMIN_CHAT_ID", None
        )
        if self.bot_client and admin_id:
            try:
                kwargs = {}
                if parse_mode:
                    kwargs["parse_mode"] = parse_mode
                await self.bot_client.send_message(admin_id, message, **kwargs)
                return
            except Exception as exc:
                logger.warning("[NOTIFY BOT WARNING] %s; bot send failed", exc)
        else:
            logger.warning("[NOTIFY ERROR] bot_client not available to notify admin")

    async def _send_to_group_or_admin(self, text: str, **kwargs) -> None:
        target_group = (
            self.TN5_GROUP_ID
            or getattr(self.settings, "CRM_GROUP_ID", None)
            or getattr(self.settings, "TEAM_GROUP_ID", None)
        )
        if target_group:
            if self.bot_client:
                try:
                    send_kwargs = dict(kwargs)
                    if "reply_to" in send_kwargs and "message_thread_id" not in send_kwargs:
                        send_kwargs["message_thread_id"] = send_kwargs.pop("reply_to")
                    await self.bot_client.send_message(target_group, text, **send_kwargs)
                    return
                except Exception as exc:
                    logger.warning("[SEND GROUP BOT WARNING] %s; bot send failed", exc)
            logger.warning("[SEND GROUP ERROR] bot_client not available for group send")
            return
        await self._notify_admin(text, parse_mode=kwargs.get("parse_mode"))

    def _get_amocrm_client(self) -> Any:
        if self.msg_controller and getattr(self.msg_controller, "crm", None):
            client = getattr(self.msg_controller.crm, "amocrm", None)
            if client:
                return client
        if self.get_surgical_integration:
            return self.get_surgical_integration().amocrm
        return None

    def _get_db(self) -> Any:
        if self.msg_controller:
            return getattr(self.msg_controller, "db", None)
        return None
