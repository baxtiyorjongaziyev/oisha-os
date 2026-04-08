import asyncio
import logging
import sys
import requests
from collections import defaultdict

project_dir = r"c:\Users\baxti\.gemini\antigravity\playground\oisha-os"
sys.path.append(project_dir)

import settings
import amocrm_sync

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger("task_audit")

async def check_duplicate_tasks():
    amocrm = amocrm_sync.AmoCRMSync(
        subdomain=settings.settings.AMOCRM_SUBDOMAIN,
        client_id=settings.settings.AMOCRM_CLIENT_ID,
        client_secret=settings.settings.AMOCRM_CLIENT_SECRET.get_secret_value() if settings.settings.AMOCRM_CLIENT_SECRET else None,
        redirect_url=settings.settings.AMOCRM_REDIRECT_URL
    )
    
    amocrm._load_token()
    headers = amocrm._get_headers()
    
    logger.info("Fetching active tasks...")
    url = f"{amocrm.base_url}/api/v4/tasks?filter[is_completed]=0&limit=200"
    res = requests.get(url, headers=headers)
    
    if res.status_code == 200:
        tasks = res.json().get("_embedded", {}).get("tasks", [])
        logger.info(f"Total active tasks fetched: {len(tasks)}")
        
        # Group tasks by lead ID
        lead_tasks = defaultdict(list)
        for t in tasks:
            if t.get('entity_type') == 'leads':
                lead_tasks[t.get('entity_id')].append({
                    "id": t.get("id"),
                    "text": t.get("text"),
                    "created_at": t.get("created_at")
                })
        
        duplicate_count = 0
        for lead_id, tasks_for_lead in lead_tasks.items():
            if len(tasks_for_lead) > 1:
                # further check if text matches exactly
                texts = [t['text'].strip() for t in tasks_for_lead]
                if len(texts) != len(set(texts)):
                    logger.warning(f"DUPLICATE TASKS FOUND for Lead ID: {lead_id}")
                    for t in tasks_for_lead:
                        logger.warning(f"  - Task ID: {t['id']}, Text: '{t['text']}'")
                    duplicate_count += 1
                else:
                    logger.info(f"Multiple UNIQUE tasks for Lead ID: {lead_id}. Count: {len(tasks_for_lead)}")
        
        if duplicate_count == 0:
            logger.info("Great! No duplicate active tasks found for any leads.")
        else:
            logger.warning(f"Found {duplicate_count} leads with duplicate tasks.")
            
    else:
        logger.error(f"Failed to fetch tasks: {res.status_code} - {res.text}")

if __name__ == "__main__":
    asyncio.run(check_duplicate_tasks())
