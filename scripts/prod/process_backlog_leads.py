
import asyncio
import logging
import os
import sys

# Add root directory to path to import services correctly
root_dir = r"c:\Users\baxti\.gemini\antigravity\playground\oisha-os"
sys.path.append(root_dir)

from services.google_service import GoogleService
from amocrm_sync import AmoCRMSync
from database import Database
from settings import settings
from telethon import TelegramClient

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("BACKLOG_PROCESSOR")

BACKLOG_LEADS = [
    {
        "name": "Abdumo'min Aka Sarkor Comfort Cabel TN5",
        "phone": "+998998594646",
        "note": "Sarkor Comfort Cabel. Yakshanba kuni aloqaga chiqish kerak @Oydin_JonBranding",
        "responsible": "Oydin",
        "price": 0,
        "follow_up": "Sunday"
    },
    {
        "name": "Jamoliddin Aka TN5 Gr Avtoservis",
        "phone": "+79912380262",
        "note": "Avtoservis. Whatsappdan gaplashish kerak @Oydin_JonBranding. Yakshanba kuni.",
        "responsible": "Oydin",
        "price": 0,
        "follow_up": "Sunday"
    },
    {
        "name": "Zafar Aka Lola Taste Konfet Ich Gr",
        "phone": "+998992605005",
        "note": "Lola taste expert tekshiruv. 824,000 so'm to'lov olish kerak. @Oydin_JonBranding",
        "responsible": "Oydin",
        "price": 824000,
        "follow_up": "Tomorrow"
    },
    {
        "name": "Baxrom Aka Baxra Makron ICh TN5 Gr",
        "phone": "+998905133306",
        "note": "Baxra Makron ICh. TN5 Gr xabari.",
        "responsible": "Oydin",
        "price": 0,
        "follow_up": None
    }
]

async def process_backlog():
    db = Database()
    amo = AmoCRMSync(
        subdomain=settings.AMOCRM_SUBDOMAIN,
        client_id=settings.AMOCRM_CLIENT_ID,
        client_secret=settings.AMOCRM_CLIENT_SECRET.get_secret_value(),
        redirect_url=settings.AMOCRM_REDIRECT_URL
    )
    google = GoogleService()
    
    # Try to reuse session or create mock client if session is locked
    try:
        client = TelegramClient(os.path.join(root_dir, 'research_session'), settings.API_ID, settings.API_HASH)
        await client.connect()
        connected = True
    except Exception as e:
        logger.warning(f"Session locked, sending skip notifications: {e}")
        connected = False
    
    for lead in BACKLOG_LEADS:
        logger.info(f"Processing: {lead['name']}")
        
        # 1. Save to Google Contacts
        try:
            await google.save_contact(lead['name'], [lead['phone']], notes=lead['note'], group_name="TEZ NATIJA 5")
            logger.info(f"Saved contact: {lead['name']}")
        except Exception as e:
            logger.error(f"Google Error: {e}")

        # 2. Create AmoCRM Lead
        try:
            amo.create_lead(
                name=lead['name'],
                phone=lead['phone'],
                price=lead['price'],
                note=lead['note']
            )
            logger.info(f"AmoCRM lead created: {lead['name']}")
        except Exception as e:
            logger.error(f"AmoCRM Error: {e}")

        # 3. Notification (Simplified if not connected)
        if connected:
            try:
                message = (
                    f"📥 **YANGI LID (BACKLOG)**\n\n"
                    f"👤 **Mijoz:** {lead['name']}\n"
                    f"📞 **Tel:** {lead['phone']}\n"
                    f"💰 **Summa:** {lead['price']:,} UZS\n"
                    f"📝 **Vazifa:** {lead['note']}\n\n"
                    f"📢 @Oydin_JonBranding ushbu lid bilan ishlashni boshlaymiz! 👸🛡️"
                )
                await client.send_message(settings.CRM_GROUP_ID, message)
            except Exception as e:
                logger.error(f"Notification Error: {e}")
            
        await asyncio.sleep(2)

    if connected:
        await client.disconnect()

if __name__ == "__main__":
    asyncio.run(process_backlog())
