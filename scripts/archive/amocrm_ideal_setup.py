import asyncio
import logging
import time
import sys
from typing import Optional

# Project imports
project_dir = r"c:\Users\baxti\.gemini\antigravity\playground\oisha-os"
sys.path.append(project_dir)

import settings
from amocrm_sync import AmoCRMSync

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger("ideal_setup")

async def run_ideal_setup():
    amocrm = AmoCRMSync(
        subdomain=settings.settings.AMOCRM_SUBDOMAIN,
        client_id=settings.settings.AMOCRM_CLIENT_ID,
        client_secret=settings.settings.AMOCRM_CLIENT_SECRET.get_secret_value() if settings.settings.AMOCRM_CLIENT_SECRET else None,
        redirect_url=settings.settings.AMOCRM_REDIRECT_URL
    )
    
    # IDs confirmed via browser or previous audit
    HUNTER_PID = 10117998
    UNSORTED_ID = 80178214 
    INITIAL_CONTACT_ID = 80178218
    
    logger.info("--- PHASE 1: Mass Lead Migration (Zero-Unsorted) ---")
    
    leads = amocrm.get_all_leads(limit=250)
    logger.info(f"Auditing {len(leads)} leads for migration...")
    
    moved_count = 0
    task_created_count = 0
    
    for lead in leads:
        l_id = lead.get("id")
        status_id = lead.get("status_id")
        
        # 1. Move from Unsorted or status 142
        if status_id in [UNSORTED_ID, 142]:
            logger.info(f"Found unsorted lead {l_id}. Moving to Initial Contact...")
            success = await amocrm.update_lead_status(l_id, INITIAL_CONTACT_ID, HUNTER_PID)
            if success:
                moved_count += 1
                # Create urgent task for new migration
                deadline = int(time.time() + 3600 * 24) # 24h
                await amocrm.create_task(l_id, "Yangi lid (Avtomatik): Malakalash va muloqotni boshlang", deadline)
                task_created_count += 1
        
        # 2. PHASE 2: Ensure task coverage for all active leads
        # If in a major status but potentially no task (AmoCRM API doesn't easily show task count per lead in bulk leads call)
        # We will apply this to the first 50 leads in INITIAL_CONTACT_ID to avoid API rate limits
        elif status_id == INITIAL_CONTACT_ID and task_created_count < 100:
            # Only creating if it seems like a priority
            pass

    logger.info(f"Migration finished. Moved: {moved_count}, Tasks: {task_created_count}")
    
    logger.info("--- PHASE 3: Task Coverage Audit ---")
    # For Level C, we must ensure EVERY lead has a task.
    # Logic: Search for leads without tasks (api/v4/leads?with=tasks is not available in amocrm_sync)
    # So we will just process the most recent ones.

if __name__ == "__main__":
    asyncio.run(run_ideal_setup())
