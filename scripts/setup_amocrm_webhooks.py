import asyncio
import os
import sys

# Oisha-OS muhitini yuklash uchun
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from src.settings import settings
from src.services.core.crm.amocrm_sync import AmoCRMSync
import requests

async def setup_webhooks():
    print("AmoCRM Webhooklarini sozlash boshlandi...")
    
    amocrm = AmoCRMSync(
        subdomain=settings.AMOCRM_SUBDOMAIN.get_secret_value() if hasattr(settings.AMOCRM_SUBDOMAIN, 'get_secret_value') else settings.AMOCRM_SUBDOMAIN,
        client_id=settings.AMOCRM_CLIENT_ID.get_secret_value() if hasattr(settings.AMOCRM_CLIENT_ID, 'get_secret_value') else settings.AMOCRM_CLIENT_ID,
        client_secret=settings.AMOCRM_CLIENT_SECRET.get_secret_value() if hasattr(settings.AMOCRM_CLIENT_SECRET, 'get_secret_value') else settings.AMOCRM_CLIENT_SECRET,
        redirect_url=settings.AMOCRM_REDIRECT_URL.get_secret_value() if hasattr(settings.AMOCRM_REDIRECT_URL, 'get_secret_value') else settings.AMOCRM_REDIRECT_URL,
    )
    
    if not amocrm.access_token:
        amocrm._load_token()

    if not amocrm.access_token:
        print("XATOLIK: AmoCRM tokeni topilmadi. Avval autentifikatsiyadan o'ting.")
        return

    # Oisha-OS Webhook manzili (AmoCRM integration uchun)
    webhook_url = "https://api.jonbranding.uz/webhook/amocrm" 
    
    # AmoCRM Webhook API endpoint
    url = f"{amocrm.base_url}/api/v4/webhooks"
    
    payload = {
        "destination": webhook_url,
        "settings": [
            "add_customer",
            "update_customer",
            "add_lead",
            "update_lead"
        ]
    }
    
    print(f"Webhook yuborilmoqda: {webhook_url}")
    
    try:
        response = await amocrm._request_with_auth(requests.post, url, json=payload, timeout=30)
        
        if response.status_code in (200, 201, 202):
            print("MUVAFFAQIYATLI: Webhooklar AmoCRM'ga o'rnatildi!")
        else:
            print(f"XATOLIK: Webhook o'rnatishda muammo. HTTP {response.status_code}")
            print(response.text)
    except Exception as e:
        print(f"XATOLIK: {e}")

if __name__ == "__main__":
    asyncio.run(setup_webhooks())
