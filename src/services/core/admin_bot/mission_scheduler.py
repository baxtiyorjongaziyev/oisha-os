"""
Admin Bot daily missions scheduling mixin.
"""
from __future__ import annotations

import asyncio
from datetime import datetime
import structlog
from telethon import Button

from src.services.core.mission_control import MissionControl, MissionControlFetchError
from src.time_utils import get_local_now
from src.services.core.admin_bot.gcontacts_sync import AdminGContactsSyncMixin

logger = structlog.get_logger()


class AdminMissionSchedulerMixin(AdminGContactsSyncMixin):
    """AdminBot mixin for mission distribution and scheduling."""

    async def trigger_daily_missions(self):
        """Asosiy missiya taqsimlash logikasi."""
        try:
            from src.settings import settings

            if not settings.SALES_MANAGER_IDS:
                logger.warning("[ADMIN_BOT] trigger_daily_missions: No managers found.")
                return False

            mc = MissionControl(db=self.db)

            managers = []
            for mid in settings.SALES_MANAGER_IDS:
                try:
                    entity = await self.bot_client.get_entity(mid)
                    name = entity.first_name or "Menejer"
                    managers.append((mid, name))
                except Exception as e:
                    logger.warning(f"[ADMIN_BOT] Manager {mid} entity not found: {e}")
                    managers.append((mid, f"Menejer-{mid}"))

            try:
                missions_map = await mc.distribute_daily_missions(managers)
            except MissionControlFetchError as e:
                logger.warning(f"[ADMIN_BOT] trigger_daily_missions skipped due to CRM fetch error: {e}")
                return False

            if not missions_map:
                logger.info("[ADMIN_BOT] No missions distributed today.")
                return True

            for manager_id, missions in missions_map.items():
                if not missions:
                    continue

                msg = (
                    f"🎯 **BUGUNGI SURGICAL SALES MISSIYALARINGIZ ({get_local_now().strftime('%d.%m.%Y')})**\n\n"
                    f"Hurmatli menejer, bugun sizga **{len(missions)} ta** muhim kontakt biriktirildi.\n"
                    f"Har bir bitim bo'yicha sun'iy intellekt tavsiyasi berilgan:\n\n"
                )

                buttons = []
                for i, m in enumerate(missions, 1):
                    lead_name = m.get('lead_name', "Noma'lum")
                    lead_id = m.get('lead_id')
                    action = m.get('action', "Bog'lanish")
                    urgency = m.get('urgency', 'normal')

                    urgency_icon = "🔥" if urgency == "critical" else ("⚡" if urgency == "high" else "📌")

                    msg += (
                        f"{i}. {urgency_icon} **{lead_name}** (ID: `{lead_id}`)\n"
                        f"   └ 🎯 **Topshiriq:** {action}\n\n"
                    )

                    buttons.append([
                        Button.inline(f"👁 Ko'rish: {lead_name[:15]}", data=f"view_lead_{lead_id}"),
                        Button.inline("✅ Bajarildi", data=f"done_mission_{lead_id}")
                    ])

                buttons.append([Button.inline("📊 Umumiy hisobotim", data="my_mission_stats")])

                try:
                    await self.bot_client.send_message(manager_id, msg, buttons=buttons)
                    logger.info(f"[ADMIN_BOT] Sent {len(missions)} missions to manager {manager_id}")
                except Exception as e:
                    logger.error(f"[ADMIN_BOT] Failed to send missions to {manager_id}: {e}")

            return True

        except Exception as e:
            logger.error(f"[ADMIN_BOT] trigger_daily_missions error: {e}", exc_info=True)
            return False

    async def _show_settings_menu(self, event, edit=False):
        """Sozlamalar va integratsiyalar boshqaruv menyusi."""
        msg = (
            "⚙️ **TIZIM SOZLAMALARI VA INTEGRATSIYALAR**\n"
            "━━━━━━━━━━━━━━━━━━━━━━━━━━\n\n"
            "Quyidagi xizmatlar va sinxronizatsiyalarni boshqarishingiz mumkin:\n"
        )

        buttons = [
            [Button.inline("🔄 Google Contacts <-> Telegram Sync", data="admin_sync_gcontacts")],
            [Button.inline("🤖 AI Autopilot Rejimi", data="admin_autopilot_toggle")],
            [Button.inline("⏱ Schedulers & Cron Jobs", data="admin_schedulers_list")],
            [Button.inline("🔙 Asosiy Menyu", data="admin_back_to_main")]
        ]
        if edit:
            await event.edit(msg, buttons=buttons)
        else:
            await event.respond(msg, buttons=buttons)
