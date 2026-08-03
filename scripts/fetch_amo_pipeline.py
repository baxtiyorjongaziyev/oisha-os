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
    url = f'{amocrm.base_url}/api/v4/leads/pipelines/11162542'
    resp = requests.get(url, headers=headers)
    if resp.status_code == 200:
        data = resp.json()
        statuses = data.get('_embedded', {}).get('statuses', [])
        
        with open('pipeline_result.json', 'w', encoding='utf-8') as f:
            json.dump({'pipeline_id': 11162542, 'statuses': statuses}, f, ensure_ascii=False, indent=2)
        print("Muvaffaqiyatli saqlandi: pipeline_result.json")

if __name__ == '__main__':
    if os.name == 'nt':
        asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())
    asyncio.run(main())
