"""
run_telegram_task_pipeline.py
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
CLI Runner to fetch Telegram dialog history, process and transcribe voice notes,
analyze conversation semantics using Gemini AI, and automatically create
Action Tasks (vazifalar) inside AmoCRM leads.

Usage:
    python -m src.run_telegram_task_pipeline --phone "+998903881047" --lead-id 45118637 --limit 30
"""

import argparse
import asyncio
import logging
import sys

# Windows PowerShell unicode fix — force UTF-8 output
if sys.stdout.encoding and sys.stdout.encoding.lower() not in ("utf-8", "utf8"):
    try:
        sys.stdout.reconfigure(encoding="utf-8")
        sys.stderr.reconfigure(encoding="utf-8")
    except Exception:
        pass

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s -- %(message)s",
    handlers=[
        logging.StreamHandler(
            stream=open(sys.stdout.fileno(), mode="w", encoding="utf-8", closefd=False)
            if hasattr(sys.stdout, "fileno")
            else sys.stdout
        )
    ],
)
logger = logging.getLogger("telegram_task_pipeline")


async def build_amocrm() -> "AmoCRMSync":
    from src.settings import settings
    from src.services.core.amocrm_sync import AmoCRMSync

    return AmoCRMSync(
        subdomain=settings.AMOCRM_SUBDOMAIN,
        client_id=settings.AMOCRM_CLIENT_ID,
        client_secret=(
            settings.AMOCRM_CLIENT_SECRET.get_secret_value()
            if settings.AMOCRM_CLIENT_SECRET
            else ""
        ),
        redirect_url=settings.AMOCRM_REDIRECT_URL,
    )


async def build_userbot_client():
    """Build Telethon userbot client if USERBOT_SESSION_STRING is configured."""
    from src.settings import settings

    session_str = (
        settings.USERBOT_SESSION_STRING.get_secret_value()
        if settings.USERBOT_SESSION_STRING
        else None
    )
    if not session_str or not session_str.strip():
        logger.error("[PIPELINE] USERBOT_SESSION_STRING not set — Telegram dialogue reading impossible.")
        return None

    try:
        from telethon import TelegramClient
        from telethon.sessions import StringSession

        client = TelegramClient(
            StringSession(session_str),
            api_id=settings.API_ID,
            api_hash=settings.API_HASH,
        )
        await client.connect()
        if not await client.is_user_authorized():
            logger.error("[PIPELINE] Userbot session not authorized.")
            await client.disconnect()
            return None
        logger.info("✅ [PIPELINE] Userbot connected.")
        return client
    except Exception as e:
        logger.error(f"[PIPELINE] Userbot connect failed: {e}")
        return None


async def main():
    parser = argparse.ArgumentParser(
        description="Oisha-OS: Telegram Voice & Chat Task Creator Pipeline"
    )
    parser.add_argument("--phone", type=str, required=True, help="Telegram user phone number or username")
    parser.add_argument("--lead-id", type=int, required=True, help="AmoCRM lead ID to add tasks to")
    parser.add_argument("--limit", type=int, default=20, help="Number of recent messages to analyze (default: 20)")
    args = parser.parse_args()

    from src.database import Database
    from src.services.utils.voice_processor import VoiceProcessor
    from src.services.core.telegram_task_creator import TelegramTaskCreator
    from src.settings import settings

    logger.info("🚀 [PIPELINE] Starting Telegram Task Creator Pipeline...")
    
    # 1. Database Pool
    db = Database()
    await db.init_instance()

    # 2. AmoCRM Sync Client
    amocrm = await build_amocrm()

    # 3. Userbot Telegram Client
    user_client = await build_userbot_client()
    if not user_client:
        await db.close()
        logger.error("[PIPELINE] Aborting: Userbot is offline.")
        return

    # 4. Voice Processor & Gemini Settings
    api_key = settings.GEMINI_API_KEY.get_secret_value() if settings.GEMINI_API_KEY else ""
    voice_proc = VoiceProcessor(api_key=api_key)

    # 5. Core Orchestrator
    creator = TelegramTaskCreator(
        amocrm=amocrm,
        db=db,
        user_client=user_client,
        voice_processor=voice_proc,
        gemini_api_key=api_key,
    )

    try:
        logger.info(f"⚡ Running chat analysis for target '{args.phone}' on lead {args.lead_id}...")
        tasks = await creator.create_amocrm_tasks_from_chat(
            phone_or_username=args.phone,
            lead_id=args.lead_id,
            limit=args.limit,
        )
        logger.info(f"🏁 Finished. Added {len(tasks)} task(s) to AmoCRM. Details: {tasks}")
    finally:
        try:
            await user_client.disconnect()
        except Exception:
            pass
        await db.close()


if __name__ == "__main__":
    asyncio.run(main())
