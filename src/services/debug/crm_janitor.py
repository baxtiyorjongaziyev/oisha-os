import asyncio
import logging
from src.services.amocrm_sync import AmoCRMSync
from src.settings import settings

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

async def run_cleanup():
    amo = AmoCRMSync(
        subdomain=settings.AMOCRM_SUBDOMAIN,
        client_id=settings.AMOCRM_CLIENT_ID,
        client_secret=settings.AMOCRM_CLIENT_SECRET.get_secret_value() if settings.AMOCRM_CLIENT_SECRET else None,
        redirect_url=settings.AMOCRM_REDIRECT_URL
    )
    amo._load_token()
    
    print("🧹 AmoCRM Janitor ishga tushdi...")
    
    # 1. 'Muvaffaqiyatsiz' liddarni qidirish
    search_url = f"{amo.base_url}/api/v4/leads?filter[statuses][0][status_id]=143&limit=250"
    import requests
    resp = requests.get(search_url, headers=amo._get_headers())
    
    if resp.status_code == 200:
        candidates = resp.json().get("_embedded", {}).get("leads", [])
        ids = [l["id"] for l in candidates]
        print(f"🔍 {len(ids)} ta o'chirilishi kerak bo'lgan 'Lost' lidlar topildi.")
        
        # 2. O'chirish (Bulk emas, birma-bir metodda)
        confirm = True # User already "automatically" approved the plan
        if confirm:
            deleted_count = await amo.delete_leads(ids)
            print(f"✅ {deleted_count} ta lid muvaffaqiyatli o'chirildi.")
        else:
            print("❌ Bekor qilindi.")
    else:
        print(f"🤷 O'chirish uchun 'Lost' lidlar topilmadi (Status: {resp.status_code}).")

    # 3. Akkaunt holatini tekshirish
    status = await amo.get_account_status()
    if status:
        # Some plans show limits in 'limits' key
        print(f"\n📊 Akkaunt holati (API):")
        # print(status.get("name"), status.get("id"))
    
if __name__ == "__main__":
    asyncio.run(run_cleanup())
