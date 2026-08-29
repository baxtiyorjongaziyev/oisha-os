"""
AiogramCallbackEventAdapter bridging aiogram callback queries to Telethon-style events.
"""
from __future__ import annotations

import logging
from typing import Any, Optional

logger = logging.getLogger("AiogramCallbackEventAdapter")

class AiogramCallbackEventAdapter:
    """Expose the small Telethon callback surface used by Hisobchi."""

    def __init__(self, callback: Any):
        self.callback = callback
        self.data = getattr(callback, "data", None)

    async def answer(self, text: str = "") -> None:
        try:
            await self.callback.answer(text)
        except Exception as exc:
            logger.debug("[HISOBCHI] Callback answer failed: %s", exc)

    async def edit(
        self,
        text: Optional[str] = None,
        *,
        parse_mode: Optional[str] = None,
        buttons: Any = None,
    ) -> None:
        message = getattr(self.callback, "message", None)
        if message is None:
            return
        from src.services.core.telegram.bot_runtime import (
            _coerce_aiogram_inline_keyboard,
        )
        try:
            if text is None:
                if buttons is not None:
                    reply_markup = _coerce_aiogram_inline_keyboard(buttons)
                    await message.edit_reply_markup(reply_markup=reply_markup)
                return

            kwargs: dict[str, Any] = {}
            if parse_mode:
                kwargs["parse_mode"] = parse_mode.upper()
            if buttons is not None:
                kwargs["reply_markup"] = _coerce_aiogram_inline_keyboard(buttons)
            else:
                kwargs["reply_markup"] = None
            await message.edit_text(text, **kwargs)
        except Exception as exc:
            err_msg = str(exc).lower()
            if "message is not modified" in err_msg:
                logger.debug("[HISOBCHI] edit ignored message not modified: %s", exc)
                return
            logger.warning("[HISOBCHI] edit message failed: %s", exc)
