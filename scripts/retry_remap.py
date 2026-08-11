import os
import requests
import json
import time
from datetime import datetime, timedelta
from dotenv import load_dotenv

import sys
sys.path.insert(0, os.path.abspath('.'))
from src.services.core.crm.amocrm_sync import AmoCRMSync
from src.settings import settings

OLD_STATUS_MAP = {
    80178214: {"name": "Неразобранное", "new_pipe": 11162698, "new_stat": 87609514},
    87192054: {"name": "Yangi so'rov", "new_pipe": 11162698, "new_stat": 87609514},
    80178222: {"name": "Muloqot boshlandi", "new_pipe": 11162698, "new_stat": 87609518},
    86306478: {"name": "Brief & Ehtiyoj aniqlandi", "new_pipe": 11162698, "new_stat": 87609522},
    80178218: {"name": "Uchrashuv & Brief o'tdi", "new_pipe": 11162702, "new_stat": 87609534},
    86306482: {"name": "KP & Prezentatsiya berildi", "new_pipe": 11162702, "new_stat": 87609538},
    86306490: {"name": "Muzokara & Shartnoma", "new_pipe": 11162702, "new_stat": 87609542},
    86306494: {"name": "Avans olindi", "new_pipe": 11162702, "new_stat": 87609550},
}

def main():
    load_dotenv()
    amocrm = AmoCRMSync(
        subdomain=settings.AMOCRM_SUBDOMAIN,
        client_id=settings.AMOCRM_CLIENT_ID,
        client_secret=settings.AMOCRM_CLIENT_SECRET,
        redirect_url=settings.AMOCRM_REDIRECT_URL,
    )
    headers = amocrm._get_headers()
    
    print("Fetching leads that are STILL in 143 from old pipeline...", flush=True)
    leads = []
    page = 1
    while True:
        url = f"{amocrm.base_url}/api/v4/leads?filter[statuses][0][pipeline_id]=10117998&limit=250&page={page}"
        resp = requests.get(url, headers=headers)
        if resp.status_code == 200:
            data = resp.json().get('_embedded', {}).get('leads', [])
            leads.extend(data)
            if len(data) < 250:
                break
            page += 1
        else:
            break
            
    # Filter ONLY those in 143 right now updated today
    one_day_ago = int((datetime.now() - timedelta(days=1)).timestamp())
    victims = [l for l in leads if l['updated_at'] > one_day_ago and l['status_id'] == 143]
    
    print(f"Remaining victims to process: {len(victims)}", flush=True)
    
    updates = []
    
    for idx, lead in enumerate(victims):
        lead_id = lead['id']
        events_url = f"{amocrm.base_url}/api/v4/events?filter[entity]=lead&filter[entity_id][]={lead_id}&filter[type]=lead_status_changed&limit=100"
        ev_resp = requests.get(events_url, headers=headers)
        if ev_resp.status_code == 200:
            events = ev_resp.json().get('_embedded', {}).get('events', [])
            
            target_status = None
            for ev in events:
                val_before = ev.get('value_before', [{}])[0].get('lead_status', {})
                if val_before.get('pipeline_id') == 10117998:
                    old_status = val_before.get('id')
                    if old_status in OLD_STATUS_MAP:
                        target_status = OLD_STATUS_MAP[old_status]
                        break
            
            if target_status:
                updates.append({
                    "id": lead_id,
                    "pipeline_id": target_status['new_pipe'],
                    "status_id": target_status['new_stat']
                })
        time.sleep(0.15)
                    
    print(f"Updates to push: {len(updates)}", flush=True)
    
    if updates:
        batch_size = 250
        for i in range(0, len(updates), batch_size):
            batch = updates[i:i+batch_size]
            patch_url = f"{amocrm.base_url}/api/v4/leads"
            patch_resp = requests.patch(patch_url, headers=headers, json=batch)
            if patch_resp.status_code in (200, 202):
                print(f"Batch {i//batch_size + 1} updated successfully.", flush=True)
            else:
                print(f"Error updating batch {i//batch_size + 1}: {patch_resp.text}", flush=True)

if __name__ == '__main__':
    main()
