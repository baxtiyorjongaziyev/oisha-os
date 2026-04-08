import asyncio
import logging
import sys
import time
from typing import Optional, List

# Project root
project_dir = r"c:\Users\baxti\.gemini\antigravity\playground\oisha-os"
sys.path.append(project_dir)

import settings
import amocrm_sync

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger("task_coverage")

async def ensure_task_coverage():
    amocrm = amocrm_sync.AmoCRMSync(
        subdomain=settings.settings.AMOCRM_SUBDOMAIN,
        client_id=settings.settings.AMOCRM_CLIENT_ID,
        client_secret=settings.settings.AMOCRM_CLIENT_SECRET.get_secret_value() if settings.settings.AMOCRM_CLIENT_SECRET else None,
        redirect_url=settings.settings.AMOCRM_REDIRECT_URL
    )
    
    amocrm._load_token()
    
    logger.info("Starting Task Coverage Audit for Hunter Pipeline...")
    
    # Get leads from Hunter pipeline
    # Statuses: 80178218 (Initial), 80178222 (Qualified), 80178226 (Interested), 80178230 (Meeting)
    active_statuses = [80178218, 80178222, 80178226, 80178230]
    
    total_leads_processed = 0
    tasks_created = 0
    
    for status_id in active_statuses:
        leads = amocrm.get_all_leads(limit=250) # In real scenario we check by status. amocrm_sync filter by status needed.
        # But get_all_leads fetches recent leads across all.
        
        for lead in leads:
            l_id = lead.get("id")
            s_id = lead.get("status_id")
            
            if s_id == status_id:
                total_leads_processed += 1
                # AmoCRM API check for existing tasks on a lead:
                # GET /api/v4/tasks?filter[entity_id]=lead_id
                t_url = f"{amocrm.base_url}/api/v4/tasks"
                params = {"filter[entity_id]": l_id, "filter[is_completed]": 0}
                import requests
                t_resp = requests.get(t_url, headers=amocrm._get_headers(), params=params)
                
                has_task = False
                if t_resp.status_code == 200:
                    tasks = t_resp.json().get("_embedded", {}).get("tasks", [])
                    if tasks:
                        has_task = True
                
                if not has_task:
                    logger.info(f"Lead {l_id} has NO active task. Creating one...")
                    deadline = int(time.time() + 3600 * 4) # 4 soat ichida
                    await amocrm.create_task(l_id, "Level C Nazorati: Navbatdagi qadamni aniqlang", deadline)
                    tasks_created += 1
                
                if tasks_created >= 50: # Limit to avoid rate limiting or too many notifications at once
                    logger.info("Reached batch limit of 50 tasks.")
                    break
        if tasks_created >= 50: break

    logger.info(f"Task Coverage Finished. Leads checked: {total_leads_processed}, Tasks created: {tasks_created}")

if __name__ == "__main__":
    asyncio.run(ensure_task_coverage())
