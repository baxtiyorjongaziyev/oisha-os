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
    url = f'{amocrm.base_url}/api/v4/leads/pipelines'
    
    print("Pipelines ro'yxati olinmoqda...")
    resp = requests.get(url, headers=headers)
    if resp.status_code == 200:
        pipelines = resp.json().get('_embedded', {}).get('pipelines', [])
        
        results = []
        for p in pipelines:
            pid = p.get('id')
            name = p.get('name')
            # get statuses
            statuses = p.get('_embedded', {}).get('statuses', [])
            status_data = [{"id": s.get('id'), "name": s.get('name'), "sort": s.get('sort')} for s in statuses]
            
            results.append({
                "pipeline_id": pid,
                "name": name,
                "statuses": status_data
            })
            
        with open('all_pipelines.json', 'w', encoding='utf-8') as f:
            json.dump(results, f, ensure_ascii=False, indent=2)
            
        print("Barcha voronkalar all_pipelines.json ga saqlandi.")
    else:
        print(f"Error fetching pipelines: {resp.text}")

if __name__ == '__main__':
    if os.name == 'nt':
        asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())
    asyncio.run(main())
