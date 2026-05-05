import asyncio
import logging
from telethon import TelegramClient
from services.google_service import GoogleService
from services.lead_scraper import LeadScraper
from settings import settings

# Setup logging
logging.basicConfig(
    level=logging.INFO, format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger("PILOT_SYNC")


async def main():
    try:
        # Initialize Services
        google_service = GoogleService()
        # Connect Telegram
        client = TelegramClient("userbot_session", settings.API_ID, settings.API_HASH)
        await client.connect()

        # Initialize Scraper with client for background tasks
        scraper = LeadScraper(google_service, client=client)

        if not await client.is_user_authorized():
            print("Telegram authorized emas!")
            return

        group_id = -1003820339529
        topic_id = 7  # Ishtirokchilar ma'lumotlari

        print("\n🚀 LEAD SYNC BOSHLANDI (Limit: 25 kontakt) 👸🛡️")
        print("Guruh: 'TEZ NATIJA 5' UMUMIY")
        print(f"Mavzu ID: {topic_id}")
        print("-" * 40)

        # Start safe sync with limit = 25
        synced_count = await scraper.sync_topic_to_contacts(
            client, group_id, topic_id, limit=25
        )

        print("-" * 40)
        print(f"✅ PILOT YAKUNLANDI. {synced_count} ta kontakt saqlandi. ✨🧚‍♂️")

        await client.disconnect()
    except Exception as e:
        logger.error(f"Pilot Error: {e}")


if __name__ == "__main__":
    asyncio.run(main())
