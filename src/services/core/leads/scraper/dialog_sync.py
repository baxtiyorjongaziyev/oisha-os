"""
Telegram private dialog scraping and hunter 2026 leads extraction mixin.
"""
from __future__ import annotations

import asyncio
import logging
import os
from datetime import datetime, timezone
from telethon import TelegramClient

from src.services.core.customer_outbound_policy import automatic_customer_send_allowed
from src.settings import settings

logger = logging.getLogger("LeadScraper")


class DialogSyncMixin:
    """Handles private conversation scraping and 2026 deal creation."""

    async def sync_private_dialogs(self, client: TelegramClient, limit: int = 100):
        """Oxirgi shaxsiy suhbatlardan (DM) lidlarni qidirib topish va AmoCRMga qo'shish."""
        from src.services.core.auto_lead_agent import AutoLeadAgent

        logger.info(f"[SCRAPER] Shaxsiy suhbatlar (DM) tahlili boshlandi (Limit: {limit})... 👸🛡️")
        agent = AutoLeadAgent(api_key=settings.GEMINI_API_KEY.get_secret_value())
        sync_count = 0
        async for dialog in client.iter_dialogs(limit=limit):
            if not dialog.is_user or dialog.entity.bot:
                continue
            if await self.db.is_crm_synced(dialog.id):
                continue
            if await self._dm_process_dialog(client, dialog, agent):
                sync_count += 1
        logger.info(f"[DM SYNC] Yakunlandi. Jami: {sync_count}")
        return sync_count

    async def _dm_process_dialog(self, client, dialog, agent) -> bool:
        messages = await client.get_messages(dialog.entity, limit=20)
        chat_text = "\n".join(f"{'Bot' if m.out else 'User'}: {m.text}" for m in messages if m.text)
        if not chat_text:
            return False
        is_lead, details = await agent.qualify_chat(chat_text)
        intent = details.get("intent_category", "SPAM")
        if not (is_lead or intent in DM_INTERESTING_INTENTS):
            return False
        logger.info(f"[DM SYNC] Interaction found ({intent}): {dialog.name}")
        phone = details.get("phone") or getattr(dialog.entity, "phone", "Unknown")
        synced = False
        if is_lead and self.amocrm:
            synced = await self._dm_save_to_crm(dialog, phone, intent, details)
        if is_lead or intent in DM_OUTREACH_INTENTS:
            await self._dm_autonomous_outreach(client, dialog, messages)
        await self._dm_notify(dialog, phone, intent, details, is_lead)
        return synced

    async def _dm_save_to_crm(self, dialog, phone, intent, details) -> bool:
        name = f"DM Lead: {dialog.name}"
        note = (
            f"AI Summary: {details.get('summary')}\n"
            f"Intent: {intent}\n"
            f"User: @{getattr(dialog.entity, 'username', 'N/A')}"
        )
        try:
            if hasattr(self.amocrm, "create_lead"):
                await self.amocrm.create_lead(name=name, price=0, phone=phone, note=note)
            elif hasattr(self.amocrm, "ensure_lead"):
                await self.amocrm.ensure_lead(name=name, phone=phone, note=note)
            elif self.message_controller and getattr(self.message_controller, "crm", None):
                await self.message_controller.crm.sync_lead(
                    user_id=dialog.id, name=name, phone=phone, note=note
                )
            else:
                raise AttributeError("No supported CRM lead creation method found")
            await self.db.set_crm_synced(dialog.id)
            logger.info(f"[DM SYNC] AmoCRMga qo'shildi: {dialog.name}")
            return True
        except Exception as e:
            logger.error(f"[DM SYNC ERROR] AmoCRM save: {e}")
            return False

    async def _dm_autonomous_outreach(self, client, dialog, messages) -> None:
        if not (_autonomous_outreach_enabled() and self.message_controller):
            return
        last_msg = messages[0] if messages else None
        if not last_msg or last_msg.out:
            return
        try:
            logger.info(f"👸 [AUTONOMOUS] Initiating negotiation outreach for {dialog.name}...")
            reply = await self.message_controller.get_response(
                user_id=dialog.id, text=last_msg.text or "", message_obj=last_msg
            )
            if reply:
                await client.send_message(dialog.entity, reply)
                logger.info(f"✅ [AUTONOMOUS] Response sent to {dialog.name}")
        except Exception as auto_ex:
            logger.error(f"👸 [AUTONOMOUS ERROR] Failed to respond to {dialog.name}: {auto_ex}")

    async def _dm_notify(self, dialog, phone, intent, details, is_lead) -> None:
        if not self.notify_callback:
            return
        label = DM_INTENT_LABELS.get(intent, "📢 NEW INTERACTION")
        tip = details.get("coaching_tip", "Suhbatni davom ettiring.")
        status = "✅ AmoCRM-ga saqlandi." if is_lead else "👁️ Oisha kuzatmoqda (Hali lead emas)."
        msg = (
            f"👸 **{label} aniqlandi!**\n\n"
            f"👤 **Mijoz:** {dialog.name}\n"
            f"📞 **Tel:** {phone}\n"
            f"📝 **Xulosa:** {details.get('summary')}\n"
            f"💡 **Oisha Coach Maslahati:** _{tip}_\n\n"
            f"{status} 👸🛡️"
        )
        try:
            await self.notify_callback(msg)
        except Exception as n_ex:
            logger.error(f"[DM SYNC] Notification error: {n_ex}")

    async def hunt_2026_leads(
        self,
        client: TelegramClient,
        bot_client: TelegramClient = None,
        team_group_id: int = None,
        topic_id: int = None,
        limit: int = 500,
    ):
        """2026-yildagi barcha shaxsiy yozishmalarni skanerlash va sifatli leadlarni Team CRM topicga yuborish."""
        from src.services.core.auto_lead_agent import AutoLeadAgent

        logger.info("[HUNT 2026] Shaxsiy chatlarni skanerlash boshlandi...")
        target_group = team_group_id or settings.TEAM_GROUP_ID or settings.CRM_GROUP_ID
        target_topic = topic_id or settings.TOPIC_CRM_ID or settings.CRM_TOPIC_ID
        send_client = bot_client or client
        if not target_group:
            logger.error("[HUNT 2026] TEAM_GROUP_ID yoki CRM_GROUP_ID sozlanmagan!")
            return 0

        agent = AutoLeadAgent(api_key=settings.GEMINI_API_KEY.get_secret_value())
        found_leads, scanned = await self._hunt_scan_dialogs(client, agent, limit)
        logger.info(
            f"[HUNT 2026] Skanerlash tugadi. {scanned} dialog tekshirildi, {len(found_leads)} sifatli lead topildi."
        )
        await self._hunt_report(send_client, target_group, target_topic, found_leads, scanned)
        if found_leads:
            logger.info(f"[HUNT 2026] Team CRM topicga {len(found_leads)} lead yuborildi.")
        return len(found_leads)

    async def _hunt_scan_dialogs(self, client, agent, limit):
        found_leads, scanned = [], 0
        async for dialog in client.iter_dialogs(limit=limit):
            if not dialog.is_user or getattr(dialog.entity, "bot", False):
                continue
            scanned += 1
            chat_text = await _hunt_chat_text(client, dialog)
            if not chat_text:
                continue
            try:
                is_lead, details = await agent.qualify_chat(chat_text)
            except Exception as e:
                logger.warning(f"[HUNT 2026] AI error for {dialog.name}: {e}")
                await asyncio.sleep(2)
                continue
            lead = _hunt_build_lead(dialog, is_lead, details)
            if lead:
                found_leads.append(lead)
                await asyncio.sleep(1.5)
        return found_leads, scanned

    async def _hunt_report(self, send_client, group, topic, found_leads, scanned):
        if not found_leads:
            messages = ["👸 **HUNT 2026 natijasi:**\n\n❌ Sifatli lead topilmadi."]
        else:
            messages = _hunt_format_batches(found_leads, scanned)
        for msg in messages:
            try:
                await send_client.send_message(group, msg, reply_to=topic)
            except Exception as e:
                logger.error(f"[HUNT 2026] Send error: {e}")
            if found_leads:
                await asyncio.sleep(1)


HUNT_SINCE = datetime(2026, 1, 1, tzinfo=timezone.utc)
HUNT_QUALITY_INTENTS = {"HOT_LEAD", "POTENTIAL", "VIP_CLIENT", "PARTNER"}
HUNT_INTENT_EMOJIS = {"HOT_LEAD": "🔥", "POTENTIAL": "🌱", "VIP_CLIENT": "👑", "PARTNER": "🤝"}
HUNT_BATCH_SIZE = 5


async def _hunt_chat_text(client, dialog) -> str:
    messages = await client.get_messages(dialog.entity, limit=30, offset_date=None)
    relevant = [m for m in messages if m.text and m.date and m.date >= HUNT_SINCE]
    return "\n".join(f"{'Me' if m.out else 'User'}: {m.text}" for m in relevant[:25])


def _hunt_build_lead(dialog, is_lead: bool, details: dict) -> dict | None:
    intent = details.get("intent_category", "SPAM")
    confidence = details.get("confidence_score", 0)
    if not (is_lead or intent in HUNT_QUALITY_INTENTS):
        return None
    if confidence < 0.5 and not is_lead:
        return None
    return {
        "name": dialog.name,
        "username": getattr(dialog.entity, "username", None),
        "phone": details.get("phone") or getattr(dialog.entity, "phone", None),
        "intent": intent,
        "confidence": confidence,
        "summary": details.get("summary", ""),
        "needs": details.get("needs", ""),
        "business": details.get("business", ""),
        "coaching_tip": details.get("coaching_tip", ""),
    }


def _hunt_format_entry(idx: int, lead: dict) -> str:
    emoji = HUNT_INTENT_EMOJIS.get(lead["intent"], "📢")
    contact = f"@{lead['username']}" if lead["username"] else (lead["phone"] or "N/A")
    entry = (
        f"**{idx}. {emoji} {lead['name']}**\n"
        f"   📞 {contact}\n"
        f"   🏷 {lead['intent']} (confidence: {lead['confidence']:.0%})\n"
        f"   📝 {lead['summary']}\n"
    )
    if lead["needs"]:
        entry += f"   🎯 Ehtiyoj: {lead['needs']}\n"
    if lead["coaching_tip"]:
        entry += f"   💡 Maslahat: {lead['coaching_tip']}\n"
    return entry + "\n"


def _hunt_format_batches(found_leads: list[dict], scanned: int) -> list[str]:
    header = (
        f"👸 **HUNT 2026 — {len(found_leads)} ta sifatli lead topildi!**\n"
        f"📊 Jami {scanned} ta dialog skanerlanadi\n"
        f"{'━' * 30}\n\n"
    )
    batches = []
    for i in range(0, len(found_leads), HUNT_BATCH_SIZE):
        chunk = found_leads[i : i + HUNT_BATCH_SIZE]
        body = "".join(_hunt_format_entry(idx, lead) for idx, lead in enumerate(chunk, start=i + 1))
        batches.append((header if i == 0 else "") + body)
    return batches


DM_INTERESTING_INTENTS = {"HOT_LEAD", "POTENTIAL", "VIP_CLIENT", "PARTNER", "NETWORKING", "SUPPORT"}
DM_OUTREACH_INTENTS = {"HOT_LEAD", "POTENTIAL", "VIP_CLIENT"}
DM_INTENT_LABELS = {
    "HOT_LEAD": "🔥 HOT LEAD",
    "POTENTIAL": "🌱 POTENTIAL",
    "VIP_CLIENT": "👑 VIP CLIENT",
    "PARTNER": "🤝 PARTNER",
    "NETWORKING": "☕️ NETWORKING",
    "SUPPORT": "🛠 SUPPORT",
}


def _autonomous_outreach_enabled() -> bool:
    flag = os.getenv("ENABLE_AUTONOMOUS_OUTREACH", "").strip().lower() in {"1", "true", "yes", "on"}
    return flag and automatic_customer_send_allowed("lead_outreach")
