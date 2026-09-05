from __future__ import annotations
from src.context import app_ctx

import logging
from typing import Any, Dict, List, Optional

from telegram import Bot

from src.services.core.telegram.telegram_ai_features import (
    TelegramBotAPI10Client,
)
from src.services.core.tool_registry import ToolResult

logger = logging.getLogger(__name__)



def configure_userbot_group_fallback(client: Optional[Any]) -> None:
    """Reuse the running userbot for group delivery when the bot lacks access."""
    app_ctx.userbot_group_fallback = client


async def send_group_message_with_fallback(
    bot: Any,
    *,
    chat_id: int,
    text: str,
    thread_id: Optional[int] = None,
    parse_mode: Optional[str] = None,
    disable_web_page_preview: bool = False,
    allow_userbot_fallback: bool = True,
) -> Any:
    """Send through Bot API first, then through the already-connected userbot."""
    try:
        return await bot.send_message(
            chat_id=chat_id,
            text=text,
            parse_mode=parse_mode,
            message_thread_id=thread_id,
            disable_web_page_preview=disable_web_page_preview,
        )
    except Exception as bot_exc:
        if not allow_userbot_fallback or app_ctx.userbot_group_fallback is None:
            raise
        logger.warning(
            "[TELEGRAM TOOL] Bot group send failed; using userbot fallback: %s",
            bot_exc,
        )
        kwargs: Dict[str, Any] = {
            "link_preview": not disable_web_page_preview,
        }
        if thread_id:
            kwargs["reply_to"] = thread_id
        if parse_mode:
            kwargs["parse_mode"] = str(parse_mode).lower()
        return await app_ctx.userbot_group_fallback.send_message(chat_id, text, **kwargs)


from src.services.core.tool_adapters_pkg.telegram_api10 import TelegramAPI10Mixin


class TelegramNotificationAdapter(TelegramAPI10Mixin):
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
        allow_userbot_fallback: bool = True,
    ) -> ToolResult:
        try:
            message = await send_group_message_with_fallback(
                self.bot,
                chat_id=chat_id,
                text=text,
                parse_mode=parse_mode or self.default_parse_mode,
                thread_id=thread_id,
                disable_web_page_preview=disable_web_page_preview,
                allow_userbot_fallback=allow_userbot_fallback,
            )
            return ToolResult(
                tool_name="telegram.group_message",
                success=True,
                sent_count=1,
                group_message_id=getattr(message, "message_id", None)
                or getattr(message, "id", None),
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
