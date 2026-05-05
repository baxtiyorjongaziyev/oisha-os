import logging
import asyncio
import time
from src.database import Database
from src.services.core.amocrm_sync import AmoCRMSync
from src.services.core.auto_lead_agent import AutoLeadAgent
from telethon import Button

logger = logging.getLogger(__name__)


class UnansweredMonitor:
    def __init__(
        self, amocrm: AmoCRMSync, bot_client, db: Database, auto_lead: AutoLeadAgent
    ):
        self.amocrm = amocrm
        self.bot_client = bot_client
        self.db = db
        self.auto_lead = auto_lead

    async def start_monitoring(self, interval_seconds: int = 1800):
        """Har X soniyada o'qilmagan xabarlarni tekshiradi."""
        logger.info(
            f"👸 [MONITOR] Unanswered messages monitor started with interval {interval_seconds}s"
        )
        while True:
            try:
                await self.check_and_notify()
            except Exception as e:
                logger.error(f"👸 [MONITOR] Error in monitor loop: {e}", exc_info=True)
            await asyncio.sleep(interval_seconds)

    async def check_and_notify(self):
        """amoCRM-dan o'qilmagan xabarlarni oladi va menejerlarni bezovta qiladi."""
        logger.info("👸 [MONITOR] Scanning for unanswered messages...")

        # 1. Get unread chats from amoCRM (v4 doesn't have a direct 'unread' API easily,
        # so we check leads in 'Incoming' or check chats if available via Wazzup/Chat API)
        # For now, let's look at leads updated more than 20 mins ago but still in initial stages

        leads = await self.amocrm.get_leads(
            filter_status=[142, 143]
        )  # Example statuses for New/Incoming
        if not leads:
            return

        for lead in leads:
            lead_id = lead["id"]
            last_msg_time = lead.get("updated_at", 0)
            now = int(time.time())

            # Agar 20 daqiqadan (1200s) oshgan bo'lsa
            if (now - last_msg_time) > 1200:
                # Check if already notified to avoid spam
                job_key = f"notified_unread_{lead_id}_{last_msg_time}"
                if await self.db.get_state(job_key) == "done":
                    continue

                # 2. Get lead notes/last messages to generate AI draft
                notes = await self.amocrm.get_lead_notes(lead_id)
                last_text = "Mijoz so'rovi (CRM-da ko'ring)"
                if notes:
                    last_text = notes[0].get("params", {}).get("text", last_text)

                # 3. Generate AI Draft
                prompt = f"Mijoz quyidagicha yozgan: '{last_text}'. Unga samimiy, yordam beruvchi va qisqa javob yozing. Sotuvni davom ettiring."
                draft_reply = await self.auto_lead.generate_reply(last_text, prompt)

                # 4. Notify Responsible Manager
                manager_id = lead.get("responsible_user_id")
                # Map amoCRM user_id to Telegram ID (This requires a mapping table in DB)
                tg_manager_id = await self.db.get_state(f"amocrm_to_tg_{manager_id}")

                if not tg_manager_id:
                    # Fallback to Admin/Owner or Team Group
                    from src.settings import settings

                    target_chat = settings.CRM_TOPIC_ID or settings.OWNER_ID
                else:
                    target_chat = int(tg_manager_id)

                msg = (
                    f"⏳ **MIJOZ JAVOB KUTYAPTI!** (20+ daqiqa)\n"
                    f"👤 **Lid:** {lead['name']}\n"
                    f"📝 **Mijoz xabari:** _{last_text[:100]}..._\n\n"
                    f"👸 **Oisha Tavsiyasi:**\n`{draft_reply}`"
                )

                buttons = [
                    [Button.inline("✅ Yuborish (Draft)", f"send_draft:{lead_id}")],
                    [
                        Button.url(
                            "🌐 amoCRM-da ochish",
                            f"https://{self.amocrm.subdomain}.amocrm.ru/leads/detail/{lead_id}",
                        )
                    ],
                ]

                try:
                    await self.bot_client.send_message(
                        target_chat, msg, buttons=buttons, parse_mode="markdown"
                    )
                    await self.db.set_state(job_key, "done")
                except Exception as e:
                    logger.error(f"Failed to notify manager for lead {lead_id}: {e}")

    async def send_draft_to_crm(self, lead_id: int, text: str):
        """Menejer tasdiqlagan xabarni amoCRM-ga (Wazzup orqali) yuboradi."""
        # Wazzup API or amoCRM message API call here
        return await self.amocrm.add_lead_note(
            lead_id, f"👸 Oisha (Menejer nomidan): {text}"
        )
