"""
CRMDailyReporter and ReportBot orchestration classes.
"""
import asyncio
import logging
import os
from datetime import datetime, timedelta
from typing import Any, Optional

from src.services.core.crm.daily_report.history_db import HistoryDBMixin
from src.services.core.crm.daily_report.fetcher import AmoFetcherMixin
from src.services.core.crm.daily_report.formatter import FormatMixin

logger = logging.getLogger(__name__)


class CRMDailyReporter(HistoryDBMixin, AmoFetcherMixin, FormatMixin):
    """
    Kunlik va haftalik CRM hisobotlarini generatsiya qiluvchi sinf.
    """

    WON_STATUS = 142
    LOST_STATUS = 143
    DEFAULT_REPORT_PIPELINE_IDS = (
        "10117998",
        "10123314",
        "10123318",
        "10427390",
        "10947042",
        "10947046",
        "10963570",
    )

    def __init__(self, amocrm: Any, db_path: str = "data/report_history.db"):
        self._crm = amocrm
        self._db_path = db_path
        self._ensure_db()

class ReportBot:
    """
    Mustaqil hisobot boti — o'z Telegram token va DB bilan ishlaydi.

    Muhit o'zgaruvchilari:
        REPORT_BOT_TOKEN   — Telegram bot token (@BotFather'dan)
        REPORT_GROUP_ID    — Hisobot yuborilishi kerak guruh/kanal ID
        REPORT_HOUR        — Yuborish vaqti (soat, default=19)
        REPORT_MINUTE      — Yuborish vaqti (daqiqa, default=30)

    Buyruqlar:
        /report   — Darhol hisobot yuborish
        /stats    — Qisqa joriy holat (pipeline, bugungi leads)
        /history  — So'nggi 7 kunlik jadval
        /ping     — Bot ishlayaptimi tekshirish
    """

    def __init__(
        self,
        token: Optional[str] = None,
        group_id: Optional[int] = None,
        amocrm: Optional[Any] = None,
        report_hour: int = 19,
        report_minute: int = 30,
        db_path: str = "data/report_history.db",
    ):
        self._token        = token or os.environ.get("REPORT_BOT_TOKEN", "")
        self._group_id     = group_id or int(os.environ.get("REPORT_GROUP_ID", "0") or 0)
        self._report_hour  = int(os.environ.get("REPORT_HOUR", report_hour))
        self._report_minute = int(os.environ.get("REPORT_MINUTE", report_minute))
        self._amocrm       = amocrm
        self._reporter     = CRMDailyReporter(amocrm=amocrm, db_path=db_path)
        self._client       = None

    async def run(self) -> None:
        """Botni ishga tushirish (blocking)."""
        if not self._token:
            raise RuntimeError("REPORT_BOT_TOKEN topilmadi")

        from telethon import TelegramClient, events
        from telethon.sessions import StringSession

        # Bot session uchun alohida bot client
        api_id   = int(os.environ.get("API_ID", "0"))
        api_hash = os.environ.get("API_HASH", "")

        self._client = TelegramClient(StringSession(), api_id, api_hash).start(
            bot_token=self._token
        )

        @self._client.on(events.NewMessage(pattern="/ping"))
        async def ping(event):
            await event.respond("✅ Report bot ishlayapti")

        @self._client.on(events.NewMessage(pattern="/report"))
        async def manual_report(event):
            await event.respond("⏳ Hisobot tayyorlanmoqda...")
            await self._send_report(event.chat_id)

        @self._client.on(events.NewMessage(pattern="/stats"))
        async def quick_stats(event):
            await event.respond("⏳ Statistika olinmoqda...")
            stats = await self._reporter.fetch_stats()
            text  = (
                f"📊 Bugungi holat ({stats.date_label})\n"
                f"Tushgan: {stats.total_leads} lead\n"
                f"Won: {stats.won} | Daromad: ${stats.revenue:,.0f}\n"
                f"Pipeline: ${stats.pipeline_value:,.0f}"
            )
            await event.respond(text)

        @self._client.on(events.NewMessage(pattern="/history"))
        async def show_history(event):
            history = self._reporter.get_history(7)
            if not history:
                await event.respond("Tarix yo'q hali.")
                return
            lines = ["📅 So'nggi 7 kun:"]
            for s in history:
                lines.append(
                    f"{s.date_label}: {s.total_leads} lead | {s.won} won | ${s.revenue:,.0f}"
                )
            await event.respond("\n".join(lines))

        # Scheduled sender
        asyncio.create_task(self._scheduler_loop())

        logger.info(
            f"[ReportBot] started — hisobot {self._report_hour}:{self._report_minute:02d} da"
        )
        await self._client.run_until_disconnected()

    async def _scheduler_loop(self) -> None:
        """Har kuni belgilangan vaqtda hisobot yuboradi."""
        while True:
            now = datetime.now()
            target = now.replace(
                hour=self._report_hour,
                minute=self._report_minute,
                second=0,
                microsecond=0,
            )
            if now >= target:
                target += timedelta(days=1)
            wait_sec = (target - now).total_seconds()
            logger.info(f"[ReportBot] keyingi hisobot {target} da ({wait_sec/3600:.1f}h)")
            await asyncio.sleep(wait_sec)
            if self._group_id:
                await self._send_report(self._group_id)

    async def _send_report(self, chat_id: int) -> None:
        try:
            ok = await self._reporter.send_to_group(self._client, chat_id)
            if not ok:
                await self._client.send_message(
                    chat_id, "⚠️ Hisobotni yuborishda xatolik. AmoCRM tekshirilsin."
                )
        except Exception as exc:
            logger.error(f"[ReportBot] _send_report error: {exc}")


# ─────────────────────────────────────────────────────────────────────────────
# A) EnterpriseReporter extension — patch qilish uchun funksiya
# ─────────────────────────────────────────────────────────────────────────────

async def build_reportagram_report(
    enterprise_reporter: Any,
    amocrm: Optional[Any] = None,
) -> str:
    """
    EnterpriseReporter instansiga bog'liq bo'lmagan holda reportagram formatida
    hisobot qaytaradi. enterprise_reporter.crm.amocrm dan client oladi.

    Ishlatish:
        from src.services.core.crm.crm_daily_report import build_reportagram_report
        text = await build_reportagram_report(self)
    """
    crm_client = amocrm
    if crm_client is None and enterprise_reporter is not None:
        crm_service = getattr(enterprise_reporter, "crm", None)
        if crm_service:
            crm_client = getattr(crm_service, "amocrm", None)

    reporter = CRMDailyReporter(amocrm=crm_client)
    stats    = await reporter.fetch_stats()
    prev     = reporter._load_prev_stats()
    return reporter.format_report(stats, prev)
