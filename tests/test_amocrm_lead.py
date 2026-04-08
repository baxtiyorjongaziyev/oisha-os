import asyncio
import logging
from amocrm_sync import AmoCRMSync
from settings import settings

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

async def test_create_lead():
    print("AmoCRM Test Lead yaratish boshlandi...")
    print(f"DEBUG: Subdomain={settings.AMOCRM_SUBDOMAIN}")
    print(f"DEBUG: ClientID={settings.AMOCRM_CLIENT_ID}")
    print(f"DEBUG: Redirect={settings.AMOCRM_REDIRECT_URL}")
    
    amo = AmoCRMSync(
        subdomain=settings.AMOCRM_SUBDOMAIN,
        client_id=settings.AMOCRM_CLIENT_ID,
        client_secret=settings.AMOCRM_CLIENT_SECRET.get_secret_value() if settings.AMOCRM_CLIENT_SECRET else None,
        redirect_url=settings.AMOCRM_REDIRECT_URL
    )
    
    try:
        # Test lead ma'lumotlari
        name = "Test Mijoz (Oisha-OS)"
        phone = "+998991234567"
        price = 100000
        note = "Bu Oisha-OS Enterprise botidan test lead."
        
        print(f"Lead yaratishga urinish: {name} ({phone})...")
        success = amo.create_lead(name, phone, price, note)
        
        if success:
            print("✅ Lead muvaffaqiyatli yaratildi!")
        else:
            print("❌ Lead yaratib bo'lmadi (Loglarni ko'ring).")
            
    except Exception as e:
        print(f"💥 Xatolik yuz berdi: {e}")

if __name__ == "__main__":
    asyncio.run(test_create_lead())
