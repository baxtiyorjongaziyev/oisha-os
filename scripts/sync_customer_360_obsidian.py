"""
Backfill & Initial Sync Script for Customer 360 in Obsidian Second Brain.

Scans active projects and clients across AmoCRM, Airtable, and Telegram,
and creates or updates rich Customer 360 cards in Obsidian (70-Mijozlar/).
"""
import asyncio
import logging
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src.services.customer_360 import (
    Customer360Collector,
    Customer360ObsidianSyncer,
)


logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger(__name__)

# Birlamchi asosiy mijozlar ro'yxati (JonBranding Registry va faol loyihalardan)
INITIAL_CLIENTS = [
    {"name": "Kamila Pardalari", "phone": "+998901234567"},
    {"name": "Ledir", "phone": ""},
    {"name": "Beyaz", "phone": ""},
    {"name": "Shirona", "phone": ""},
    {"name": "Sadiya Cakes", "phone": ""},
    {"name": "Melav", "phone": ""},
    {"name": "Yasira", "phone": ""},
]


async def main():
    logger.info("🚀 Customer 360 Obsidian Initial Sync boshlanmoqda...")
    collector = Customer360Collector()
    syncer = Customer360ObsidianSyncer()

    success_count = 0
    for client in INITIAL_CLIENTS:
        name = client["name"]
        phone = client.get("phone", "")
        logger.info(f"🔄 Sinxronlanmoqda: {name}...")
        try:
            profile = await collector.collect_profile(
                identifier=name,
                phone=phone,
                name=name,
            )
            saved_path = await syncer.sync_profile(profile)
            if saved_path:
                logger.info(f"✅ Muvaffaqiyatli saqlandi: {saved_path}")
                success_count += 1
        except Exception as ex:
            logger.error(f"❌ Xatolik {name}: {ex}")

    logger.info(f"🎉 Yakunlandi! Jami {success_count}/{len(INITIAL_CLIENTS)} ta mijoz kartochkalari yaratildi va yangilandi.")


if __name__ == "__main__":
    asyncio.run(main())
