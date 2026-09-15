"""
Hisobchi and SalesCoach aiogram callback query registration handlers.
"""
from __future__ import annotations

import logging
from typing import Any
import src.handlers.callbacks as cb

logger = logging.getLogger("AdminAiogramCallbacks")

def register_hisobchi_aiogram_callbacks(
    dispatcher: Any,
    *,
    engine: Any,
) -> None:
    """Route every Hisobchi inline approval callback through Aiogram."""
    from aiogram import F
    from src.services.core.hisobchi_callbacks import register_callbacks

    prefixes = ("happrove:", "hedit:", "hskip:", "hcat:", "howner:", "hback:")

    register_callbacks(dispatcher, engine=engine)

    from src.services.core.airtable_approval_callbacks import register_airtable_approval_callbacks
    register_airtable_approval_callbacks(dispatcher)

    # Register additional custom callbacks defined in src.handlers.callbacks
    @dispatcher.callback_query(F.data.startswith("task_conf:"))
    async def _task_conf_cb(callback: Any) -> None:
        try:
            await cb.task_conf_callback(callback.update, None, db=engine.db)
        except Exception:
            logger.error("task_conf_callback failed", exc_info=True)
            await callback.answer("Xatolik yuz berdi, qayta urinib ko'ring")

    @dispatcher.callback_query(F.data.startswith("strat_conf:"))
    async def _strat_conf_cb(callback: Any) -> None:
        try:
            await cb.strat_conf_callback(callback.update, None)
        except Exception:
            logger.error("strat_conf_callback failed", exc_info=True)
            await callback.answer("Xatolik yuz berdi, qayta urinib ko'ring")


def register_existing_contact_signal_callbacks(dispatcher: Any, *, msg_controller: Any) -> None:
    """CRM signal tasdiqlash/rad etish tugmalarini ro'yxatdan o'tkazadi."""
    from aiogram import F

    @dispatcher.callback_query(F.data.startswith("exsig_confirm:"))
    async def _exsig_confirm(callback: Any) -> None:
        try:
            from src.handlers.msg_pipeline.existing_contact_signal import (
                confirm_existing_contact_signal,
            )

            sender_id_str = callback.data.split(":", 1)[-1]
            await confirm_existing_contact_signal(
                sender_id=int(sender_id_str),
                msg_controller=msg_controller,
            )
            await callback.message.edit_text(
                callback.message.text + "\n\n✅ Tasdiqlandi, CRM yangilanmoqda."
            )
        except Exception:
            logger.error("existing_contact_signal confirm failed", exc_info=True)
            await callback.answer("Xatolik yuz berdi, qayta urinib ko'ring")
        else:
            await callback.answer()

    @dispatcher.callback_query(F.data == "exsig_reject")
    async def _exsig_reject(callback: Any) -> None:
        try:
            await callback.message.edit_text(callback.message.text + "\n\n❌ Rad etildi.")
        except Exception:
            logger.error("existing_contact_signal reject failed", exc_info=True)
        await callback.answer()


def register_salescoach_aiogram_callbacks(dispatcher: Any, *, context: Any) -> None:
    """Route SalesCoach approval decisions through the bot-account head."""
    from aiogram import F
    from src.services.core.telegram_salescoach_runtime import (
        handle_salescoach_callback,
    )

    @dispatcher.callback_query(F.data.startswith(("scapprove:", "screject:")))
    async def _salescoach_callback(callback: Any) -> None:
        try:
            await handle_salescoach_callback(
                str(getattr(callback, "data", "") or ""),
                callback,
                context,
            )
        except Exception:
            logger.error("SalesCoach callback failed", exc_info=True)
            await callback.answer("Xatolik yuz berdi, qayta urinib ko'ring")
