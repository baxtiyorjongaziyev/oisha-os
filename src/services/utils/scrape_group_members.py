import asyncio
import logging
import random
from telethon import TelegramClient, errors
from src.database import Database
from src.settings import settings

# Setup logging
logging.basicConfig(
    level=logging.INFO, format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger("GroupScraper")


async def scrape_group_members(target_group_name: str):
    """'Tez natija 4' kabi guruh a'zolarini skanerlash va bazaga saqlash."""
    db = Database()
    session_path = "userbot_session"  # Standard session name used in the project

    client = TelegramClient(session_path, settings.API_ID, settings.API_HASH)

    try:
        await client.connect()
        if not await client.is_user_authorized():
            logger.error(
                "❌ Userbot authorized emas! Iltimos session faylini tekshiring."
            )
            return

        logger.info(f"🔍 Searching for group: {target_group_name}")
        target_group = None

        async for dialog in client.iter_dialogs():
            if target_group_name.upper() in dialog.name.upper():
                target_group = dialog
                logger.info(f"✅ Found: {dialog.name} (ID: {dialog.id})")
                break

        if not target_group:
            logger.error(f"❌ '{target_group_name}' guruhi topilmadi.")
            return

        logger.info(f"🚀 Scraping participants from {target_group.name}...")
        count = 0

        # Get all participants
        # We use a loop with delays to avoid FloodWait
        async for user in client.iter_participants(target_group.id):
            if user.bot:
                continue

            # Basic info
            user_id = user.id
            username = user.username
            first_name = user.first_name or "Unknown"
            last_name = user.last_name or ""
            phone = user.phone

            # Save to Oisha's memory (bot.db)
            db.upsert_user(
                user_id=user_id,
                first_name=first_name,
                last_name=last_name,
                username=username,
                phone=phone,
                source_group=target_group.name,  # Use a generic field or metadata
                role="Lead (Scraped)",
                last_seen=None,
            )

            count += 1
            if count % 50 == 0:
                logger.info(f"📈 Processed {count} members...")
                # Small safety delay every 50 users
                await asyncio.sleep(random.uniform(1, 3))

        logger.info(
            f"✨ DONE! Total {count} contacts from '{target_group_name}' saved to bot.db."
        )

    except errors.FloodWaitError as fe:
        logger.warning(f"⏳ FloodWait: {fe.seconds} soniya kutish kerak...")
        await asyncio.sleep(fe.seconds)
    except Exception as e:
        logger.error(f"❌ Error during scraping: {e}", exc_info=True)
    finally:
        await client.disconnect()


if __name__ == "__main__":
    # TARGET: "Tez natija 4"
    TARGET = "Tez natija 4"
    asyncio.run(scrape_group_members(TARGET))
