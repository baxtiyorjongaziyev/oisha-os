from __future__ import annotations

import asyncio
import logging
from typing import Any, Dict, List, Optional

from telegram import Bot

from src.services.core.airtable_sync import AirtableSync
from src.services.core.amocrm_sync import AmoCRMSync
from src.services.core.tool_registry import ToolRegistry, ToolResult


logger = logging.getLogger(__name__)


class TelegramNotificationAdapter:
    tool_name = "telegram"

    def __init__(self, bot_token: str, default_parse_mode: str = "HTML"):
        self.bot = Bot(token=bot_token)
        self.default_parse_mode = default_parse_mode

    async def send_group_message(
        self,
        chat_id: int,
        text: str,
        *,
        thread_id: Optional[int] = None,
        parse_mode: Optional[str] = None,
        disable_web_page_preview: bool = False,
    ) -> ToolResult:
        try:
            message = await self.bot.send_message(
                chat_id=chat_id,
                text=text,
                parse_mode=parse_mode or self.default_parse_mode,
                message_thread_id=thread_id,
                disable_web_page_preview=disable_web_page_preview,
            )
            return ToolResult(
                tool_name="telegram.group_message",
                success=True,
                sent_count=1,
                group_message_id=message.message_id,
                metadata={"chat_id": chat_id, "thread_id": thread_id},
            )
        except Exception as exc:
            logger.warning("[TELEGRAM TOOL] Group send failed: %s", exc)
            return ToolResult(
                tool_name="telegram.group_message",
                success=False,
                status="failed",
                reason=str(exc),
                failed_targets=[{"chat_id": chat_id, "error": str(exc)}],
                metadata={"chat_id": chat_id, "thread_id": thread_id},
            )

    async def send_direct_messages(
        self,
        messages: List[Dict[str, Any]],
        *,
        parse_mode: Optional[str] = None,
        disable_web_page_preview: bool = False,
    ) -> ToolResult:
        delivered_to: List[int] = []
        failed_targets: List[Dict[str, Any]] = []
        direct_message_ids: List[int] = []
        attempted = 0

        for item in messages:
            user_id = int(item.get("user_id") or 0)
            text = str(item.get("text") or "").strip()
            if not user_id or not text:
                continue

            attempted += 1
            try:
                message = await self.bot.send_message(
                    chat_id=user_id,
                    text=text,
                    parse_mode=item.get("parse_mode") or parse_mode or self.default_parse_mode,
                    disable_web_page_preview=disable_web_page_preview,
                )
                delivered_to.append(user_id)
                direct_message_ids.append(message.message_id)
            except Exception as exc:
                logger.warning("[TELEGRAM TOOL] DM send failed for %s: %s", user_id, exc)
                failed_targets.append({"user_id": user_id, "error": str(exc)})

        success = attempted == 0 or bool(delivered_to)
        status = "ok"
        if failed_targets and delivered_to:
            status = "partial"
        elif failed_targets and not delivered_to:
            status = "failed"

        return ToolResult(
            tool_name="telegram.direct_messages",
            success=success,
            status=status,
            sent_count=len(delivered_to),
            direct_message_ids=direct_message_ids,
            delivered_to=delivered_to,
            failed_targets=failed_targets,
            reason=None if success else "all_direct_messages_failed",
            metadata={"attempted": attempted},
        )


class AmoCRMLeadAdapter:
    tool_name = "amocrm_leads"

    def __init__(self, amocrm: AmoCRMSync):
        self.amocrm = amocrm

    async def fetch_leads(self, limit: int = 50) -> List[Dict[str, Any]]:
        return await self.amocrm.get_leads_detailed(limit=limit)

    async def fetch_stagnated_leads(self, hours: int = 24) -> List[Dict[str, Any]]:
        return await asyncio.to_thread(self.amocrm.check_stagnated_leads, hours)

    async def get_user_name(self, user_id: int) -> str:
        return await asyncio.to_thread(self.amocrm.get_user_name, user_id)


class AirtableProjectAdapter:
    tool_name = "airtable_projects"

    def __init__(self, airtable: AirtableSync):
        self.airtable = airtable

    async def fetch_projects(self) -> List[Dict[str, Any]]:
        return await asyncio.to_thread(self.airtable.get_projects)


def build_default_tool_registry(
    *,
    bot_token: Optional[str] = None,
    amocrm: Optional[AmoCRMSync] = None,
    airtable: Optional[AirtableSync] = None,
) -> ToolRegistry:
    registry = ToolRegistry()
    if bot_token:
        registry.register("telegram", TelegramNotificationAdapter(bot_token))
    if amocrm is not None:
        registry.register("amocrm_leads", AmoCRMLeadAdapter(amocrm))
    if airtable is not None:
        registry.register("airtable_projects", AirtableProjectAdapter(airtable))
    return registry
