"""
TelegramBotAPI10Client implementation for Telegram Bot API 10 features.
"""
from __future__ import annotations

import logging
from typing import Any, Dict, Iterable, List, Optional
import httpx

from src.services.core.telegram.ai_features.models import (
    BOT_API_10_ALLOWED_UPDATES,
    BotApiTransport,
    TelegramBotAPIError,
    clean_payload,
)

logger = logging.getLogger("TelegramBotAPI10Client")

class TelegramBotAPI10Client:
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
    ) -> bool:
        result = await self.call(
            "sendMessageDraft",
            {
                "chat_id": chat_id,
                "message_thread_id": message_thread_id,
                "draft_id": draft_id,
                "text": text,
                "parse_mode": parse_mode,
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
        """Remove an actor's recent reactions in a chat (Bot API 10, actor-scoped).

        Per the changelog this is scoped to an actor (``user_id`` or ``actor_chat_id``),
        not to a single message. Unverified here — confirm against a live Bot API 10 bot
        before production use.
        """
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
        chat_id: int | str,
        text: str,
        *,
        receiver_user_id: Optional[int] = None,
        callback_query_id: Optional[str] = None,
        message_thread_id: Optional[int] = None,
        parse_mode: Optional[str] = "HTML",
        reply_markup: Optional[Dict[str, Any]] = None,
        disable_notification: bool = False,
    ) -> Dict[str, Any]:
        """Send a message visible only to one user (Bot API 10.2).

        Pass ``receiver_user_id`` to show the message to a single group member, or
        ``callback_query_id`` to answer an ephemeral callback. NOTE: verify against a
        live Bot API 10.2 bot before enabling in production.
        """
        result = await self.call(
            "sendMessage",
            {
                "chat_id": chat_id,
                "text": text,
                "receiver_user_id": receiver_user_id,
                "callback_query_id": callback_query_id,
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
        """Send a block-structured rich message (Bot API 10.1 ``sendRichMessage``).

        ``rich_message`` is an InputRichMessage dict — e.g.
        ``{"text": "...", "blocks": [...]}``. Build it with
        :func:`build_input_rich_message`. NOTE: verify block schema against a live
        Bot API 10.1 bot before enabling in production.
        """
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

