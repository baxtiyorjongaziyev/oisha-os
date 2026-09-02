"""AmoCRM OAuth — token olish uchun yo'riqnoma."""
import os
import sys
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from src.settings import settings

subdomain = settings.AMOCRM_SUBDOMAIN
client_id = settings.AMOCRM_CLIENT_ID
redirect_url = settings.AMOCRM_REDIRECT_URL

print("=" * 60)
print("AmoCRM OAuth Token Olish")
print("=" * 60)
print()
print("1. Brauzerda quyidagi havolani oching:")
print()
auth_url = f"https://{subdomain}.amocrm.ru/oauth2/authorize?client_id={client_id}&redirect_uri={redirect_url}"
print(f"   {auth_url}")
print()
print("2. AmoCRM ga kiring va ruxsat bering")
print("3. Redirect bo'lgan URL dan ?code=... ni toping")
print("   Masalan: https://localhost/?code=ABC123def456")
print("4. Quyidagi buyrug'ni ishga tushiring:")
print()
print("   python src/scripts/get_amocrm_token.py <CODE>")
print()
print("=" * 60)
