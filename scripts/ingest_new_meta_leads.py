"""Script to immediately fetch all leads from a new Meta Leadgen Form and route to amoCRM."""
import os, sys, json, requests, asyncio
from datetime import datetime

sys.stdout.reconfigure(encoding="utf-8")
sys.path.insert(0, r"c:\Users\baxti\playground\oisha-os")
os.environ["AMOCRM_TOKEN_DB_PERSIST"] = "0"

from src.services.core.instagram.leadgen_router import route_leadgen_event
from src.services.core.instagram.leadgen_dedup import is_leadgen_processed

def fetch_and_route_form(form_id: str, access_token: str):
    version = os.getenv("META_GRAPH_API_VERSION", "v19.0").strip()
    url = f"https://graph.facebook.com/{version}/{form_id}/leads"
    params = {
        "access_token": access_token,
        "fields": "id,created_time,field_data,ad_id,form_id",
        "limit": 100
    }
    
    print(f"[{datetime.now()}] Forma {form_id} dan lidlar olinmoqda...")
    leads = []
    while url:
        resp = requests.get(url, params=params, timeout=20)
        if resp.status_code != 200:
            print(f"Xatolik ({resp.status_code}):", resp.text)
            return
        data = resp.json()
        leads.extend(data.get("data", []))
        url = data.get("paging", {}).get("next")
        params = {} # paging url includes params
        
    print(f"Jami Meta'da topilgan lidlar soni: {len(leads)} ta")
    
    loop = asyncio.get_event_loop()
    new_count = 0
    for lead in leads:
        leadgen_id = str(lead.get("id") or "").strip()
        if not leadgen_id:
            continue
        if is_leadgen_processed(leadgen_id):
            print(f"Lid {leadgen_id} allaqachon qayta ishlangan (o'tkazib yuborildi).")
            continue
            
        event = {**lead, "leadgen_id": leadgen_id}
        res = loop.run_until_complete(route_leadgen_event(event, access_token))
        if res.get("ok"):
            new_count += 1
            print(f"Muvaffaqiyatli amoCRM'ga tushirildi: Leadgen ID {leadgen_id} -> amoCRM Deal #{res.get('lead_id')}")
        else:
            print(f"Xatolik lid {leadgen_id} uchun:", res)
            
    print(f"\nJarayon yakunlandi! Jami {new_count} ta yangi lid amoCRM 'Sotuv Bo'limi' voronkasiga tushirildi.")

if __name__ == "__main__":
    if len(sys.argv) < 3:
        print("Foydalanish: python ingest_new_meta_leads.py <FORM_ID> <PAGE_ACCESS_TOKEN>")
        sys.exit(1)
    fetch_and_route_form(sys.argv[1], sys.argv[2])
