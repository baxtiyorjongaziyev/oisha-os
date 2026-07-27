"""Compatibility bridge for legacy Telethon bot handlers on Aiogram.

This adapter is only for the bot-token head.  It never accepts or wraps the
Telethon userbot session.  Legacy handlers can be migrated incrementally while
Aiogram remains the sole owner of bot updates.
"""

from __future__ import annotations

import inspect
import logging
from dataclasses import dataclass
from types import SimpleNamespace
from typing import Any, Awaitable, Callable, Optional

from src.services.core.telegram.bot_runtime import (
    AiogramBotRuntime,
    _coerce_aiogram_inline_keyboard,
)

logger = logging.getLogger(__name__)


def _parse_mode(value: Optional[str]) -> Optional[str]:
    return value.upper() if value else None


class AiogramLegacyMessageEvent:
    def __init__(self, message: Any, *, pattern_match: Any = None):
        self._message = message
        self.pattern_match = pattern_match
        reply = getattr(message, "reply_to_message", None)
        text = str(getattr(message, "text", "") or "")
        self.message = SimpleNamespace(
            message=text,
            text=text,
            entities=list(getattr(message, "entities", None) or []),
            reply_to=(
                SimpleNamespace(reply_to_msg_id=getattr(reply, "message_id", None))
                if reply is not None
                else None
            ),
            reply_to_msg_id=getattr(reply, "message_id", None),
        )

    @property
    def sender_id(self) -> int:
        return int(getattr(getattr(self._message, "from_user", None), "id", 0) or 0)

    @property
    def chat_id(self) -> int:
        return int(getattr(getattr(self._message, "chat", None), "id", 0) or 0)

    @property
    def text(self) -> str:
        return str(getattr(self._message, "text", "") or "")

    @property
    def raw_text(self) -> str:
        return self.text

    @property
    def entities(self) -> list[Any]:
        return list(getattr(self._message, "entities", None) or [])

    @property
    def is_private(self) -> bool:
        return str(getattr(getattr(self._message, "chat", None), "type", "")) == "private"

    @property
    def is_reply(self) -> bool:
        return getattr(self._message, "reply_to_message", None) is not None

    @property
    def reply_to(self) -> Any:
        return getattr(self._message, "reply_to_message", None)

    @property
    def reply_to_msg_id(self) -> Optional[int]:
        reply = getattr(self._message, "reply_to_message", None)
        return getattr(reply, "message_id", None)

    async def get_chat(self) -> Any:
        return getattr(self._message, "chat", None)

    async def get_sender(self) -> Any:
        return getattr(self._message, "from_user", None)

    async def get_reply_message(self) -> Any:
        reply = getattr(self._message, "reply_to_message", None)
        return AiogramLegacyMessageEvent(reply) if reply is not None else None

    async def respond(
        self,
        text: str,
        *,
        parse_mode: Optional[str] = None,
        buttons: Any = None,
        link_preview: bool = True,
        **kwargs: Any,
    ) -> "AiogramLegacyMessageEvent":
        if buttons is not None:
            kwargs["reply_markup"] = _coerce_aiogram_inline_keyboard(buttons)
        if not link_preview:
            try:
                from aiogram.types import LinkPreviewOptions

                kwargs["link_preview_options"] = LinkPreviewOptions(is_disabled=True)
            except Exception:
                kwargs["disable_web_page_preview"] = True
        sent = await self._message.answer(
            text,
            parse_mode=_parse_mode(parse_mode),
            **kwargs,
        )
        return AiogramLegacyMessageEvent(sent)

    reply = respond

    async def edit(
        self,
        text: str,
        *,
        parse_mode: Optional[str] = None,
        buttons: Any = None,
        link_preview: bool = True,
        **kwargs: Any,
    ) -> "AiogramLegacyMessageEvent":
        if buttons is not None:
            kwargs["reply_markup"] = _coerce_aiogram_inline_keyboard(buttons)
        if not link_preview:
            try:
                from aiogram.types import LinkPreviewOptions

                kwargs["link_preview_options"] = LinkPreviewOptions(is_disabled=True)
            except Exception:
                kwargs["disable_web_page_preview"] = True
        edited = await self._message.edit_text(
            text,
            parse_mode=_parse_mode(parse_mode),
            **kwargs,
        )
        return AiogramLegacyMessageEvent(edited)


class AiogramLegacyCallbackEvent:
    def __init__(self, callback: Any):
        self._callback = callback
        self.data = str(getattr(callback, "data", "") or "").encode()
        self.message = AiogramLegacyMessageEvent(callback.message)

    @property
    def sender_id(self) -> int:
        return int(getattr(getattr(self._callback, "from_user", None), "id", 0) or 0)

    async def get_sender(self) -> Any:
        return getattr(self._callback, "from_user", None)

    async def answer(self, text: str = "", *, alert: bool = False, **_: Any) -> None:
        await self._callback.answer(text, show_alert=alert)

    async def edit(self, text: str, **kwargs: Any) -> Any:
        return await self.message.edit(text, **kwargs)

    async def respond(self, text: str, **kwargs: Any) -> Any:
        return await self.message.respond(text, **kwargs)


@dataclass
class _MessageRegistration:
    handler: Callable[[Any], Awaitable[Any]]
    matcher: Optional[Callable[[str], Any]]


class AiogramTelethonCompatClient:
    """Capture Telethon decorators and dispatch them from one Aiogram router."""

    def __init__(self, *, bot: Any, dispatcher: Any):
        self.bot = bot
        self.dispatcher = dispatcher
        self.runtime = AiogramBotRuntime(bot)
        self._messages: list[_MessageRegistration] = []
        self._callbacks: list[Callable[[Any], Awaitable[Any]]] = []
        self._attached = False

    def on(self, builder: Any) -> Callable[[Callable[..., Any]], Callable[..., Any]]:
        kind = getattr(builder, "__module__", "") + "." + getattr(
            type(builder), "__name__", ""
        )

        def decorator(handler: Callable[..., Any]) -> Callable[..., Any]:
            if "newmessage" in kind.lower():
                pattern = getattr(builder, "pattern", None)
                matcher = getattr(pattern, "__self__", None)
                if matcher is not None:
                    matcher = matcher.match
                elif callable(pattern):
                    matcher = pattern
                self._messages.append(_MessageRegistration(handler, matcher))
            elif "callbackquery" in kind.lower():
                self._callbacks.append(handler)
            elif "inlinequery" in kind.lower():
                logger.info(
                    "[BOT] Legacy inline-query handler awaits native Aiogram migration."
                )
            elif inspect.isclass(builder) and builder.__name__ == "Raw":
                logger.info("[BOT] Legacy raw guest handler replaced by Bot API ingress.")
            return handler

        return decorator

    def attach(self) -> None:
        if self._attached:
            return
        self._attached = True

        @self.dispatcher.message()
        async def _dispatch_message(message: Any) -> None:
            text = str(getattr(message, "text", "") or "")
            for registration in self._messages:
                match = registration.matcher(text) if registration.matcher else None
                if registration.matcher is not None and match is None:
                    continue
                event = AiogramLegacyMessageEvent(message, pattern_match=match)
                await registration.handler(event)

        @self.dispatcher.callback_query()
        async def _dispatch_callback(callback: Any) -> None:
            event = AiogramLegacyCallbackEvent(callback)
            for handler in self._callbacks:
                await handler(event)

    async def send_message(self, chat_id: int | str, text: str, **kwargs: Any) -> Any:
        return (await self.runtime.send_message(chat_id, text, **kwargs)).raw

    async def get_entity(self, entity_id: int | str) -> Any:
        return await self.bot.get_chat(entity_id)
