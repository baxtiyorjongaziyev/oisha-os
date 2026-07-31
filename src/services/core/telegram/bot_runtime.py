"""Bot-token runtime ports for the Telethon -> Aiogram migration.

Userbot stays on Telethon. This module only abstracts the bot account head
(@jonairobot) so callers can move one flow at a time without changing business
logic.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Optional, Protocol
import logging
logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class SentBotMessage:
    chat_id: int | str
    message_id: Optional[int]
    backend: str
    raw: Any = None


class BotRuntimePort(Protocol):
    backend: str

    async def send_message(
        self,
        chat_id: int | str,
        text: str,
        *,
        parse_mode: Optional[str] = None,
        message_thread_id: Optional[int] = None,
        disable_web_page_preview: bool = False,
        disable_notification: bool = False,
        reply_to_message_id: Optional[int] = None,
        **extra: Any,
    ) -> SentBotMessage:
        """Send one bot-account message through the selected backend."""


class TelethonBotRuntime:
    """Compatibility wrapper for the current Telethon bot-token client."""

    backend = "telethon"

    def __init__(self, client: Any):
        self.client = client

    async def send_message(
        self,
        chat_id: int | str,
        text: str,
        *,
        parse_mode: Optional[str] = None,
        message_thread_id: Optional[int] = None,
        disable_web_page_preview: bool = False,
        disable_notification: bool = False,
        reply_to_message_id: Optional[int] = None,
        **extra: Any,
    ) -> SentBotMessage:
        kwargs: dict[str, Any] = dict(extra)
        if parse_mode:
            kwargs["parse_mode"] = parse_mode.lower()
        if message_thread_id:
            kwargs["reply_to"] = message_thread_id
        elif reply_to_message_id:
            kwargs["reply_to"] = reply_to_message_id
        kwargs["link_preview"] = not disable_web_page_preview
        if disable_notification:
            kwargs["silent"] = True

        message = await self.client.send_message(chat_id, text, **kwargs)
        return SentBotMessage(
            chat_id=chat_id,
            message_id=getattr(message, "id", None)
            or getattr(message, "message_id", None),
            backend=self.backend,
            raw=message,
        )


class AiogramBotRuntime:
    """Aiogram wrapper with the same surface as TelethonBotRuntime."""

    backend = "aiogram"

    def __init__(self, bot: Any):
        self.bot = bot

    async def send_message(
        self,
        chat_id: int | str,
        text: str,
        *,
        parse_mode: Optional[str] = None,
        message_thread_id: Optional[int] = None,
        disable_web_page_preview: bool = False,
        disable_notification: bool = False,
        reply_to_message_id: Optional[int] = None,
        **extra: Any,
    ) -> SentBotMessage:
        kwargs: dict[str, Any] = dict(extra)
        buttons = kwargs.pop("buttons", None)
        reply_to = kwargs.pop("reply_to", None)
        if parse_mode:
            kwargs["parse_mode"] = parse_mode
        if message_thread_id:
            kwargs["message_thread_id"] = message_thread_id
        if disable_notification:
            kwargs["disable_notification"] = True

        if disable_web_page_preview:
            try:
                from aiogram.types import LinkPreviewOptions

                kwargs["link_preview_options"] = LinkPreviewOptions(is_disabled=True)
            except Exception:
                logger.error("Exception handled in %s", __name__, exc_info=True)
                kwargs["disable_web_page_preview"] = True

        if reply_to_message_id or reply_to:
            kwargs["reply_to_message_id"] = reply_to_message_id or reply_to
        if buttons is not None and "reply_markup" not in kwargs:
            reply_markup = _coerce_aiogram_inline_keyboard(buttons)
            if reply_markup is not None:
                kwargs["reply_markup"] = reply_markup

        message = await self.bot.send_message(chat_id=chat_id, text=text, **kwargs)
        return SentBotMessage(
            chat_id=chat_id,
            message_id=getattr(message, "message_id", None)
            or getattr(message, "id", None),
            backend=self.backend,
            raw=message,
        )


def build_bot_runtime(*, backend: str, client: Any) -> BotRuntimePort:
    normalized = backend.strip().lower()
    if normalized == "telethon":
        return TelethonBotRuntime(client)
    if normalized == "aiogram":
        return AiogramBotRuntime(client)
    raise ValueError(f"Unsupported bot runtime backend: {backend}")


def build_outbound_bot_runtime(
    *,
    backend: str,
    bot_token: str,
    telethon_client: Any,
) -> BotRuntimePort:
    """Build the outbound bot runtime without starting any update receiver.

    This is intentionally send-only. Telethon can continue owning bot updates
    while Aiogram is tested for outbound messages behind a feature flag.
    """
    normalized = backend.strip().lower()
    if normalized in {"", "telethon"}:
        return TelethonBotRuntime(telethon_client)
    if normalized == "aiogram":
        from aiogram import Bot

        return AiogramBotRuntime(Bot(token=bot_token))
    raise ValueError(f"Unsupported bot runtime backend: {backend}")


def _coerce_aiogram_inline_keyboard(buttons: Any) -> Any:
    """Convert Telethon-style inline button rows to Aiogram markup when possible."""
    if buttons is None:
        return None
    if hasattr(buttons, "inline_keyboard"):
        return buttons
    try:
        from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup
    except Exception:
        logger.error("Exception handled in %s", __name__, exc_info=True)
        return buttons

    rows = buttons if isinstance(buttons, list) else [[buttons]]
    keyboard: list[list[Any]] = []
    for row in rows:
        source_row = row if isinstance(row, list) else [row]
        converted_row = []
        for button in source_row:
            text = None
            data = None
            if isinstance(button, dict):
                text = button.get("text")
                data = button.get("callback_data") or button.get("data")
            else:
                text = getattr(button, "text", None)
                data = getattr(button, "callback_data", None) or getattr(button, "data", None)
            if isinstance(data, bytes):
                data = data.decode("utf-8")
            if text and data:
                converted_row.append(
                    InlineKeyboardButton(text=str(text), callback_data=str(data))
                )
        if converted_row:
            keyboard.append(converted_row)
    if not keyboard:
        return None
    return InlineKeyboardMarkup(inline_keyboard=keyboard)
