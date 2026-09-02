"""
Telegram Bot API 1.0 advanced features mixin for tool adapters.
"""
from __future__ import annotations

import logging
from typing import Any, Dict, List, Optional

from src.services.core.telegram.telegram_ai_features import (
    build_input_rich_message,
    build_text_article_result,
)
from src.services.core.tool_registry import ToolResult

logger = logging.getLogger(__name__)


class TelegramAPI10Mixin:
    """Advanced Bot API 1.0 features: polls, reactions, ephemeral replies, rich messages."""

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

    async def send_group_poll(
        self,
        chat_id: int,
        question: str,
        options: List[Dict[str, Any]],
        *,
        is_anonymous: bool = True,
        allows_multiple_answers: bool = False,
        members_only: Optional[bool] = None,
        country_codes: Optional[List[str]] = None,
        disable_notification: bool = False,
        thread_id: Optional[int] = None,
    ) -> ToolResult:
        """Send a poll with Bot API 10 audience limits (members_only, country_codes)."""
        try:
            message = await self.bot_api10.send_poll(
                chat_id,
                question,
                options,
                is_anonymous=is_anonymous,
                allows_multiple_answers=allows_multiple_answers,
                members_only=members_only,
                country_codes=country_codes,
                disable_notification=disable_notification,
                message_thread_id=thread_id,
            )
            return ToolResult(
                tool_name="telegram.poll",
                success=True,
                sent_count=1,
                group_message_id=message.get("message_id"),
                metadata={"chat_id": chat_id, "thread_id": thread_id},
            )
        except Exception as exc:
            logger.warning("[TELEGRAM TOOL] Poll send failed: %s", exc)
            return ToolResult(
                tool_name="telegram.poll",
                success=False,
                status="failed",
                reason=str(exc),
                failed_targets=[{"chat_id": chat_id, "error": str(exc)}],
                metadata={"chat_id": chat_id, "thread_id": thread_id},
            )

    async def clear_message_reactions(
        self,
        chat_id: int | str,
        message_id: int,
        user_id: int,
    ) -> ToolResult:
        """Remove a specific user's reaction from a message (Bot API 10 deleteMessageReaction).

        Only single-actor removal is exposed. deleteAllMessageReactions is actor-scoped
        (chat_id + user_id/actor_chat_id, not message-scoped), so a "clear every reaction
        on this message" call is intentionally not modeled here. Verify reaction methods
        against a live Bot API 10 bot before production use.
        """
        try:
            ok = await self.bot_api10.delete_message_reaction(
                chat_id, message_id, user_id
            )
            return ToolResult(
                tool_name="telegram.reaction_cleanup",
                success=bool(ok),
                status="succeeded" if ok else "failed",
                metadata={
                    "chat_id": chat_id,
                    "message_id": message_id,
                    "user_id": user_id,
                },
            )
        except Exception as exc:
            logger.warning("[TELEGRAM TOOL] Reaction cleanup failed: %s", exc)
            return ToolResult(
                tool_name="telegram.reaction_cleanup",
                success=False,
                status="failed",
                reason=str(exc),
                metadata={"chat_id": chat_id, "message_id": message_id},
            )

    async def fetch_user_personal_chat_messages(
        self,
        user_id: int,
        *,
        limit: int = 20,
    ) -> List[Dict[str, Any]]:
        """Read permissioned messages from a user's public personal channel/chat."""
        try:
            return await self.bot_api10.get_user_personal_chat_messages(
                user_id, limit=limit
            )
        except Exception as exc:
            logger.warning(
                "[TELEGRAM TOOL] Personal chat fetch failed for %s: %s", user_id, exc
            )
            return []

    async def send_ephemeral_reply(
        self,
        chat_id: int | str,
        text: str,
        receiver_user_id: int,
        *,
        thread_id: Optional[int] = None,
        parse_mode: Optional[str] = None,
        reply_markup: Optional[Dict[str, Any]] = None,
    ) -> ToolResult:
        """Send a private (ephemeral) reply visible only to receiver_user_id.

        Bot API 10.2 — verify against a live bot before enabling in production.
        """
        try:
            message = await self.bot_api10.send_ephemeral_message(
                chat_id,
                text,
                receiver_user_id=receiver_user_id,
                message_thread_id=thread_id,
                parse_mode=parse_mode or self.default_parse_mode,
                reply_markup=reply_markup,
            )
            return ToolResult(
                tool_name="telegram.ephemeral_message",
                success=True,
                sent_count=1,
                group_message_id=message.get("message_id"),
                metadata={"chat_id": chat_id, "receiver_user_id": receiver_user_id},
            )
        except Exception as exc:
            logger.warning("[TELEGRAM TOOL] Ephemeral reply failed: %s", exc)
            return ToolResult(
                tool_name="telegram.ephemeral_message",
                success=False,
                status="failed",
                reason=str(exc),
                metadata={"chat_id": chat_id, "receiver_user_id": receiver_user_id},
            )

    async def send_rich_group_message(
        self,
        chat_id: int | str,
        *,
        text: Optional[str] = None,
        blocks: Optional[List[Dict[str, Any]]] = None,
        thread_id: Optional[int] = None,
        reply_markup: Optional[Dict[str, Any]] = None,
    ) -> ToolResult:
        """Send a block-structured rich message (Bot API 10.1 sendRichMessage).

        Provide plain ``text`` and/or ``blocks`` (InputRichBlock* dicts). Verify the
        block schema against a live Bot API 10.1 bot before enabling in production.
        """
        try:
            rich_message = build_input_rich_message(text=text, blocks=blocks)
            if not rich_message:
                return ToolResult(
                    tool_name="telegram.rich_message",
                    success=False,
                    status="failed",
                    reason="rich message requires text or blocks",
                    metadata={"chat_id": chat_id},
                )
            message = await self.bot_api10.send_rich_message(
                chat_id,
                rich_message,
                message_thread_id=thread_id,
                reply_markup=reply_markup,
            )
            return ToolResult(
                tool_name="telegram.rich_message",
                success=True,
                sent_count=1,
                group_message_id=message.get("message_id"),
                metadata={"chat_id": chat_id, "thread_id": thread_id},
            )
        except Exception as exc:
            logger.warning("[TELEGRAM TOOL] Rich message send failed: %s", exc)
            return ToolResult(
                tool_name="telegram.rich_message",
                success=False,
                status="failed",
                reason=str(exc),
                failed_targets=[{"chat_id": chat_id, "error": str(exc)}],
                metadata={"chat_id": chat_id, "thread_id": thread_id},
            )
