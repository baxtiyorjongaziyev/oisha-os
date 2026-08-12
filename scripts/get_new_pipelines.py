import os
import asyncio
import requests
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
    
    pipelines_url = f"{amocrm.base_url}/api/v4/leads/pipelines"
    resp = requests.get(pipelines_url, headers=headers)
    pipelines = resp.json().get('_embedded', {}).get('pipelines', [])
    for p in pipelines:
        if p['id'] in [11162698, 11162702]:
            print(f"Pipeline: {p['name']} ({p['id']})")
            for status in p['_embedded']['statuses']:
                print(f"  - {status['name']} ({status['id']})")

if __name__ == '__main__':
    if os.name == 'nt':
        asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())
    asyncio.run(main())
