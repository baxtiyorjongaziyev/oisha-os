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
    
    # 1. Get any lead from 10117998 that was closed recently (today)
    url = f"{amocrm.base_url}/api/v4/leads?order[updated_at]=desc&limit=250"
    resp = requests.get(url, headers=headers)
    leads = resp.json().get('_embedded', {}).get('leads', [])
    
    found = 0
    for lead in leads:
        lead_id = lead['id']
        ev_url = f"{amocrm.base_url}/api/v4/leads/{lead_id}/events?filter[type]=lead_status_changed&limit=10"
        ev_resp = requests.get(ev_url, headers=headers)
        if ev_resp.status_code == 200:
            events = ev_resp.json().get('_embedded', {}).get('events', [])
            for ev in events:
                val_before = ev.get('value_before', [{}])[0]
                val_after = ev.get('value_after', [{}])[0]
                if val_before.get('pipeline_id') == 10117998:
                    print(f"Found migrated lead {lead_id}:")
                    print(json.dumps(ev, indent=2))
                    found += 1
                    break
        if found >= 3:
            break

if __name__ == '__main__':
    if os.name == 'nt':
        asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())
    asyncio.run(main())
