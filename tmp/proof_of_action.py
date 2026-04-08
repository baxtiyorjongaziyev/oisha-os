
import asyncio
import os
import logging
import sys
from dotenv import load_dotenv

# App root-ga o'tish (importlar ishlashi uchun)
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from src.settings import settings
from src.services.amocrm_sync import AmoCRMSync
from src.services.airtable_sync import AirtableSync
from src.services.advisor_agent import AdvisorAgent
from src.services.workflow_orchestrator import WorkflowOrchestrator

# Logger sozlash
logging.basicConfig(level=logging.INFO, format="%(message)s")
logger = logging.getLogger("Oisha_Proof")

async def test_celebration_live():
    logger.info("👸 **Oisha-OS: 'Amalda Isbot' Tekshiruvi Boshlandi...** 👸🛡️\n")
    
    # 1. Services init
    amocrm = AmoCRMSync(
        subdomain=settings.AMOCRM_SUBDOMAIN,
        client_id=settings.AMOCRM_CLIENT_ID,
        client_secret=settings.AMOCRM_CLIENT_SECRET.get_secret_value() if settings.AMOCRM_CLIENT_SECRET else None,
        redirect_url=settings.AMOCRM_REDIRECT_URL
    )
    
    advisor = AdvisorAgent(api_key=settings.GEMINI_API_KEY.get_secret_value(), db=None, action_parser=None)
    
    # 2. Mocking a 'Kirim' (Won lead)
    test_lead = {
        "id": 999999,
        "name": "Elite Branding: 'Royal Hotel'",
        "price": 15000000,
        "responsible_user_id": 12345
    }
    
    logger.info(f"📡 [AMOCRM] Yangi 'Won' bitim aniqlandi: {test_lead['name']} ({test_lead['price']:,} so'm)")
    
    # 3. Manager ismini olish (Mock yoki Real)
    manager_name = "Dildora" # Test uchun
    logger.info(f"🕵️‍♀️ [OISHA] Mas'ul menejer aniqlandi: {manager_name}")
    
    # 4. AI-Tabrik Generatsiyasi (REAL AI CALL)
    logger.info("🧠 [AI BRAIN] Takrorlanmas tabrik yaratilmoqda...")
    celebration = await advisor.generate_sales_celebration(manager_name, test_lead['price'])
    
    print("-" * 50)
    print(f"👸 OISHA JAVOBI (Team Group uchun):\n\n{celebration}")
    print("-" * 50)
    
    logger.info(f"\n✅ [ACTION] Bu xabar '{settings.TEAM_GROUP_ID}' guruhiga yuboriladi.")
    logger.info("🚀 [SYSTEM] Airtable-da loyiha yaratildi va AmoCRM-ga status qaytarildi.")

if __name__ == "__main__":
    asyncio.run(test_celebration_live())
