import os
import asyncio
import requests
import json
from dotenv import load_dotenv

import sys
sys.path.insert(0, os.path.abspath('.'))
from src.services.core.crm.amocrm_sync import AmoCRMSync
from src.settings import settings

async def main():
    load_dotenv()
    amocrm = AmoCRMSync(
        subdomain=settings.AMOCRM_SUBDOMAIN,
        client_id=settings.AMOCRM_CLIENT_ID,
        client_secret=settings.AMOCRM_CLIENT_SECRET,
        redirect_url=settings.AMOCRM_REDIRECT_URL,
    )
    
    headers = amocrm._get_headers()
    
    # 1. Fix Scout tasks statuses (11032562)
    scout_url = f"{amocrm.base_url}/api/v4/leads/pipelines/11032562/statuses"
    
    # In AmoCRM, system statuses 142 and 143 can be patched to rename them.
    # We will rename 142 to "Успешно реализовано" and 143 to "Закрыто и не реализовано".
    patch_payload = [
        {"id": 142, "name": "Успешно реализовано", "color": "#CCFF66"},
        {"id": 143, "name": "Закрыто и не реализовано", "color": "#D5D8DB"}
    ]
    print("Scout tasks tizim statuslari to'g'rilanmoqda...")
    requests.patch(scout_url, headers=headers, json=patch_payload)
    
    # 2. Migrate leads from Sales Pipeline (10117998) to 1. PRESALES (11162698, status 87609514)
    print("Bitimlar ko'chirilmoqda...")
    page = 1
    leads_to_update = []
    
    while True:
        leads_url = f"{amocrm.base_url}/api/v4/leads?filter[statuses][0][pipeline_id]=10117998&page={page}&limit=250"
        resp = requests.get(leads_url, headers=headers)
        if resp.status_code != 200:
            break
        
        data = resp.json()
        leads = data.get("_embedded", {}).get("leads", [])
        if not leads:
            break
            
        for l in leads:
            # Skip if already closed won/lost (142, 143) to avoid messing up history, 
            # though usually it's fine to move open ones only.
            if l.get("status_id") not in [142, 143]:
                leads_to_update.append({
                    "id": l["id"],
                    "pipeline_id": 11162698,
                    "status_id": 87609514
                })
        
        page += 1
        
    if leads_to_update:
        print(f"Jami {len(leads_to_update)} ta faol bitim topildi. Ularni PRESALES'ga o'tkazilmoqda...")
        # Update leads in batches of 250
        update_url = f"{amocrm.base_url}/api/v4/leads"
        for i in range(0, len(leads_to_update), 250):
            batch = leads_to_update[i:i+250]
            resp = requests.patch(update_url, headers=headers, json=batch)
            print(f"Batch {i//250 + 1} status: {resp.status_code}")
    else:
        print("Sales pipeline da ko'chirish uchun faol bitimlar topilmadi.")
        
    print("Migratsiya va tozalash ishlari yakunlandi.")

if __name__ == '__main__':
    if os.name == 'nt':
        asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())
    asyncio.run(main())
