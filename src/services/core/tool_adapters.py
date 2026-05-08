from __future__ import annotations

import asyncio
import logging
from typing import Any, Dict, List, Optional

from telegram import Bot

from src.services.core.airtable_sync import AirtableSync
from src.services.core.amocrm_sync import AmoCRMSync
from src.services.core.telegram_ai_features import (
    TelegramBotAPI10Client,
    build_text_article_result,
)
from src.services.core.tool_registry import ToolRegistry, ToolResult

logger = logging.getLogger(__name__)


class TelegramNotificationAdapter:
    tool_name = "telegram"

    def __init__(self, bot_token: str, default_parse_mode: str = "HTML"):
        self.bot_token = bot_token
        self.bot = Bot(token=bot_token)
        self.bot_api10 = TelegramBotAPI10Client(bot_token)
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
                    parse_mode=item.get("parse_mode")
                    or parse_mode
                    or self.default_parse_mode,
                    disable_web_page_preview=disable_web_page_preview,
                )
                delivered_to.append(user_id)
                direct_message_ids.append(message.message_id)
            except Exception as exc:
                logger.warning(
                    "[TELEGRAM TOOL] DM send failed for %s: %s", user_id, exc
                )
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

    async def stream_direct_message(
        self,
        chat_id: int,
        final_text: str,
        *,
        draft_id: int,
        draft_text: str = "",
        thread_id: Optional[int] = None,
        parse_mode: Optional[str] = None,
    ) -> ToolResult:
        """Show a temporary Bot API 10.0 draft, then persist the final message."""
        try:
            await self.bot_api10.send_message_draft(
                chat_id,
                draft_id,
                text=draft_text,
                message_thread_id=thread_id,
                parse_mode=parse_mode or self.default_parse_mode,
            )
            message = await self.bot_api10.finalize_streamed_message(
                chat_id,
                final_text,
                message_thread_id=thread_id,
                parse_mode=parse_mode or self.default_parse_mode,
            )
            return ToolResult(
                tool_name="telegram.streaming_message",
                success=True,
                sent_count=1,
                direct_message_ids=[int(message.get("message_id", 0))],
                metadata={"chat_id": chat_id, "thread_id": thread_id, "draft_id": draft_id},
            )
        except Exception as exc:
            logger.warning("[TELEGRAM TOOL] Streaming send failed: %s", exc)
            return ToolResult(
                tool_name="telegram.streaming_message",
                success=False,
                status="failed",
                reason=str(exc),
                failed_targets=[{"chat_id": chat_id, "error": str(exc)}],
                metadata={"chat_id": chat_id, "thread_id": thread_id, "draft_id": draft_id},
            )

    async def answer_guest_query(
        self,
        guest_query_id: str,
        text: str,
        *,
        title: str = "Oisha javobi",
        parse_mode: str = "HTML",
    ) -> ToolResult:
        try:
            result = build_text_article_result(text, title=title, parse_mode=parse_mode)
            sent = await self.bot_api10.answer_guest_query(guest_query_id, result)
            return ToolResult(
                tool_name="telegram.guest_query",
                success=True,
                sent_count=1,
                direct_message_ids=[],
                metadata={
                    "guest_query_id": guest_query_id,
                    "inline_message_id": sent.get("inline_message_id"),
                },
            )
        except Exception as exc:
            logger.warning("[TELEGRAM TOOL] Guest query answer failed: %s", exc)
            return ToolResult(
                tool_name="telegram.guest_query",
                success=False,
                status="failed",
                reason=str(exc),
                metadata={"guest_query_id": guest_query_id},
            )

    async def send_bot_to_bot_message(
        self,
        bot_username: str,
        text: str,
        *,
        business_connection_id: Optional[str] = None,
        parse_mode: Optional[str] = None,
    ) -> ToolResult:
        try:
            message = await self.bot_api10.send_to_bot(
                bot_username,
                text,
                business_connection_id=business_connection_id,
                parse_mode=parse_mode or self.default_parse_mode,
            )
            return ToolResult(
                tool_name="telegram.bot_to_bot",
                success=True,
                sent_count=1,
                group_message_id=message.get("message_id"),
                metadata={"bot_username": bot_username},
            )
        except Exception as exc:
            logger.warning("[TELEGRAM TOOL] Bot-to-bot send failed: %s", exc)
            return ToolResult(
                tool_name="telegram.bot_to_bot",
                success=False,
                status="failed",
                reason=str(exc),
                failed_targets=[{"bot_username": bot_username, "error": str(exc)}],
                metadata={"bot_username": bot_username},
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

    def get_last_error(self) -> Optional[str]:
        return getattr(self.amocrm, "last_error", None)

    async def create_followup_task(
        self,
        lead_id: int,
        text: str,
        complete_till: int,
        *,
        responsible_user_id: Optional[int] = None,
    ) -> ToolResult:
        result = await self.amocrm.create_task(
            int(lead_id),
            text,
            int(complete_till),
            responsible_user_id=responsible_user_id,
        )
        task_id = self._extract_embedded_id(result, "tasks")
        success = bool(result and task_id)
        return ToolResult(
            tool_name="amocrm.followup_task",
            success=success,
            status="ok" if success else "failed",
            reason=None if success else (self.get_last_error() or "task_create_failed"),
            metadata={
                "lead_id": int(lead_id),
                "task_id": task_id,
                "complete_till": int(complete_till),
                "responsible_user_id": responsible_user_id,
            },
            raw=result if isinstance(result, dict) else {},
        )

    async def add_lead_note(self, lead_id: int, text: str) -> ToolResult:
        result = await asyncio.to_thread(self.amocrm.add_lead_note, int(lead_id), text)
        note_id = self._extract_embedded_id(result, "notes")
        success = bool(result and note_id)
        return ToolResult(
            tool_name="amocrm.lead_note",
            success=success,
            status="ok" if success else "failed",
            reason=None if success else (self.get_last_error() or "note_create_failed"),
            metadata={"lead_id": int(lead_id), "note_id": note_id},
            raw=result if isinstance(result, dict) else {},
        )

    async def update_lead_status(
        self,
        lead_id: int,
        status_id: int,
        *,
        pipeline_id: Optional[int] = None,
    ) -> ToolResult:
        result = await self.amocrm.update_lead_status(
            int(lead_id),
            int(status_id),
            int(pipeline_id) if pipeline_id else None,
        )
        updated_id = None
        if isinstance(result, dict):
            updated_id = result.get("id") or self._extract_embedded_id(result, "leads")
        success = bool(result and (updated_id or result is True))
        return ToolResult(
            tool_name="amocrm.lead_status",
            success=success,
            status="ok" if success else "failed",
            reason=(
                None
                if success
                else (self.get_last_error() or "lead_status_update_failed")
            ),
            metadata={
                "lead_id": int(lead_id),
                "updated_id": updated_id or int(lead_id),
                "status_id": int(status_id),
                "pipeline_id": pipeline_id,
            },
            raw=result if isinstance(result, dict) else {},
        )

    @staticmethod
    def _extract_embedded_id(result: Any, collection_name: str) -> Optional[int]:
        if not isinstance(result, dict):
            return None
        embedded = result.get("_embedded") or {}
        collection = embedded.get(collection_name) or []
        if isinstance(collection, list) and collection:
            item = collection[0] or {}
            if isinstance(item, dict) and item.get("id"):
                return int(item["id"])
        if result.get("id"):
            return int(result["id"])
        return None


class AirtableProjectAdapter:
    tool_name = "airtable_projects"

    def __init__(self, airtable: AirtableSync):
        self.airtable = airtable

    async def fetch_projects(self) -> List[Dict[str, Any]]:
        return await asyncio.to_thread(self.airtable.get_projects)

    async def update_stage(self, record_id: str, next_stage: str) -> ToolResult:
        result = await asyncio.to_thread(
            self.airtable.update_project_stage, record_id, next_stage
        )
        success = bool(result)
        return ToolResult(
            tool_name="airtable.project_stage",
            success=success,
            status="ok" if success else "failed",
            reason=None if success else "airtable_stage_update_failed",
            metadata={"record_id": record_id, "next_stage": next_stage},
            raw=result if isinstance(result, dict) else {},
        )

    async def update_fields(self, record_id: str, fields: Dict[str, Any]) -> ToolResult:
        result = await asyncio.to_thread(
            self.airtable.update_project_fields, record_id, fields
        )
        success = bool(result)
        return ToolResult(
            tool_name="airtable.project_fields",
            success=success,
            status="ok" if success else "failed",
            reason=None if success else "airtable_fields_update_failed",
            metadata={"record_id": record_id, "field_names": sorted(fields.keys())},
            raw=result if isinstance(result, dict) else {},
        )

    async def get_record_link(self, record_id: str) -> Optional[str]:
        return await asyncio.to_thread(self.airtable.get_record_url, record_id)


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
