"""Widget methods on top of the raw Bot API client."""
from __future__ import annotations

from typing import Any, Dict, Optional, Union

from src.services.core.telegram.ai_features.bot_api_client import TelegramBotAPI10Client
from src.services.core.telegram.widgets.limits import (
    MAX_ANSWER_BYTES,
    MAX_SHARED_CACHE_TIME,
    MIN_SHARED_CACHE_TIME,
    WidgetLimitError,
    validate_html,
    validate_state,
)

ChatId = Union[int, str]


class WidgetClient:
    """sendWidget / editMessageWidgetData / answerWidgetQuery and shared widgets."""

    def __init__(self, api: TelegramBotAPI10Client):
        self.api = api

    async def send_widget(
        self,
        chat_id: ChatId,
        html: str,
        *,
        caption: Optional[str] = None,
        allow_queries: bool = False,
        is_shared: bool = False,
        public_data: Optional[str] = None,
        chat_data: Optional[str] = None,
        width: Optional[int] = None,
        height: Optional[int] = None,
        message_thread_id: Optional[int] = None,
        reply_to_message_id: Optional[int] = None,
        protect_content: Optional[bool] = None,
        reply_markup: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        validate_html(html)
        validate_state("public_data", public_data)
        validate_state("chat_data", chat_data)
        result = await self.api.call(
            "sendWidget",
            {
                "chat_id": chat_id,
                "html": html,
                "caption": caption,
                "allow_queries": True if allow_queries else None,
                "is_shared": True if is_shared else None,
                "public_data": public_data,
                "chat_data": chat_data,
                "width": width,
                "height": height,
                "message_thread_id": message_thread_id,
                "reply_parameters": (
                    {"message_id": reply_to_message_id}
                    if reply_to_message_id is not None
                    else None
                ),
                "protect_content": protect_content,
                "reply_markup": reply_markup,
            },
        )
        return result if isinstance(result, dict) else {}

    async def edit_message_widget_data(
        self,
        *,
        chat_id: Optional[ChatId] = None,
        message_id: Optional[int] = None,
        inline_message_id: Optional[str] = None,
        chat_data: Optional[str] = None,
        public_data: Optional[str] = None,
    ) -> Any:
        if inline_message_id is None and (chat_id is None or message_id is None):
            raise ValueError("need inline_message_id or chat_id + message_id")
        validate_state("chat_data", chat_data)
        validate_state("public_data", public_data)
        return await self.api.call(
            "editMessageWidgetData",
            {
                "chat_id": chat_id,
                "message_id": message_id,
                "inline_message_id": inline_message_id,
                "chat_data": chat_data,
                "public_data": public_data,
            },
        )

    async def answer_widget_query(self, widget_query_id: str, data: Optional[str] = None) -> Any:
        validate_state("data", data, MAX_ANSWER_BYTES)
        return await self.api.call(
            "answerWidgetQuery",
            {"widget_query_id": widget_query_id, "data": data},
        )

    async def send_shared_widget(
        self,
        chat_id: ChatId,
        widget_id: str,
        *,
        chat_data: Optional[str] = None,
        caption: Optional[str] = None,
    ) -> Dict[str, Any]:
        validate_state("chat_data", chat_data)
        result = await self.api.call(
            "sendSharedWidget",
            {"chat_id": chat_id, "widget_id": widget_id, "chat_data": chat_data, "caption": caption},
        )
        return result if isinstance(result, dict) else {}

    async def edit_shared_widget_data(
        self,
        widget_id: str,
        *,
        public_data: Optional[str] = None,
        cache_time: Optional[int] = None,
    ) -> Any:
        validate_state("public_data", public_data)
        if cache_time is not None:
            if cache_time < MIN_SHARED_CACHE_TIME:
                raise WidgetLimitError(f"cache_time must be >= {MIN_SHARED_CACHE_TIME}")
            cache_time = min(cache_time, MAX_SHARED_CACHE_TIME)
        return await self.api.call(
            "editSharedWidgetData",
            {"widget_id": widget_id, "public_data": public_data, "cache_time": cache_time},
        )
