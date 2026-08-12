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
    
    # Get all pipelines
    url = f"{amocrm.base_url}/api/v4/leads/pipelines"
    resp = requests.get(url, headers=headers)
    if resp.status_code != 200:
        print("Xatolik pipelines olishda")
        return
        
    pipelines = resp.json().get('_embedded', {}).get('pipelines', [])
    
    print("Bo'sh va keraksiz voronkalarni aniqlash boshlandi...")
    for p in pipelines:
        pid = p.get('id')
        name = p.get('name')
        
        # Check leads count in this pipeline (active)
        # To just check if there are ANY leads (including closed ones), we can query without filtering statuses
        leads_url = f"{amocrm.base_url}/api/v4/leads?filter[statuses][0][pipeline_id]={pid}&limit=1"
        l_resp = requests.get(leads_url, headers=headers)
        
        has_leads = False
        if l_resp.status_code == 200:
            leads = l_resp.json().get('_embedded', {}).get('leads', [])
            if leads:
                has_leads = True
                
        print(f"[{pid}] {name}: {'BOSH/PUSTOY' if not has_leads else 'BITIMLAR MAVJUD'}")

if __name__ == '__main__':
    if os.name == 'nt':
        asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())
    asyncio.run(main())
