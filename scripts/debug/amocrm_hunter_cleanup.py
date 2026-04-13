import asyncio
import logging
import sys
import requests

project_dir = r"c:\Users\baxti\.gemini\antigravity\playground\oisha-os"
sys.path.append(project_dir)

import settings
import amocrm_sync

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger("hunter_cleanup")

async def delete_duplicate():
    amocrm = amocrm_sync.AmoCRMSync(
        subdomain=settings.settings.AMOCRM_SUBDOMAIN,
        client_id=settings.settings.AMOCRM_CLIENT_ID,
        client_secret=settings.settings.AMOCRM_CLIENT_SECRET.get_secret_value() if settings.settings.AMOCRM_CLIENT_SECRET else None,
        redirect_url=settings.settings.AMOCRM_REDIRECT_URL
    )
    
    amocrm._load_token()
    headers = amocrm._get_headers()
    
    pipeline_id = 10117998
    statuses_to_delete = [81332478, 81518994]  # Duplicate "Bog'lanib bo'lmadi" & "Qayta aloqa"
    
    for sid in statuses_to_delete:
        logger.info(f"Deleting status {sid}...")
        url = f"{amocrm.base_url}/api/v4/leads/pipelines/{pipeline_id}/statuses/{sid}"
        res = requests.delete(url, headers=headers)
        if res.status_code == 204:
            logger.info(f"Successfully deleted status {sid}")
        else:
            logger.error(f"Failed to delete {sid}: {res.status_code} - {res.text}")

if __name__ == "__main__":
    asyncio.run(delete_duplicate())
