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
    
    if not await amocrm.check_connection():
        print("XATOLIK: AmoCRM ga ulanib bo'lmadi!")
        return

    headers = amocrm._get_headers()
    url = f"{amocrm.base_url}/api/v4/leads/pipelines"
    
    payload = [
        {
            "name": "1. PRESALES",
            "sort": 1,
            "is_main": True,
            "is_unsorted_on": False,
            "_embedded": {
                "statuses": [
                    {"name": "Yangi so'rov", "sort": 10},
                    {"name": "Aloqaga chiqildi", "sort": 20},
                    {"name": "Kvalifikatsiya", "sort": 30},
                    {"name": "Uchrashuv belgilandi", "sort": 40}
                ]
            }
        },
        {
            "name": "2. CLOSER",
            "sort": 2,
            "is_main": False,
            "is_unsorted_on": False,
            "_embedded": {
                "statuses": [
                    {"name": "Uchrashuv o'tdi", "sort": 10},
                    {"name": "KP / Taklif", "sort": 20},
                    {"name": "Muzokara", "sort": 30},
                    {"name": "Shartnoma tayyorlanmoqda", "sort": 40},
                    {"name": "Avans kutilmoqda", "sort": 50}
                ]
            }
        }
    ]
    
    print("Yangi voronkalar yaratilmoqda...")
    resp = requests.post(url, headers=headers, json=payload)
    if resp.status_code in (200, 201):
        data = resp.json()
        pipelines = data.get("_embedded", {}).get("pipelines", [])
        
        results = []
        for p in pipelines:
            pid = p.get("id")
            name = p.get("name")
            print(f"PIPELINE_ID={pid} - {name}")
            
            # GET pipeline details to fetch status IDs
            detail_resp = requests.get(f"{url}/{pid}", headers=headers)
            if detail_resp.status_code == 200:
                detail_data = detail_resp.json()
                statuses = detail_data.get("_embedded", {}).get("statuses", [])
                results.append({
                    "pipeline_id": pid,
                    "name": name,
                    "statuses": statuses
                })
        
        with open("new_pipelines_result.json", "w", encoding="utf-8") as f:
            json.dump(results, f, ensure_ascii=False, indent=2)
            
        print("Barcha voronkalar new_pipelines_result.json ga saqlandi.")
    else:
        print(f"Xatolik: {resp.status_code} - {resp.text}")

if __name__ == '__main__':
    if os.name == 'nt':
        asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())
    asyncio.run(main())
