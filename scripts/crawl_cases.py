import asyncio
import logging
from telethon import TelegramClient
from telethon.sessions import StringSession
from src.settings import settings
from src.services.core.case_publisher import CasePublisher

# Set up logging
logging.basicConfig(
    level=logging.INFO, format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger("src.crawl_cases")


async def main(limit: int = 50):
    session_string = (
        settings.USERBOT_SESSION_STRING.get_secret_value()
        if settings.USERBOT_SESSION_STRING
        else None
    )

    if session_string:
        logger.info("[CRAWL] Using USERBOT_SESSION_STRING for authentication.")
        client = TelegramClient(
            StringSession(session_string),
            settings.API_ID,
            settings.API_HASH,
        )
    else:
        logger.info(
            "[CRAWL] No session string found. Using file-based session: data/oisha_user_active"
        )
        client = TelegramClient(
            "data/oisha_user_active", settings.API_ID, settings.API_HASH
        )

    await client.start()

    target = settings.JONBRANDING_CHANNEL.strip().lower()
    logger.info(f"🚀 [CRAWL] Starting backlog crawl of channel '@{target}' (limit={limit})...")

    publisher = CasePublisher(client=client)

    scanned = 0
    published = 0
    skipped = 0

    try:
        # Iterate over the target channel's messages
        async for msg in client.iter_messages(target, limit=limit):
            scanned += 1
            if not msg.text:
                skipped += 1
                continue

            try:
                success = await publisher.process_message(msg)
                if success:
                    published += 1
                else:
                    skipped += 1
            except Exception as pe:
                logger.error(f"[CRAWL] Error processing message {msg.id}: {pe}")
                skipped += 1

            # Safe delay to prevent Telegram flood wait triggers and API rate limit issues
            await asyncio.sleep(3.0)

    except Exception as e:
        logger.error(f"❌ [CRAWL] Crawl session failed: {e}")
    finally:
        await client.disconnect()

    logger.info(
        f"\n🏁 [CRAWL] Backlog crawl finished.\n"
        f"📊 Stats:\n"
        f"- Scanned: {scanned}\n"
        f"- Published Cases: {published}\n"
        f"- Skipped: {skipped}"
    )


if __name__ == "__main__":
    import sys

    limit_val = 30
    if len(sys.argv) > 1 and sys.argv[1].isdigit():
        limit_val = int(sys.argv[1])

    asyncio.run(main(limit=limit_val))
