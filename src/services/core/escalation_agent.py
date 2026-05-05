import logging
import datetime
from typing import Dict, Any
from src.database import Database
from src import config

logger = logging.getLogger(__name__)


class EscalationAgent:
    """Oisha yuborgan xabarlarga javob qaytarilganini nazorat qiluvchi agent."""

    def __init__(self, db: Database, bot_client=None):
        self.db = db
        self.bot_client = bot_client
        self.escalation_threshold_hours = 4

    async def check_pending_feedbacks(self):
        """Ogohlantirish xabarlariga javob berilmaganligini tekshirish."""
        logger.info("[ESCALATION] Checking for unreplied alerts...")

        # 1. Oisha yuborgan oxirgi 24 soat ichidagi 'alert' turidagi amallarni olish
        # Hozircha agent_actions jadvalidan 'alert' yoki 'stagnation_alert' turidagilarini qidiramiz
        actions = await self.db.get_recent_agent_actions(limit=50)

        for action in actions:
            # Faqat 'agent_execute' (xabar yuborilgan) va alert mazmunidagi amallarni tekshiramiz
            if action["action_type"] != "agent_execute":
                continue

            data = action["action_data"]
            if not isinstance(data, dict):
                continue

            # Agar bu xabar accountability yoki stagnation haqida bo'lsa
            task_kind = data.get("task_kind", "")
            if "stagnation" not in task_kind and "accountability" not in task_kind:
                continue

            created_at = datetime.datetime.fromisoformat(action["created_at"])
            if datetime.datetime.now() - created_at > datetime.timedelta(
                hours=self.escalation_threshold_hours
            ):
                # Eskalatsiya vaqti kelgan.
                # Ammo avval javob berilganmi-yo'qmi, shuni tekshirish kerak.

                # Agar ushbu amal allaqachon eskalatsiya qilingan bo'lsa, o'tkazib yuboramiz
                if data.get("escalated"):
                    continue

                target_user_id = action["user_id"]
                if not target_user_id:
                    continue

                # 2. Ushbu vaqtdan keyin ushbu userdan xabarlar kelganmi?
                # (Sodda tekshirish: user_id xabar yozgan bo'lsa, demak u ko'rgan yoki javob bergan deb hisoblaymiz)
                conn = await self.db.get_connection()
                query = "SELECT COUNT(*) FROM message_logs WHERE user_id = ? AND created_at > ? AND is_ai_reply = 0"
                async with conn.execute(
                    query, (target_user_id, action["created_at"])
                ) as cursor:
                    row = await cursor.fetchone()
                    reply_count = row[0] if row else 0

                if reply_count == 0:
                    await self._escalate(action)
                else:
                    logger.info(
                        f"[ESCALATION] User {target_user_id} replied to alert. No escalation needed."
                    )
                    # Allaqachon ko'rilgan deb belgi qo'yamiz (logda)
                    data["escalated"] = False
                    data["replied"] = True
                    await self.db.log_agent_action(
                        action["user_id"], "alert_replied", data
                    )

    async def _escalate(self, action: Dict[str, Any]):
        """Admin-ga eskalatsiya qilish."""
        data = action["action_data"]
        user_id = action["user_id"]
        goal = data.get("goal", "Noma'lum ogohlantirish")

        logger.warning(
            f"[ESCALATION] Alert not replied by {user_id}. Escalating to Admin..."
        )

        owner_id = int(config.OWNER_ID or 0)
        if not owner_id or not self.bot_client:
            logger.error(
                "[ESCALATION] Owner ID or Bot Client missing. Cannot escalate."
            )
            return

        user_info = await self.db.get_user_info(user_id)
        name = user_info["first_name"] if user_info else f"ID: {user_id}"
        username = (
            f"@{user_info['username']}" if user_info and user_info["username"] else name
        )

        alert_text = (
            f"🚨 <b>ESKALATSIYA: JAVOB BERILMADI</b>\n"
            f"━━━━━━━━━━━━━━━━━━━━\n"
            f"👤 <b>Xodim:</b> {username}\n"
            f"📝 <b>Ogohlantirish:</b> {goal}\n"
            f"⏱ <b>Vaqt:</b> {action['created_at']}\n"
            f"━━━━━━━━━━━━━━━━━━━━\n"
            f"⚠️ Ushbu xodim {self.escalation_threshold_hours} soatdan beri Oishaning ogohlantirishiga javob bermadi."
        )

        try:
            # Telethon yoki boshqa client orqali admin-ga yuborish
            await self.bot_client.send_message(owner_id, alert_text, parse_mode="html")

            # Eskalatsiya qilinganini bazada saqlash
            data["escalated"] = True
            data["escalated_at"] = datetime.datetime.now().isoformat()
            await self.db.log_agent_action(user_id, "alert_escalated", data)
            logger.info(f"✅ Escalation message sent to Admin for user {user_id}")
        except Exception as e:
            logger.error(f"[ESCALATION ERROR] Failed to send message: {e}")
