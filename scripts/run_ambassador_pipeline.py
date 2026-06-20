"""
run_ambassador_pipeline.py
~~~~~~~~~~~~~~~~~~~~~~~~~~
Unified pipeline runner for Brand Ambassador Journey Automation in Oisha-OS.

Usage:
    # Run both sync and processing:
    python -m src.run_ambassador_pipeline

    # Only sync successfully realized leads from AmoCRM to Ambassadors:
    python -m src.run_ambassador_pipeline --sync-leads

    # Only process and send scheduled Telegram touchpoints/NPS surveys:
    python -m src.run_ambassador_pipeline --process-touches
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
logger = logging.getLogger("ambassador_pipeline")


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
        logger.warning("[AMBASSADOR PIPELINE] USERBOT_SESSION_STRING not set — Telegram proactive nudges disabled.")
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
            logger.warning("[AMBASSADOR PIPELINE] Userbot session not authorized.")
            await client.disconnect()
            return None
        logger.info("✅ [AMBASSADOR PIPELINE] Userbot connected.")
        return client
    except Exception as e:
        logger.warning(f"[AMBASSADOR PIPELINE] Userbot connect failed: {e}")
        return None


async def main():
    parser = argparse.ArgumentParser(
        description="Oisha-OS: Ambassador Journey Automation Pipeline"
    )
    parser.add_argument("--limit", type=int, default=50, help="Number of AmoCRM leads to scan")
    parser.add_argument("--sync-leads", action="store_true", help="Sync won leads to brand ambassadors")
    parser.add_argument("--process-touches", action="store_true", help="Process and send scheduled NPS/nudges")
    args = parser.parse_args()

    run_sync = args.sync_leads or (not args.process_touches)
    run_touches = args.process_touches or (not args.sync_leads)

    from src.database import Database
    from src.services.core.ambassador_journey import AmbassadorJourneyManager
    from src.settings import settings

    logger.info("🚀 [AMBASSADOR PIPELINE] Starting Oisha-OS Ambassador Journey Pipeline...")
    
    # 1. Init Database
    db = Database()
    await db.init_instance()

    # 2. Init AmoCRM Sync
    amocrm = await build_amocrm()

    # 3. Init Userbot if sending is requested
    user_client = None
    if run_touches:
        user_client = await build_userbot_client()

    # 4. Instantiate Ambassador Journey Manager
    api_key = settings.GEMINI_API_KEY.get_secret_value() if settings.GEMINI_API_KEY else ""
    manager = AmbassadorJourneyManager(
        amocrm=amocrm,
        db=db,
        user_client=user_client,
        gemini_api_key=api_key,
    )

    try:
        if run_sync:
            logger.info("⚡ [STAGE 1] Syncing successfully closed deals from AmoCRM...")
            sync_stats = await manager.sync_won_leads_to_ambassadors(limit=args.limit)
            logger.info(f"✅ [STAGE 1] Finished. Stats: {sync_stats}")

        if run_touches:
            logger.info("⚡ [STAGE 2] Processing scheduled outreach touchpoints...")
            touch_stats = await manager.process_scheduled_touchpoints()
            logger.info(f"✅ [STAGE 2] Finished. Stats: {touch_stats}")

    finally:
        if user_client:
            try:
                await user_client.disconnect()
            except Exception:
                pass
        await db.close()
        logger.info("🏁 [AMBASSADOR PIPELINE] Pipeline execution completed.")


if __name__ == "__main__":
    asyncio.run(main())
