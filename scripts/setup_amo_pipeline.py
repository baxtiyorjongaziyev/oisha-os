import os
import asyncio
import requests
import json
from dotenv import load_dotenv

import sys
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
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
    
    # Ensure auth
    if not await amocrm.check_connection():
        print("XATOLIK: AmoCRM ga ulanib bo'lmadi!")
        return

    headers = amocrm._get_headers()
    url = f"{amocrm.base_url}/api/v4/leads/pipelines"
    
    payload = [
        {
            "name": "Oisha Business Command Center",
            "sort": 1,
            "is_main": True,
            "is_unsorted_on": False,
            "_embedded": {
                "statuses": [
                    {"name": "Yangi so'rov", "sort": 10, "color": "#fffd7f"},
                    {"name": "Aloqaga chiqildi", "sort": 20},
                    {"name": "Kvalifikatsiya", "sort": 30},
                    {"name": "Strategik sessiya", "sort": 40},
                    {"name": "KP yuborildi", "sort": 50},
                    {"name": "Muzokara", "sort": 60},
                    {"name": "Avans kutilmoqda", "sort": 70},
                    {"name": "Ishlab chiqarish", "sort": 80}
                ]
            }
        }
    ]
    
    print("Pipeline yaratilmoqda...")
    resp = requests.post(url, headers=headers, json=payload)
    if resp.status_code in (200, 201):
        data = resp.json()
        pipeline = data.get("_embedded", {}).get("pipelines", [{}])[0]
        pipeline_id = pipeline.get("id")
        statuses = pipeline.get("_embedded", {}).get("statuses", [])
        print(f"PIPELINE_ID={pipeline_id}")
        for s in statuses:
            print(f"STATUS: {s.get('name')} -> ID={s.get('id')}")
        
        # Save to a json file for the agent to parse
        with open("pipeline_result.json", "w", encoding="utf-8") as f:
            json.dump({"pipeline_id": pipeline_id, "statuses": statuses}, f, ensure_ascii=False, indent=2)
            
    else:
        print(f"Xatolik: {resp.status_code} - {resp.text}")

if __name__ == "__main__":
    if os.name == 'nt':
        asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())
    asyncio.run(main())
