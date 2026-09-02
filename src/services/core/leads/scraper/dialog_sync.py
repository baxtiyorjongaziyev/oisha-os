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
        logger.info(
            f"[SCRAPER] Shaxsiy suhbatlar (DM) tahlili boshlandi (Limit: {limit})... 👸🛡️"
        )

        sync_count = 0
        from src.services.core.auto_lead_agent import AutoLeadAgent
        from src.settings import settings

        auto_lead_agent = AutoLeadAgent(
            api_key=settings.GEMINI_API_KEY.get_secret_value()
        )

        async for dialog in client.iter_dialogs(limit=limit):
            if not dialog.is_user or dialog.entity.bot:
                continue

            user_id = dialog.id
            if await self.db.is_crm_synced(user_id):
                continue

            # 1. Get last messages
            messages = await client.get_messages(dialog.entity, limit=20)
            chat_text = "\n".join(
                [f"{'Bot' if m.out else 'User'}: {m.text}" for m in messages if m.text]
            )

            if not chat_text:
                continue

            # 2. AI Lead Qualification
            is_lead, lead_details = await auto_lead_agent.qualify_chat(chat_text)
            intent = lead_details.get("intent_category", "SPAM")

            # 3. Notification Logic - Now broad and proactive (Wow Factor)
            # Notify for everything interesting, even if not a formal 'Lead' yet
            INTERESTING_INTENTS = [
                "HOT_LEAD",
                "POTENTIAL",
                "VIP_CLIENT",
                "PARTNER",
                "NETWORKING",
                "SUPPORT",
            ]

            if is_lead or intent in INTERESTING_INTENTS:
                logger.info(f"[DM SYNC] Interaction found ({intent}): {dialog.name}")
                phone = lead_details.get("phone") or getattr(
                    dialog.entity, "phone", "Unknown"
                )

                # 3a. Save formally recognized leads to CRM
                if is_lead and self.amocrm:
                    try:
                        note_text = (
                            f"AI Summary: {lead_details.get('summary')}\n"
                            f"Intent: {intent}\n"
                            f"User: @{getattr(dialog.entity, 'username', 'N/A')}"
                        )
                        if hasattr(self.amocrm, "create_lead"):
                            await self.amocrm.create_lead(
                                name=f"DM Lead: {dialog.name}",
                                price=0,
                                phone=phone,
                                note=note_text,
                            )
                        elif hasattr(self.amocrm, "ensure_lead"):
                            await self.amocrm.ensure_lead(
                                name=f"DM Lead: {dialog.name}",
                                phone=phone,
                                note=note_text,
                            )
                        elif self.message_controller and getattr(
                            self.message_controller, "crm", None
                        ):
                            await self.message_controller.crm.sync_lead(
                                user_id=user_id,
                                name=f"DM Lead: {dialog.name}",
                                phone=phone,
                                note=note_text,
                            )
                        else:
                            raise AttributeError(
                                "No supported CRM lead creation method found"
                            )
                        await self.db.set_crm_synced(user_id)
                        sync_count += 1
                        logger.info(f"[DM SYNC] AmoCRMga qo'shildi: {dialog.name}")
                    except Exception as e:
                        logger.error(f"[DM SYNC ERROR] AmoCRM save: {e}")

                # 3b. [NEW] Autonomous Proactive Negotiation (Phase 3)
                # If it's a lead or potential interaction, and Oisha hasn't responded yet, initiate outreach.
                autonomous_outreach_enabled = os.getenv(
                    "ENABLE_AUTONOMOUS_OUTREACH", ""
                ).strip().lower() in {"1", "true", "yes", "on"} and automatic_customer_send_allowed("lead_outreach")
                if (
                    autonomous_outreach_enabled
                    and self.message_controller
                    and (is_lead or intent in ["HOT_LEAD", "POTENTIAL", "VIP_CLIENT"])
                ):
                    try:
                        # Check if the last message was from us to avoid double-responding
                        last_msg = messages[0] if messages else None
                        if last_msg and not last_msg.out:
                            logger.info(
                                f"👸 [AUTONOMOUS] Initiating negotiation outreach for {dialog.name}..."
                            )

                            # Get last user message text
                            user_text = last_msg.text or ""

                            # Generate autonomous response using SalesAgent (via Controller)
                            # We provide context that this is an autonomous sync trigger
                            ai_response = await self.message_controller.get_response(
                                user_id=user_id, text=user_text, message_obj=last_msg
                            )

                            if ai_response:
                                await client.send_message(dialog.entity, ai_response)
                                logger.info(
                                    f"✅ [AUTONOMOUS] Response sent to {dialog.name}"
                                )

                                # Mark as responded in DB to prevent loops (optional, as get_messages check exists)
                                # await self.db.set_negotiation_active(user_id, True)
                    except Exception as auto_ex:
                        logger.error(
                            f"👸 [AUTONOMOUS ERROR] Failed to respond to {dialog.name}: {auto_ex}"
                        )

                # 4. Proactive Real-time Notification in Telegram (The 'Wow' Factor)
                if self.notify_callback:
                    try:
                        intent_emojis = {
                            "HOT_LEAD": "🔥 HOT LEAD",
                            "POTENTIAL": "🌱 POTENTIAL",
                            "VIP_CLIENT": "👑 VIP CLIENT",
                            "PARTNER": "🤝 PARTNER",
                            "NETWORKING": "☕️ NETWORKING",
                            "SUPPORT": "🛠 SUPPORT",
                        }
                        emoji = intent_emojis.get(intent, "📢 NEW INTERACTION")

                        msg = (
                            f"👸 **{emoji} aniqlandi!**\n\n"
                            f"👤 **Mijoz:** {dialog.name}\n"
                            f"📞 **Tel:** {phone}\n"
                            f"📝 **Xulosa:** {lead_details.get('summary')}\n"
                            f"💡 **Oisha Coach Maslahati:** _{lead_details.get('coaching_tip', 'Suhbatni davom ettiring.')}_\n\n"
                            f"{'✅ AmoCRM-ga saqlandi.' if is_lead else '👁️ Oisha kuzatmoqda (Hali lead emas).'} 👸🛡️"
                        )
                        await self.notify_callback(msg)
                    except Exception as n_ex:
                        logger.error(f"[DM SYNC] Notification error: {n_ex}")
                    except Exception as e:
                        logger.error(f"[DM SYNC ERROR] AmoCRM save: {e}")

        logger.info(f"[DM SYNC] Yakunlandi. Jami: {sync_count}")
        return sync_count

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

        auto_lead_agent = AutoLeadAgent(
            api_key=settings.GEMINI_API_KEY.get_secret_value()
        )

        target_group = team_group_id or settings.TEAM_GROUP_ID or settings.CRM_GROUP_ID
        target_topic = topic_id or settings.TOPIC_CRM_ID or settings.CRM_TOPIC_ID
        send_client = bot_client or client

        if not target_group:
            logger.error("[HUNT 2026] TEAM_GROUP_ID yoki CRM_GROUP_ID sozlanmagan!")
            return 0

        since_date = datetime(2026, 1, 1, tzinfo=timezone.utc)
        found_leads = []
        scanned = 0

        async for dialog in client.iter_dialogs(limit=limit):
            if not dialog.is_user:
                continue
            if getattr(dialog.entity, "bot", False):
                continue

            scanned += 1

            messages = await client.get_messages(
                dialog.entity, limit=30, offset_date=None
            )

            relevant_msgs = [
                m for m in messages
                if m.text and m.date and m.date >= since_date
            ]

            if not relevant_msgs:
                continue

            chat_text = "\n".join(
                [
                    f"{'Me' if m.out else 'User'}: {m.text}"
                    for m in relevant_msgs[:25]
                ]
            )

            try:
                is_lead, lead_details = await auto_lead_agent.qualify_chat(chat_text)
            except Exception as e:
                logger.warning(f"[HUNT 2026] AI error for {dialog.name}: {e}")
                await asyncio.sleep(2)
                continue

            intent = lead_details.get("intent_category", "SPAM")
            confidence = lead_details.get("confidence_score", 0)

            QUALITY_INTENTS = ["HOT_LEAD", "POTENTIAL", "VIP_CLIENT", "PARTNER"]
            if not (is_lead or intent in QUALITY_INTENTS):
                continue
            if confidence < 0.5 and not is_lead:
                continue

            phone = lead_details.get("phone") or getattr(dialog.entity, "phone", None)
            username = getattr(dialog.entity, "username", None)

            lead_info = {
                "name": dialog.name,
                "username": username,
                "phone": phone,
                "intent": intent,
                "confidence": confidence,
                "summary": lead_details.get("summary", ""),
                "needs": lead_details.get("needs", ""),
                "business": lead_details.get("business", ""),
                "coaching_tip": lead_details.get("coaching_tip", ""),
            }
            found_leads.append(lead_info)

            await asyncio.sleep(1.5)

        logger.info(
            f"[HUNT 2026] Skanerlash tugadi. {scanned} dialog tekshirildi, {len(found_leads)} sifatli lead topildi."
        )

        if not found_leads:
            summary_msg = "👸 **HUNT 2026 natijasi:**\n\n❌ Sifatli lead topilmadi."
            try:
                await send_client.send_message(
                    target_group, summary_msg, reply_to=target_topic
                )
            except Exception as e:
                logger.error(f"[HUNT 2026] Send error: {e}")
            return 0

        intent_emojis = {
            "HOT_LEAD": "🔥",
            "POTENTIAL": "🌱",
            "VIP_CLIENT": "👑",
            "PARTNER": "🤝",
        }

        header = (
            f"👸 **HUNT 2026 — {len(found_leads)} ta sifatli lead topildi!**\n"
            f"📊 Jami {scanned} ta dialog skanerlanadi\n"
            f"{'━' * 30}\n\n"
        )

        batch_size = 5
        for i in range(0, len(found_leads), batch_size):
            batch = found_leads[i : i + batch_size]
            msg_parts = []

            if i == 0:
                msg_parts.append(header)

            for idx, lead in enumerate(batch, start=i + 1):
                emoji = intent_emojis.get(lead["intent"], "📢")
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
                entry += "\n"
                msg_parts.append(entry)

            full_msg = "".join(msg_parts)

            try:
                await send_client.send_message(
                    target_group, full_msg, reply_to=target_topic
                )
            except Exception as e:
                logger.error(f"[HUNT 2026] Batch send error: {e}")

            await asyncio.sleep(1)

        logger.info(f"[HUNT 2026] Team CRM topicga {len(found_leads)} lead yuborildi.")
        return len(found_leads)
