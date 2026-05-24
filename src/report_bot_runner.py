"""
report_bot_runner.py — Standalone kunlik CRM hisobot botini ishga tushirish.

Ishlatish:
    python src/report_bot_runner.py

Muhit o'zgaruvchilari (.env yoki Cloud Secret Manager):
    REPORT_BOT_TOKEN   — Telegram bot token (yangi bot yarating @BotFather'da)
    REPORT_GROUP_ID    — Hisobot yuborilishi kerak guruh ID (masalan: -1001234567890)
    API_ID             — Telegram API ID (main bot bilan bir xil bo'lishi mumkin)
    API_HASH           — Telegram API Hash
    REPORT_HOUR        — Yuborish soati (default: 19)
    REPORT_MINUTE      — Yuborish daqiqasi (default: 30)

    # AmoCRM (mavjud .env dan o'qiladi)
    AMOCRM_SUBDOMAIN
    AMOCRM_CLIENT_ID
    AMOCRM_CLIENT_SECRET
"""

import asyncio
import logging
import os
import sys

# Project root
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
logger = logging.getLogger("report_bot")


def _load_env():
    """Load .env if python-dotenv is available."""
    try:
        from dotenv import load_dotenv
        load_dotenv()
    except ImportError:
        pass


def _build_amocrm():
    """AmoCRM client yaratish."""
    try:
        from src.services.core.amocrm_sync import AmoCRMSync
        subdomain      = os.environ.get("AMOCRM_SUBDOMAIN", "")
        client_id      = os.environ.get("AMOCRM_CLIENT_ID", "")
        client_secret  = os.environ.get("AMOCRM_CLIENT_SECRET", "")
        redirect_uri   = os.environ.get("AMOCRM_REDIRECT_URI", "https://example.com")
        if subdomain and client_id and client_secret:
            return AmoCRMSync(subdomain, client_id, client_secret, redirect_uri)
    except Exception as exc:
        logger.warning(f"AmoCRM init failed: {exc}")
    return None


async def main():
    _load_env()

    token    = os.environ.get("REPORT_BOT_TOKEN", "")
    group_id = int(os.environ.get("REPORT_GROUP_ID", "0") or 0)

    if not token:
        logger.error(
            "REPORT_BOT_TOKEN topilmadi. .env ga REPORT_BOT_TOKEN=... qo'shing."
        )
        sys.exit(1)
    if not group_id:
        logger.error(
            "REPORT_GROUP_ID topilmadi. .env ga REPORT_GROUP_ID=-1001234567890 qo'shing."
        )
        sys.exit(1)

    amocrm = _build_amocrm()
    if not amocrm:
        logger.warning("AmoCRM ulanmadi — hisobot bo'sh statistika bilan ishlaydi.")

    from src.services.core.crm_daily_report import ReportBot
    bot = ReportBot(
        token=token,
        group_id=group_id,
        amocrm=amocrm,
        report_hour=int(os.environ.get("REPORT_HOUR", 19)),
        report_minute=int(os.environ.get("REPORT_MINUTE", 30)),
    )

    logger.info(f"Report bot ishga tushmoqda → guruh {group_id}")
    await bot.run()


if __name__ == "__main__":
    asyncio.run(main())
