import asyncio
import logging
import os
import sys
import time
from typing import Optional

# Project imports
project_dir = r"c:\Users\baxti\.gemini\antigravity\playground\oisha-os"
sys.path.append(project_dir)

import settings
from amocrm_sync import AmoCRMSync

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger("cleanup")

async def level_c_cleanup():
    amocrm = AmoCRMSync(
        subdomain=settings.settings.AMOCRM_SUBDOMAIN,
        client_id=settings.settings.AMOCRM_CLIENT_ID,
        client_secret=settings.settings.AMOCRM_CLIENT_SECRET.get_secret_value() if settings.settings.AMOCRM_CLIENT_SECRET else None,
        redirect_url=settings.settings.AMOCRM_REDIRECT_URL
    )
    
    # Hunter Pipeline IDs
    PID = 10117998
    UNSORTED_ID = 142 
    INITIAL_CONTACT_ID = 80178218
    
    logger.info("Starting Level C Cleanup...")

    leads = amocrm.get_all_leads(limit=250)
    logger.info(f"Found {len(leads)} leads to audit.")
    
    moved_count = 0
    task_created_count = 0
    
    for lead in leads:
        l_id = lead.get("id")
        status_id = lead.get("status_id")
        
        # Unsorted -> Initial Contact
        if status_id == UNSORTED_ID:
            logger.info(f"Moving lead {l_id} from Unsorted to Initial Contact...")
            await amocrm.update_lead_status(l_id, INITIAL_CONTACT_ID, PID)
            moved_count += 1
        
        # Ensure task for Initial Contact
        if status_id == INITIAL_CONTACT_ID:
            deadline = int(time.time() + 86400) 
            await amocrm.create_task(l_id, "Level C Audit: Aloqaga chiqing va malakalang", deadline)
            task_created_count += 1

    logger.info(f"Cleanup finished. Moved: {moved_count}, Tasks created: {task_created_count}")

if __name__ == "__main__":
    asyncio.run(level_c_cleanup())
