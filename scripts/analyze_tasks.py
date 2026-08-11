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
    
    # PRESALES Pipeline ID
    presales_id = 11162698
    
    leads_url = f"{amocrm.base_url}/api/v4/leads?filter[statuses][0][pipeline_id]={presales_id}&limit=250"
    resp = requests.get(leads_url, headers=headers)
    if resp.status_code != 200:
        print(f"Xatolik: {resp.text}")
        return
        
    leads = resp.json().get('_embedded', {}).get('leads', [])
    print(f"Total leads fetched: {len(leads)}")
    
    task_samples = []
    
    # Loop through all leads
    has_tasks_count = 0
    for lead in leads:
        lead_id = lead['id']
        print(f"Checking tasks for lead {lead_id}...")
        tasks_url = f"{amocrm.base_url}/api/v4/tasks?filter[entity_type]=leads&filter[entity_id]={lead_id}&filter[is_completed]=0"
        task_resp = requests.get(tasks_url, headers=headers)
        
        if task_resp.status_code == 200:
            tasks = task_resp.json().get('_embedded', {}).get('tasks', [])
            for t in tasks:
                has_tasks_count += 1
                task_samples.append({
                    "lead_id": lead_id,
                    "task_id": t['id'],
                    "text": t.get('text', ''),
                    "task_type_id": t.get('task_type_id')
                })

    print(f"Total leads with tasks: {has_tasks_count}")
    print("--- TASK SAMPLES ---")
    for s in task_samples[:50]:
        print(s)

if __name__ == '__main__':
    if os.name == 'nt':
        asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())
    asyncio.run(main())
