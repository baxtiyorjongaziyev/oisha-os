"""Airtable Transaction Approval Callbacks for Telegram (@jonairobot / Aiogram).
Handles:
  at_app:<record_id> -> Updates Airtable Tranzaksiyalar record Holat="Tasdiqlangan"
  at_rej:<record_id> -> Updates Airtable Tranzaksiyalar record Holat="Bekor qilingan"
"""
import asyncio
import html
import logging
from typing import Any
import httpx
from aiogram import F

from src.services.core.airtable_config import airtable_request_headers
from src.settings import settings
from src.time_utils import get_local_now

logger = logging.getLogger(__name__)

AIRTABLE_API_BASE = "https://api.airtable.com/v0"
DEFAULT_BASE_ID = "app8xoyx1XCumYFXV"
DEFAULT_TABLE_ID = "tblrqxqIzyrvg7XpQ"  # Tranzaksiyalar table


def _get_airtable_headers() -> dict[str, str]:
    return airtable_request_headers()


async def update_airtable_transaction_status(record_id: str, new_status: str) -> bool:
    base_id = getattr(settings, "AIRTABLE_BASE_ID", None) or DEFAULT_BASE_ID
    url = f"{AIRTABLE_API_BASE}/{base_id}/{DEFAULT_TABLE_ID}/{record_id}"
    try:
        headers = _get_airtable_headers()
        payload = {"fields": {"Holat": new_status}}
        async with httpx.AsyncClient(timeout=10.0) as client:
            resp = await client.patch(url, headers=headers, json=payload)
            if resp.status_code in (200, 201):
                logger.info("[AIRTABLE] Record %s status updated to %s", record_id, new_status)
                return True
            else:
                logger.error("[AIRTABLE] Failed update %s: HTTP %s %s", record_id, resp.status_code, resp.text)
                return False
    except Exception as exc:
        logger.error("[AIRTABLE] Exception updating %s: %s", record_id, exc)
        return False


def _report_pnl_sync_result(task: asyncio.Task[dict[str, Any]]) -> None:
    try:
        task.result()
    except asyncio.CancelledError:
        logger.warning("[PNL_SYNC] Background sync was cancelled")
    except Exception:
        logger.exception("[PNL_SYNC] Background sync failed")


def register_airtable_approval_callbacks(dispatcher: Any) -> None:
    @dispatcher.callback_query(F.data.startswith(("at_app:", "at_rej:")))
    async def _airtable_approval_callback(callback: Any) -> None:
        data = str(getattr(callback, "data", "") or "")
        parts = data.split(":", 1)
        if len(parts) != 2:
            await callback.answer("⚠️ Noto'g'ri so'rov formati.")
            return

        action, record_id = parts[0], parts[1]
        user = getattr(callback, "from_user", None)
        user_name = (
            f"@{user.username}"
            if (user and getattr(user, "username", None))
            else (getattr(user, "full_name", None) or "Moliyachi")
        )
        now_str = get_local_now().strftime("%d.%m.%Y %H:%M")

        if action == "at_app":
            success = await update_airtable_transaction_status(record_id, "Tasdiqlangan")
            if success:
                # Trigger real-time P&L recalculation
                try:
                    from src.services.core.finance.pnl_sync import sync_monthly_pnl

                    task = asyncio.create_task(sync_monthly_pnl())
                    task.add_done_callback(_report_pnl_sync_result)
                except Exception as exc:
                    logger.warning("P&L sync background task warning: %s", exc)

                await callback.answer("✅ Airtable'da 'Tasdiqlangan' holatiga o'tkazildi!", show_alert=True)
                msg = getattr(callback, "message", None)
                if msg:
                    orig_text = getattr(msg, "html_text", None) or getattr(msg, "text", "")
                    clean_text = orig_text.split("⏳ Holat:")[0].split("⏳ <b>Holat:")[0].strip()
                    updated_text = (
                        f"{clean_text}\n\n"
                        f"✅ <b>Tasdiqlandi</b>\n"
                        f"👤 <b>Tasdiqladi:</b> {html.escape(user_name)}\n"
                        f"🕒 <b>Vaqt:</b> {now_str}"
                    )
                    try:
                        await msg.edit_text(updated_text, parse_mode="HTML", reply_markup=None)
                    except Exception as e:
                        logger.debug("Edit message error: %s", e)
            else:
                await callback.answer("❌ Airtable yangilanmadi, qayta urinib ko'ring.", show_alert=True)

        elif action == "at_rej":
            success = await update_airtable_transaction_status(record_id, "Bekor qilingan")
            if success:
                await callback.answer("❌ Airtable'da 'Bekor qilingan' holatiga o'tkazildi!", show_alert=True)
                msg = getattr(callback, "message", None)
                if msg:
                    orig_text = getattr(msg, "html_text", None) or getattr(msg, "text", "")
                    clean_text = orig_text.split("⏳ Holat:")[0].split("⏳ <b>Holat:")[0].strip()
                    updated_text = (
                        f"{clean_text}\n\n"
                        f"❌ <b>Bekor qilindi</b>\n"
                        f"👤 <b>Bekor qildi:</b> {html.escape(user_name)}\n"
                        f"🕒 <b>Vaqt:</b> {now_str}"
                    )
                    try:
                        await msg.edit_text(updated_text, parse_mode="HTML", reply_markup=None)
                    except Exception as e:
                        logger.debug("Edit message error: %s", e)
            else:
                await callback.answer("❌ Airtable yangilanmadi, qayta urinib ko'ring.", show_alert=True)
