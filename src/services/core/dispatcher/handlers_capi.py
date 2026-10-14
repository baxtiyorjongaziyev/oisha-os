"""Telegram bot command and callback handlers for Targetolog CAPI automation."""
from __future__ import annotations

import datetime
import html
import logging
from typing import Any, Callable, Dict

from src.services.core.marketing import capi_platform as platform

logger = logging.getLogger("CapiTelegramHandler")


def format_capi_status_text(snapshot: Dict[str, Any]) -> str:
    """Compile executive CAPI status message for Targetolog and marketing team."""
    cfg = snapshot.get("configuration", {})
    events = snapshot.get("events", [])
    crm_events = snapshot.get("crm_events", [])

    is_configured = bool(cfg.get("configured", False))
    dataset_id = cfg.get("dataset_id") or "Ulanmagan"
    dataset_status = "Ulangan" if is_configured else "Ulanmagan"
    mode = "🧪 Test Events" if cfg.get("mode") == "test" else "🟢 Haqiqiy (Live)"
    enabled = "✅ Faol" if cfg.get("enabled") else "⏸ O'chiq"

    # Status counts across website and CRM
    sent_count = sum(1 for e in events if e.get("status") == "sent")
    sent_count += sum(1 for e in crm_events if e.get("status") == "sent")

    queued_count = sum(1 for e in events if e.get("status") in {"queued", "pending"})
    queued_count += sum(1 for e in crm_events if e.get("status") in {"queued", "pending"})

    failed_count = sum(1 for e in events if e.get("status") in {"failed", "rejected"})
    failed_count += sum(1 for e in crm_events if e.get("status") == "failed")

    # Lead, QualifiedLead, Purchase breakdown
    leads = sum(1 for e in events if e.get("event_name") == "Lead")
    leads += sum(1 for e in crm_events if e.get("event_name") == "Lead")

    qualified = sum(1 for e in events if e.get("event_name") == "QualifiedLead")
    qualified += sum(1 for e in crm_events if e.get("event_name") == "QualifiedLead")

    purchases = sum(1 for e in events if e.get("event_name") == "Purchase")
    purchases += sum(1 for e in crm_events if e.get("event_name") == "Purchase")

    now_tashkent = datetime.datetime.now().strftime("%d.%m.%Y %H:%M")

    lines = [
        "🎯 <b>META CONVERSIONS API (CAPI) — TARGETOLOG PANELI</b>",
        "━━━━━━━━━━━━━━━━━━━━━━━━━━",
        f"📡 <b>Dataset:</b> <code>{html.escape(str(dataset_id))}</code> ({dataset_status})",
        f"⚡ <b>Rejim:</b> {mode} ({enabled})",
        "🔄 <b>Avtomatlashtirish:</b> 24/7 Faol (har 30s navbat tekshiriladi)",
        f"🌐 <b>Sayt Ingest:</b> {'✅ Sozlangan' if cfg.get('ingest_configured') else '⚠️ Ulanmagan'}",
        "",
        "📊 <b>HODISALAR STATISTIKASI (OXIRGI QAYDLAR):</b>",
        f"• 🟢 <b>Meta qabul qilgan (Sent):</b> {sent_count} ta",
        f"• ⏳ <b>Yuborish navbatida (Queued):</b> {queued_count} ta",
        f"• ⚠️ <b>Xatoliklar (Failed):</b> {failed_count} ta",
        "",
        "🎯 <b>SAVDO VORONKASI SIGNALLARI:</b>",
        f"• 📋 <b>Lead (Sayt / Lead Ads):</b> {leads} ta",
        f"• 🎯 <b>QualifiedLead (Sifatli lid):</b> {qualified} ta",
        f"• 💰 <b>Purchase (Sotuv yopildi):</b> {purchases} ta",
        "",
        f"🕒 <i>Holat vaqti: {now_tashkent} (Toshkent)</i>",
        "━━━━━━━━━━━━━━━━━━━━━━━━━━",
        "💡 <i>Quyidagi tugmalar orqali navbatni yuborish yoki jurnallarni ko'rishingiz mumkin:</i>",
    ]
    return "\n".join(lines)


def build_capi_keyboard() -> Any:
    """Build interactive inline keyboard for Targetolog CAPI control."""
    from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup

    buttons = [
        [
            InlineKeyboardButton(text="🔄 Navbatni yuborish (Dispatch)", callback_data="capi:dispatch"),
            InlineKeyboardButton(text="📊 So'nggi eventlar", callback_data="capi:events"),
        ],
        [
            InlineKeyboardButton(text="🎬 Reklama Kreativlari", callback_data="capi:creatives"),
            InlineKeyboardButton(text="🌐 CAPI Web Konsol", url="https://oisha.jonbranding.uz/api/marketing/capi/console"),
        ],
    ]
    return InlineKeyboardMarkup(inline_keyboard=buttons)


async def handle_aiogram_capi(
    message: Any,
    *,
    is_admin: Callable[[int], bool],
) -> None:
    """Handle /capi, /targetolog, /target commands."""
    sender_id = int(getattr(getattr(message, "from_user", None), "id", 0) or 0)
    if not is_admin(sender_id):
        await message.answer("⚠️ Ushbu buyruq faqat Targetolog va Adminlar uchun ochiq.")
        return

    try:
        snapshot = await platform.snapshot()
        text = format_capi_status_text(snapshot)
        kb = build_capi_keyboard()
        await message.answer(text, reply_markup=kb, parse_mode="HTML")
    except Exception as exc:
        logger.error("[CAPI BOT] Status compilation error: %s", exc, exc_info=True)
        await message.answer(f"❌ CAPI holatini olishda xatolik yuz berdi: {html.escape(str(exc))}")


async def handle_aiogram_capi_callback(
    query: Any,
    *,
    is_admin: Callable[[int], bool],
) -> None:
    """Handle interactive inline keyboard callbacks for CAPI control."""
    sender_id = int(getattr(getattr(query, "from_user", None), "id", 0) or 0)
    if not is_admin(sender_id):
        await query.answer("⚠️ Ruxsat etilmagan.", show_alert=True)
        return

    data = getattr(query, "data", "") or ""

    if data == "capi:dispatch":
        try:
            results = await platform.dispatch_due()
            sent_count = sum(1 for r in results if r.get("status") == "sent")
            await query.answer(
                f"✅ Navbat tekshirildi: {sent_count} ta yangi event Meta'ga yetkazildi.",
                show_alert=True,
            )
            # Update the message with fresh numbers
            snapshot = await platform.snapshot()
            text = format_capi_status_text(snapshot)
            kb = build_capi_keyboard()
            if getattr(query, "message", None):
                await query.message.edit_text(text, reply_markup=kb, parse_mode="HTML")
        except Exception as exc:
            logger.error("[CAPI BOT] Dispatch error: %s", exc)
            await query.answer(f"❌ Xatolik: {exc}", show_alert=True)

    elif data == "capi:events":
        try:
            snapshot = await platform.snapshot()
            events = (snapshot.get("events", []) + snapshot.get("crm_events", []))[:8]
            if not events:
                await query.answer("ℹ️ Hozircha hodisalar mavjud emas.", show_alert=True)
                return

            lines = ["📋 <b>OXIRGI CAPI HODISALARI:</b>\n"]
            for ev in events:
                name = ev.get("event_name", "Unknown")
                status = ev.get("status", "unknown")
                status_icon = "🟢" if status == "sent" else ("⏳" if status in {"queued", "pending"} else "⚠️")
                ev_id = ev.get("event_id") or ev.get("leadgen_id") or "Noma'lum"
                lines.append(f"{status_icon} <b>{name}</b> ({status}) — <code>{ev_id}</code>")

            await query.answer()
            if getattr(query, "message", None):
                await query.message.answer("\n".join(lines), parse_mode="HTML")
        except Exception as exc:
            logger.error("[CAPI BOT] Events log error: %s", exc)
            await query.answer(f"❌ Xatolik: {exc}", show_alert=True)

    elif data == "capi:creatives":
        try:
            from src.services.core.dispatcher.handlers_admin import handle_aiogram_kreativlar
            if getattr(query, "message", None):
                await handle_aiogram_kreativlar(query.message, is_admin=is_admin)
            await query.answer()
        except Exception as exc:
            logger.error("[CAPI BOT] Creatives redirect error: %s", exc)
            await query.answer(f"❌ Xatolik: {exc}", show_alert=True)
