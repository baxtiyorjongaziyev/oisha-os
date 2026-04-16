import asyncio
import os
import sys

# Project root-ni qo'shish
sys.path.append(os.getcwd())

from src.services.core.amocrm_sync import AmoCRMSync
from src.settings import settings

async def test_lead_creation():
    print("AmoCRM Lead integratsiyasini tekshirish boshlandi...")
    
    amo = AmoCRMSync(
        subdomain=settings.AMOCRM_SUBDOMAIN,
        client_id=settings.AMOCRM_CLIENT_ID,
        client_secret=settings.AMOCRM_CLIENT_SECRET.get_secret_value() if settings.AMOCRM_CLIENT_SECRET else '',
        redirect_url=settings.AMOCRM_REDIRECT_URL
    )
    
    # Test ma'lumotlari
    test_name = "Test Mijoz (Antigravity)"
    test_phone = "+998909998877"
    test_note = "Ushbu lead integratsiyani tekshirish uchun avtomatik yaratildi. Xizmat: Brending."
    
    try:
        print(f"Lead yaratishga urinish: {test_name} ({test_phone})...")
        lead_id = await amo.ensure_lead(test_name, test_phone, test_note)
        
        if lead_id:
            print(f"MUVOFFIQUYAT! Lead yaratildi. ID: {lead_id}")
            print(f"Havola: https://{settings.AMOCRM_SUBDOMAIN}.amocrm.ru/leads/detail/{lead_id}")
        else:
            print("XATO: Lead yaratilmadi (Noma'lum sabab).")
            
    except Exception as e:
        print(f"XATO yuz berdi: {e}")

if __name__ == "__main__":
    asyncio.run(test_lead_creation())
