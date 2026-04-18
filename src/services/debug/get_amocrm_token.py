import asyncio
import sys
import os

# Add project root to path
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "../../../")))

from src.services.core.amocrm_sync import AmoCRMSync
from src.settings import settings

async def main():
    if not all([settings.AMOCRM_SUBDOMAIN, settings.AMOCRM_CLIENT_ID, settings.AMOCRM_CLIENT_SECRET, settings.AMOCRM_REDIRECT_URL]):
        print("XATO: .env faylda AmoCRM sozlamalari (Subdomain, ID, Secret, Redirect) bo'lishi shart!")
        return

    print("\n" + "="*40)
    print("🚀 AmoCRM Dastlabki Avtorizatsiya")
    print("="*40)
    print("\nQadamlar:")
    print("1. AmoCRM -> Sozlamalar -> Integratsiyalar -> Oisha-OS ni oching.")
    print("2. 'Kalitlar va ruxsatlar' bo'limidan 'Authorization Code' nusxasini oling.")
    print("3. Kodni quyida kiriting (e'tibor bering, muddat 20 minut!)\n")
    
    auth_code = input("Authorization Code: ").strip()
    
    if not auth_code:
        print("\nXato: Kod kiritilmadi.")
        return

    amocrm = AmoCRMSync(
        subdomain=settings.AMOCRM_SUBDOMAIN,
        client_id=settings.AMOCRM_CLIENT_ID,
        client_secret=settings.AMOCRM_CLIENT_SECRET.get_secret_value() if settings.AMOCRM_CLIENT_SECRET else None,
        redirect_url=settings.AMOCRM_REDIRECT_URL
    )
    
    print("\n⏳ Token olinmoqda...")
    success = amocrm.authorize_initial(auth_code)
    
    if success:
        print("\n✅ MUVAFFAQIYATLI! Token saqlandi (data/amocrm_token.json).")
        print("Endi barcha tizimlar AmoCRM bilan ishlay oladi.")
    else:
        print("\n❌ XATOLIK! Kod noto'g'ri, eskirgan yoki integratsiya sozlamalari (ID/Secret) xato.")

if __name__ == "__main__":
    asyncio.run(main())
