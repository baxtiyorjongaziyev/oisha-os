"""
TelegramBotAPI10Client implementation for Telegram Bot API 10 features.
"""
from __future__ import annotations

import logging
from typing import Any, Dict, Iterable, List, Optional
import httpx

from src.services.core.telegram.ai_features.bot_api_extensions import (
    BotAPIExtensionsMixin,
)
from src.services.core.telegram.ai_features.models import (
    BOT_API_10_ALLOWED_UPDATES,
    BotApiTransport,
    TelegramBotAPIError,
    clean_payload,
)

logger = logging.getLogger("TelegramBotAPI10Client")

class TelegramBotAPI10Client(BotAPIExtensionsMixin):
    """Small raw Bot API client for methods not yet exposed by local libraries."""

    def __init__(
        self,
        token: str,
        *,
        base_url: str = "https://api.telegram.org",
        timeout: float = 15.0,
        transport: Optional[BotApiTransport] = None,
    ):
        self.token = token.strip()
        self.base_url = base_url.rstrip("/")
        self.timeout = timeout
        self.transport = transport

    async def call(self, method: str, payload: Optional[Dict[str, Any]] = None) -> Any:
        cleaned = clean_payload(payload)
        if self.transport is not None:
            response_payload = await self.transport(method, cleaned)
        else:
            url = f"{self.base_url}/bot{self.token}/{method}"
            async with httpx.AsyncClient(timeout=self.timeout) as client:
                response = await client.post(url, json=cleaned)
                response_payload = response.json()

        if not isinstance(response_payload, dict) or not response_payload.get("ok"):
            description = (
                response_payload.get("description")
                if isinstance(response_payload, dict)
                else "invalid Bot API response"
            )
            raise TelegramBotAPIError(
                method,
                str(description or "unknown error"),
                error_code=(
                    response_payload.get("error_code")
                    if isinstance(response_payload, dict)
                    else None
                ),
                parameters=(
                    response_payload.get("parameters")
                    if isinstance(response_payload, dict)
                    else None
                ),
            )
        return response_payload.get("result")

    async def get_me(self) -> Dict[str, Any]:
        result = await self.call("getMe")
        return result if isinstance(result, dict) else {}

    async def get_webhook_info(self) -> Dict[str, Any]:
        result = await self.call("getWebhookInfo")
        return result if isinstance(result, dict) else {}

    async def get_updates(
        self,
        *,
        offset: Optional[int] = None,
        timeout: int = 25,
        limit: int = 100,
        allowed_updates: Optional[Iterable[str]] = None,
    ) -> List[Dict[str, Any]]:
        result = await self.call(
            "getUpdates",
            {
                "offset": offset,
                "timeout": timeout,
                "limit": limit,
                "allowed_updates": list(allowed_updates or BOT_API_10_ALLOWED_UPDATES),
            },
        )
        return result if isinstance(result, list) else []

    async def set_webhook(
        self,
        url: str,
        *,
        secret_token: Optional[str] = None,
        allowed_updates: Optional[Iterable[str]] = None,
        drop_pending_updates: bool = False,
    ) -> bool:
        result = await self.call(
            "setWebhook",
            {
                "url": url,
                "secret_token": secret_token,
                "allowed_updates": list(allowed_updates or BOT_API_10_ALLOWED_UPDATES),
                "drop_pending_updates": drop_pending_updates,
            },
        )
        return bool(result)

    async def answer_guest_query(
        self,
        guest_query_id: str,
        result: Dict[str, Any],
    ) -> Dict[str, Any]:
        sent = await self.call(
            "answerGuestQuery",
            {"guest_query_id": guest_query_id, "result": result},
        )
        return sent if isinstance(sent, dict) else {}

    async def send_message_draft(
        self,
        chat_id: int,
        draft_id: int,
        *,
        text: str = "",
        message_thread_id: Optional[int] = None,
        parse_mode: Optional[str] = None,
        can_stop: Optional[bool] = None,
        keep_on_stop: Optional[bool] = None,
    ) -> bool:
        result = await self.call(
            "sendMessageDraft",
            {
                "chat_id": chat_id,
                "message_thread_id": message_thread_id,
                "draft_id": draft_id,
                "text": text,
                "parse_mode": parse_mode,
                "can_stop": can_stop,
                "keep_on_stop": keep_on_stop,
            },
        )
        return bool(result)

    async def finalize_streamed_message(
        self,
        chat_id: int,
        text: str,
        *,
        message_thread_id: Optional[int] = None,
        parse_mode: Optional[str] = "HTML",
    ) -> Dict[str, Any]:
        message = await self.call(
            "sendMessage",
            {
                "chat_id": chat_id,
                "message_thread_id": message_thread_id,
                "text": text,
                "parse_mode": parse_mode,
            },
        )
        return message if isinstance(message, dict) else {}

    async def send_to_bot(
        self,
        bot_username: str,
        text: str,
        *,
        business_connection_id: Optional[str] = None,
        reply_parameters: Optional[Dict[str, Any]] = None,
        parse_mode: Optional[str] = "HTML",
    ) -> Dict[str, Any]:
        username = bot_username if bot_username.startswith("@") else f"@{bot_username}"
        message = await self.call(
            "sendMessage",
            {
                "business_connection_id": business_connection_id,
                "chat_id": username,
                "text": text,
                "parse_mode": parse_mode,
                "reply_parameters": reply_parameters,
            },
        )
        return message if isinstance(message, dict) else {}

    async def get_managed_bot_access_settings(self, user_id: int) -> Dict[str, Any]:
        result = await self.call(
            "getManagedBotAccessSettings",
            {"user_id": user_id},
        )
        return result if isinstance(result, dict) else {}

    async def set_managed_bot_access_settings(
        self,
        user_id: int,
        *,
        is_access_restricted: bool,
        added_user_ids: Optional[List[int]] = None,
    ) -> bool:
        result = await self.call(
            "setManagedBotAccessSettings",
            {
                "user_id": user_id,
                "is_access_restricted": is_access_restricted,
                "added_user_ids": added_user_ids,
            },
        )
        return bool(result)

    async def delete_webhook(self, *, drop_pending_updates: bool = False) -> bool:
        result = await self.call(
            "deleteWebhook",
            {"drop_pending_updates": drop_pending_updates},
        )
        return bool(result)

    async def get_user_personal_chat_messages(
        self,
        user_id: int,
        *,
        limit: int = 20,
    ) -> List[Dict[str, Any]]:
        bounded_limit = max(1, min(int(limit), 20))
        result = await self.call(
            "getUserPersonalChatMessages",
            {"user_id": user_id, "limit": bounded_limit},
        )
        return result if isinstance(result, list) else []

    async def delete_message_reaction(
        self,
        chat_id: int | str,
        message_id: int,
        user_id: int,
    ) -> bool:
        result = await self.call(
            "deleteMessageReaction",
            {"chat_id": chat_id, "message_id": message_id, "user_id": user_id},
        )
        return bool(result)

    async def delete_all_message_reactions(
        self,
        chat_id: int | str,
        *,
        user_id: Optional[int] = None,
        actor_chat_id: Optional[int | str] = None,
    ) -> bool:
        """Remove an actor's recent reactions in a chat (Bot API 10, actor-scoped)."""
        result = await self.call(
            "deleteAllMessageReactions",
            {"chat_id": chat_id, "user_id": user_id, "actor_chat_id": actor_chat_id},
        )
        return bool(result)

    async def send_poll(
        self,
        chat_id: int | str,
        question: str,
        options: List[Dict[str, Any]],
        *,
        is_anonymous: bool = True,
        type: str = "regular",
        allows_multiple_answers: bool = False,
        members_only: Optional[bool] = None,
        country_codes: Optional[List[str]] = None,
        disable_notification: bool = False,
        message_thread_id: Optional[int] = None,
    ) -> Dict[str, Any]:
        """Send poll with Bot API 10 limit parameters (members_only, country_codes)."""
        result = await self.call(
            "sendPoll",
            {
                "chat_id": chat_id,
                "question": question,
                "options": options,
                "is_anonymous": is_anonymous,
                "type": type,
                "allows_multiple_answers": allows_multiple_answers,
                "members_only": members_only,
                "country_codes": country_codes,
                "disable_notification": disable_notification,
                "message_thread_id": message_thread_id,
            },
        )
        return result if isinstance(result, dict) else {}

    async def send_ephemeral_message(
        self,
        chat_id: Optional[int | str],
        text: str,
        *,
        receiver_user_id: Optional[int] = None,
        callback_query_id: Optional[str] = None,
        replace_callback_query_message: Optional[bool] = None,
        ephemeral_message_parameters: Optional[Dict[str, Any]] = None,
        message_thread_id: Optional[int] = None,
        parse_mode: Optional[str] = "HTML",
        reply_markup: Optional[Dict[str, Any]] = None,
        disable_notification: bool = False,
    ) -> Dict[str, Any]:
        """Send a message visible only to one user (Bot API 10.2–10.4)."""
        result = await self.call(
            "sendMessage",
            {
                "chat_id": chat_id,
                "text": text,
                "receiver_user_id": receiver_user_id if ephemeral_message_parameters is None else None,
                "callback_query_id": callback_query_id if ephemeral_message_parameters is None else None,
                "ephemeral_message_parameters": ephemeral_message_parameters,
                "message_thread_id": message_thread_id,
                "parse_mode": parse_mode,
                "reply_markup": reply_markup,
                "disable_notification": disable_notification,
            },
        )
        return result if isinstance(result, dict) else {}

    async def delete_ephemeral_message(
        self,
        chat_id: int | str,
        ephemeral_message_id: int,
    ) -> bool:
        """Delete a previously sent ephemeral message (Bot API 10.2)."""
        result = await self.call(
            "deleteEphemeralMessage",
            {"chat_id": chat_id, "ephemeral_message_id": ephemeral_message_id},
        )
        return bool(result)

    async def send_rich_message(
        self,
        chat_id: int | str,
        rich_message: Dict[str, Any],
        *,
        business_connection_id: Optional[str] = None,
        message_thread_id: Optional[int] = None,
        reply_parameters: Optional[Dict[str, Any]] = None,
        link_preview_options: Optional[Dict[str, Any]] = None,
        reply_markup: Optional[Dict[str, Any]] = None,
        effect_id: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Send a block-structured rich message (Bot API 10.1+ ``sendRichMessage``)."""
        result = await self.call(
            "sendRichMessage",
            {
                "chat_id": chat_id,
                "rich_message": rich_message,
                "business_connection_id": business_connection_id,
                "message_thread_id": message_thread_id,
                "reply_parameters": reply_parameters,
                "link_preview_options": link_preview_options,
                "reply_markup": reply_markup,
                "effect_id": effect_id,
            },
        )
        return result if isinstance(result, dict) else {}

    async def set_my_settings(
        self,
        *,
        supports_inline_queries: Optional[bool] = None,
        inline_query_placeholder: Optional[str] = None,
        needs_inline_query_location: Optional[bool] = None,
        inline_feedback_share_denominator: Optional[int] = None,
        can_join_groups: Optional[bool] = None,
        can_read_all_group_messages: Optional[bool] = None,
        can_connect_to_business: Optional[bool] = None,
        can_manage_bots: Optional[bool] = None,
        supports_guest_queries: Optional[bool] = None,
        supports_join_request_queries: Optional[bool] = None,
        has_topics_enabled: Optional[bool] = None,
        allows_users_to_create_topics: Optional[bool] = None,
        has_topic_sidebar: Optional[bool] = None,
        can_communicate_with_bots: Optional[bool] = None,
        callback_query_mode: Optional[str] = None,
    ) -> bool:
        """Automate bot configuration (Bot API 10.5 ``setMySettings``)."""
        if callback_query_mode is not None and callback_query_mode not in ("default", "auto", "inline"):
            raise ValueError(f"Invalid callback_query_mode: {callback_query_mode}")
        if inline_feedback_share_denominator is not None and inline_feedback_share_denominator not in (0, 1, 10, 100, 1000):
            raise ValueError(f"Invalid inline_feedback_share_denominator: {inline_feedback_share_denominator}")
        result = await self.call("setMySettings", {
            "supports_inline_queries": supports_inline_queries, "inline_query_placeholder": inline_query_placeholder,
            "needs_inline_query_location": needs_inline_query_location, "inline_feedback_share_denominator": inline_feedback_share_denominator,
            "can_join_groups": can_join_groups, "can_read_all_group_messages": can_read_all_group_messages,
            "can_connect_to_business": can_connect_to_business, "can_manage_bots": can_manage_bots,
            "supports_guest_queries": supports_guest_queries, "supports_join_request_queries": supports_join_request_queries,
            "has_topics_enabled": has_topics_enabled, "allows_users_to_create_topics": allows_users_to_create_topics,
            "has_topic_sidebar": has_topic_sidebar, "can_communicate_with_bots": can_communicate_with_bots,
            "callback_query_mode": callback_query_mode,
        })
        return bool(result)

