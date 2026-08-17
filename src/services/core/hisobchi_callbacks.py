import logging
from typing import Any

from aiogram import F

from src.services.core.hisobchi_approval import handle_callback

logger = logging.getLogger(__name__)


class AiogramCallbackEventAdapter:
    """Expose the small Telethon callback surface used by Hisobchi.

    Replicated here to avoid circular imports.
    """

    def __init__(self, callback: Any):
        self.callback = callback
        self.data = getattr(callback, "data", None)

    async def answer(self, text: str = "") -> None:
        try:
            await self.callback.answer(text)
        except Exception as exc:
            logger.debug("[HISOBCHI] Callback answer failed: %s", exc)

    async def edit(self, text: str = None, *, parse_mode: str = None, buttons: Any = None) -> None:
        message = getattr(self.callback, "message", None)
        if message is None:
            return
        from src.services.core.telegram.bot_runtime import _coerce_aiogram_inline_keyboard
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


def register_callbacks(dispatcher: Any, *, engine: Any) -> None:
    """Register Hisobchi inline approval callbacks for Aiogram.

    This mirrors the original inline registration in `admin_aiogram_dispatcher.py`
    but is extracted to a dedicated module for cleaner separation.
    """
    prefixes = ("happrove:", "hedit:", "hskip:", "hcat:", "howner:", "hback:")

    @dispatcher.callback_query(F.data.startswith(prefixes))
    async def _hisobchi_callback(callback: Any) -> None:
        data = str(getattr(callback, "data", "") or "")
        event = AiogramCallbackEventAdapter(callback)
        try:
            await handle_callback(data, event, engine)
        except Exception:
            logger.error("Exception handled in %s", __name__, exc_info=True)
            await event.answer("⚠️ Xatolik yuz berdi, qayta urinib ko'ring.")
