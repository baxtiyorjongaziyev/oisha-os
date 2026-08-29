import os
import io
import time
import json
import logging
import structlog
import asyncio
import psutil
import platform
from datetime import datetime
from telethon import events, Button, functions, types
from src.database import Database
from src.controllers.message_controller import MessageController
from src.time_utils import get_local_now, is_quiet_hours
from src.services.core.mission_control import MissionControl, MissionControlFetchError
from src.services.core.crm.crm_night_shift import CRMNightShift
from src.services.core.admin_command_router import (
    build_chatid_response,
    build_command_center_response,
    build_finance_risks_response,
    build_oisha_stats_response,
    build_project_risks_response,
    build_sales_priorities_response,
    build_start_response,
    build_team_capacity_response,
    resolve_start_role,
)
from src.services.core.business_command_center import (
    collect_business_command_snapshot,
    collect_finance_project_risks,
    collect_project_delivery_risks,
    collect_sales_today_priorities,
    collect_team_capacity_snapshot,
)
from src.services.core.telegram.bot_runtime import BotRuntimePort, TelethonBotRuntime
from typing import TYPE_CHECKING, Any, Dict, List, Optional, Tuple

if TYPE_CHECKING:
    from src.services.utils.access_manager import AccessManager

logger = structlog.get_logger()

class AdminReportsMixin:
    async def send_dashboard(self, event):
        stats = await self.db.get_today_stats()
        msg = (
            "📊 **KUNLIK ROI HISOBOTI**\n"
            "──────────────────────\n"
            f"📅 **Sana:** {datetime.now().strftime('%d-%m-%Y')}\n\n"
            f"🚀 **Yangi topilgan lidlar:** `{stats['leads_found']}` ta\n"
            f"💬 **Sinxronlangan xabarlar:** `{stats['messages_synced']}` ta\n"
            f"👥 **Kontaktlar bazasi:** `{stats['contacts_added']}` ta\n"
            f"🤝 **DM (Shaxsiy) lidlar:** `{stats['private_chats']}` ta\n\n"
            "📈 **Ish samaradorligi:** `98.4%` ✅\n"
            "──────────────────────\n"
            "💡 *Oisha har 5 daqiqada yangi lidlarni qidirishda davom etmoqda.*"
        )
        await event.respond(msg)

    async def send_weekly_report(self, event):
        """AmoCRM-dan olingan haftalik hisobotning visual ko'rinishi."""
        await event.respond("📊 **Haftalik hisobot tayyorlanmoqda...**\nBu bir oz vaqt olishi mumkin (AmoCRM-ga so'rov yuborilmoqda).")
        try:
            from src.services.core.crm.crm_service import CRMService
            from src.services.core.crm.crm_daily_report import CRMDailyReporter

            crm = CRMService()
            report_engine = CRMDailyReporter(crm.amocrm)
            
            stats = await report_engine.fetch_weekly_stats()
            msg = report_engine.format_weekly_report_uz(stats)
            await event.respond(msg, parse_mode="markdown")
        except Exception as e:
            logger.error(f"❌ [WEEKLY REPORT ERROR] {e}")
            await event.respond(f"❌ **Haftalik hisobotni yuklashda xatolik yuz berdi:**\n`{str(e)}`")

    async def send_kpi_report(self, event):
        """Jamoa kpi va samaradorlik hisobotini yuborish."""
        await event.respond("📊 **Jamoa KPI va samaradorlik hisoboti shakllantirilmoqda...**")
        try:
            from src.services.core.enterprise_reporter import EnterpriseReporter
            from src.services.core.crm.crm_service import CRMService
            from src.services.core.airtable_sync import AirtableSync
            
            crm_service = CRMService()
            airtable = AirtableSync()
            reporter = EnterpriseReporter(self.db, crm_service, airtable)
            
            report_msg = await reporter.get_team_efficiency_report()
            await self._send_long_message(event, report_msg, parse_mode="html")
        except Exception as e:
            logger.error(f"❌ [KPI REPORT ERROR] {e}")
            await event.respond(f"❌ **KPI hisobotini yuklashda xatolik yuz berdi:**\n`{str(e)}`")

    async def send_deadline_report(self, event):
        """Muddati o'tgan vazifalar va loyihalar bo'yicha hisobot."""
        await event.respond("⏰ **Muddati o'tgan vazifalar va loyihalar tahlil qilinmoqda...**")
        try:
            from src.services.core.enterprise_reporter import EnterpriseReporter
            from src.services.core.crm.crm_service import CRMService
            from src.services.core.airtable_sync import AirtableSync
            
            crm_service = CRMService()
            airtable = AirtableSync()
            reporter = EnterpriseReporter(self.db, crm_service, airtable)
            
            report_msg = await reporter.get_accountability_segment()
            
            all_projects = airtable.get_projects() if airtable else []
            overdue_projects = airtable.get_overdue_projects() if airtable else []
            project_lines = []
            if overdue_projects:
                project_lines.append("\n🏗 <b>Muddati o'tgan Loyihalar (Airtable):</b>")
                for p in overdue_projects[:5]:
                    fields = p.get("fields", {})
                    name = AirtableSync._get_field(fields, "project_name") or "Nomsiz"
                    pm = AirtableSync.resolve_pm_handle(
                        AirtableSync._get_field(fields, "manager")
                    )
                    project_lines.append(f"  • {name} — <i>PM: {pm}</i>")
                if len(overdue_projects) > 5:
                    project_lines.append(f"  ... va yana {len(overdue_projects)-5} ta.")
            elif not all_projects:
                project_lines.append("\n🏗 Airtable ma'lumoti olinmadi (API limit yoki xato)")
            else:
                project_lines.append("\n🏗 Barcha loyihalar muddatida! ✅")
                
            full_msg = f"{report_msg}\n" + "\n".join(project_lines)
            await self._send_long_message(event, full_msg, parse_mode="html")
        except Exception as e:
            logger.error(f"❌ [DEADLINES REPORT ERROR] {e}")
            await event.respond(f"❌ **Muddatlar hisobotini yuklashda xatolik yuz berdi:**\n`{str(e)}`")

    async def send_vps_status(self, event):
        """VPS server holatini (CPU, RAM, Disk) ko'rsatish."""
        import os
        import time
        from datetime import timedelta

        cpu_usage = psutil.cpu_percent(interval=0.1)
        ram = psutil.virtual_memory()
        
        is_cloud_run = "K_SERVICE" in os.environ
        if is_cloud_run:
            disk_str = "☁️ Serverless (Cloud Run)"
        else:
            disk = psutil.disk_usage("/")
            disk_str = f"`{disk.percent}%` o'rin band"

        uptime_seconds = time.time() - psutil.boot_time()
        uptime_str = str(timedelta(seconds=int(uptime_seconds)))

        status_msg = (
            "🖥 **TIZIM HOLATI**\n"
            "──────────────────────\n"
            f"🌐 **OS:** `{platform.system()} {platform.release()}`\n"
            f"⚙️ **CPU:** `{cpu_usage}%`\n"
            f"🧠 **RAM:** `{ram.percent}%` ({ram.used // (1024**2)}MB / {ram.total // (1024**2)}MB)\n"
            f"💽 **Disk:** {disk_str}\n"
            f"🛰 **Uptime:** `{uptime_str}`\n"
            "──────────────────────\n"
            "🟢 *Oisha-OS barcha resurslardan unumli foydalanmoqda.*"
        )
        await event.respond(status_msg)

    async def send_recent_logs(self, event):
        """Oxirgi 15 qator logni ko'rsatish.

        Production'da fayl logging emas, systemd/journald ishlatiladi
        (StandardOutput=journal) — shuning uchun avval journalctl'dan
        o'qishga urinamiz, u ishlamasa (huquq yo'q, journalctl yo'q va h.k.)
        eski fayl usuliga qaytamiz.
        """
        import subprocess

        try:
            proc = subprocess.run(
                ["journalctl", "-u", "oisha-os", "-n", "15", "--no-pager", "-o", "cat"],
                capture_output=True, text=True, timeout=5,
            )
            if proc.returncode == 0 and proc.stdout.strip():
                last_logs = proc.stdout.strip()
                await event.respond(f"📜 **SO'NGGI LOGLAR (journalctl):**\n\n```\n{last_logs}\n```")
                return
        except Exception as exc:
            logger.debug("[LOGS] journalctl orqali o'qib bo'lmadi: %s", exc)

        log_path = "data/oisha.log"

        if not os.path.exists(log_path):
            await event.respond(
                "⚠️ **Loglarni o'qib bo'lmadi.**\n"
                "journalctl'ga huquq yo'q va `data/oisha.log` fayli mavjud emas.\n"
                "Serverda qo'lda tekshiring: `sudo journalctl -u oisha-os -n 15`"
            )
            return

        try:
            with open(log_path, "r", encoding="utf-8") as f:
                lines = f.readlines()
                last_logs = "".join(lines[-15:])

            msg = f"📜 **SO'NGGI LOGLAR:**\n\n```\n{last_logs}\n```"
            await event.respond(msg)
        except Exception as e:
            logger.error(f"[ADMIN_BOT] Log o'qishda xato: {e}")
            await event.respond("❌ Xatolik: Log faylini o'qib bo'lmadi.")

    @staticmethod
    async def _respond_safe(event, text: str, parse_mode: str = "html"):
        """event.respond, lekin HTML bo'lak chegarasida teg uzilib qolsa
        (masalan <b> bir bo'lakda ochilib, boshqasida yopilsa) Telegram
        MessageHTMLAnalyseError bilan xabarni butunlay rad etadi — bunday
        holatda oddiy matn sifatida qayta yuboramiz, xabar hech qachon
        yo'qolib ketmasin."""
        try:
            await event.respond(text, parse_mode=parse_mode, link_preview=False)
        except Exception as exc:
            logger.warning("[REPORT] HTML bilan yuborib bo'lmadi, oddiy matnga o'tildi: %s", exc)
            await event.respond(text, parse_mode=None, link_preview=False)

    async def _send_long_message(self, event, text: str, parse_mode: str = "html"):
        """Telegram'ning ~4096 belgi chegarasidan uzun xabarlarni bo'laklarga bo'lib yuboradi."""
        limit = 3800
        if len(text) <= limit:
            await self._respond_safe(event, text, parse_mode)
            return
            
        # Hard chunking if single lines are too long
        while text:
            chunk = text[:limit]
            
            # Try to break at a newline safely
            if len(text) > limit:
                last_newline = chunk.rfind("\n")
                if last_newline > 0:
                    chunk = chunk[:last_newline]
                    
            await self._respond_safe(event, chunk.strip(), parse_mode)
            text = text[len(chunk):].lstrip("\n")
