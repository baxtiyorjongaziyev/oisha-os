"""
Telegram notification dispatch and interactive callback action execution.
"""
from __future__ import annotations

import logging
import os
from typing import Any, Iterable, Mapping

from src.services.core.salescoach_runtime.adapters import (
    _parse_id_list,
)

logger = logging.getLogger("TelegramSalesCoachRuntime")


class TelegramSalesCoachNotifier:
    """Owner-only summaries; never includes raw customer messages or phones."""

    def __init__(self, *, bot_runtime: Any, owner_id: int):
        self.bot_runtime = bot_runtime
        self.owner_id = int(owner_id)

    async def send(
        self,
        *,
        analysis_id: int,
        lead_id: int,
        score: int,
        risk: Any,
        next_action: Any,
        recommended_tasks: Iterable[Any],
    ) -> None:
        task_names = [
            str(item.get("type"))
            for item in recommended_tasks
            if isinstance(item, Mapping) and item.get("type")
        ]
        text = (
            "🧭 SalesCoach tasdiqlashi\n"
            f"Lead: {int(lead_id)}\n"
            f"Baho: {max(0, min(int(score), 100))}/100\n"
            f"Risk: {str(risk or 'medium')}\n"
            f"Keyingi qadam: {str(next_action or '-')}\n"
            f"Tasklar: {', '.join(task_names) or '-'}\n"
            f"Analysis ID: {int(analysis_id)}"
        )
        if getattr(self.bot_runtime, "backend", "") == "telethon":
            from telethon import Button

            buttons: Any = [[
                Button.inline("✅ Tasdiqlash", f"scapprove:{int(analysis_id)}"),
                Button.inline("❌ Rad etish", f"screject:{int(analysis_id)}"),
            ]]
        else:
            buttons = [[
                {"text": "✅ Tasdiqlash", "callback_data": f"scapprove:{int(analysis_id)}"},
                {"text": "❌ Rad etish", "callback_data": f"screject:{int(analysis_id)}"},
            ]]
        await self.bot_runtime.send_message(self.owner_id, text, buttons=buttons)

    async def notify_write_failure(self, **payload: Any) -> None:
        await self.bot_runtime.send_message(
            self.owner_id,
            "⚠️ SalesCoach AmoCRM yozuvi tasdiqlanmadi\n"
            f"Lead: {int(payload.get('lead_id') or 0)}\n"
            f"Kod: {str(payload.get('failure_code') or 'unknown')}",
        )


async def handle_salescoach_callback(data: str, event: Any, context: Any) -> bool:
    """Authorize and execute one owner/approver SalesCoach decision."""
    if not data.startswith(("scapprove:", "screject:")):
        return False
    try:
        analysis_id = int(data.split(":", 1)[1])
    except (IndexError, ValueError):
        await event.answer("Noto'g'ri SalesCoach so'rovi")
        return True

    from src.settings import settings

    actor_id = int(
        getattr(event, "sender_id", 0)
        or getattr(getattr(event, "from_user", None), "id", 0)
        or 0
    )
    whitelist = {int(item) for item in (getattr(settings, "WHITELIST_IDS", []) or [])}
    owner_id = int(getattr(settings, "OWNER_ID", 0) or 0)
    approvers = _parse_id_list(os.getenv("SALESCOACH_APPROVER_IDS", ""))
    approvers.update(
        int(item)
        for item in (getattr(settings, "SALESCOACH_APPROVER_IDS", []) or [])
        if int(item) > 0
    )
    approvers.add(owner_id)
    if actor_id not in whitelist or actor_id not in approvers:
        await event.answer("Bu amal uchun ruxsat yo'q")
        return True

    store = getattr(context, "telegram_salescoach_store", None)
    writer = getattr(context, "salescoach_task_writer", None)
    if store is None or writer is None:
        await event.answer("SalesCoach hozir tayyor emas")
        return True
    record = await store.get_analysis(analysis_id)
    if not record or record.get("status") != "pending":
        await event.answer("Bu tavsiya allaqachon ko'rib chiqilgan")
        return True

    if data.startswith("screject:"):
        await store.update_analysis_status(analysis_id, "rejected")
        await event.answer("Rad etildi")
        return True

    if not await store.claim_analysis_approval(analysis_id):
        await event.answer("Bu tavsiya boshqa jarayonda")
        return True
    results = await writer.apply_analysis(
        analysis_id=analysis_id,
        lead_id=int(record["lead_id"]),
        responsible_user_id=int(record.get("manager_id") or 0),
        conversation_fingerprint=str(record["fingerprint"]),
        analysis=record.get("analysis") or {},
        mode="approval",
        approval_actor=str(actor_id),
    )
    if any(item.failure_code == "quiet_hours_deferred" for item in results):
        await store.update_analysis_status(analysis_id, "pending")
        await event.answer("Tungi rejim: 07:00 dan keyin qayta tasdiqlang")
        return True
    failed = any(not item.verified and not item.skipped for item in results)
    await store.update_analysis_status(
        analysis_id,
        "write_failed" if failed else "approved",
    )
    await event.answer("Yozuv tekshirilmadi" if failed else "Tasdiqlandi")
    return True
