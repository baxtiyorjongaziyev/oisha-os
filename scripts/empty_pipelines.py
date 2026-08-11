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
    
    target_pipeline = 11162702 # 2. CLOSER

    pipelines_to_empty = [10117998, 10123314] # Sales pipeline, ARXIV - Closer
    
    for pid in pipelines_to_empty:
        print(f"Voronkani tozalash boshlandi (ID: {pid})...")
        page = 1
        leads_to_update = []
        
        while True:
            # fetch all leads in the pipeline (no status filter to get closed ones too)
            leads_url = f"{amocrm.base_url}/api/v4/leads?filter[statuses][0][pipeline_id]={pid}&page={page}&limit=250"
            resp = requests.get(leads_url, headers=headers)
            print(f"[{pid}] Page {page} fetched (Status: {resp.status_code})")
            if resp.status_code != 200:
                break
            
            data = resp.json()
            leads = data.get("_embedded", {}).get("leads", [])
            if not leads:
                break
                
            for l in leads:
                current_status = l.get("status_id")
                # If they are closed won (142) or closed lost (143), map them.
                # If they are any other status, map them to closed lost (143) just in case,
                # or maybe just map them to 'Неразобранное' of CLOSER?
                # Usually if they are here, they are closed.
                new_status = 142 if current_status == 142 else 143
                
                leads_to_update.append({
                    "id": l["id"],
                    "pipeline_id": target_pipeline,
                    "status_id": new_status
                })
            
            page += 1
            
        if leads_to_update:
            print(f"[{pid}] jami {len(leads_to_update)} ta bitim topildi. Ko'chirilmoqda...")
            update_url = f"{amocrm.base_url}/api/v4/leads"
            for i in range(0, len(leads_to_update), 250):
                batch = leads_to_update[i:i+250]
                patch_resp = requests.patch(update_url, headers=headers, json=batch)
                print(f"Batch {i//250 + 1} status: {patch_resp.status_code}")
        else:
            print(f"[{pid}] da umuman bitim topilmadi, u to'liq bo'sh!")

if __name__ == '__main__':
    if os.name == 'nt':
        asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())
    asyncio.run(main())
