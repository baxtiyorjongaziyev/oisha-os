import asyncio
import logging
import sys
import requests

project_dir = r"c:\Users\baxti\.gemini\antigravity\playground\oisha-os"
sys.path.append(project_dir)

import settings
import amocrm_sync

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger("sifat_nazorati_setup")

async def setup_pipelines():
    amocrm = amocrm_sync.AmoCRMSync(
        subdomain=settings.settings.AMOCRM_SUBDOMAIN,
        client_id=settings.settings.AMOCRM_CLIENT_ID,
        client_secret=settings.settings.AMOCRM_CLIENT_SECRET.get_secret_value() if settings.settings.AMOCRM_CLIENT_SECRET else None,
        redirect_url=settings.settings.AMOCRM_REDIRECT_URL
    )
    
    amocrm._load_token()
    headers = amocrm._get_headers()
    
    # 1. Delete "After-sales (1-oy)" (ID: 84672994) from "Farmer bosqichlari" (ID: 10123318)
    farmer_pipeline_id = 10123318
    status_to_delete = 84672994
    logger.info(f"Removing After-sales stage {status_to_delete} from Farmer pipeline...")
    del_url = f"{amocrm.base_url}/api/v4/leads/pipelines/{farmer_pipeline_id}/statuses/{status_to_delete}"
    res_del = requests.delete(del_url, headers=headers)
    if res_del.status_code == 204:
        logger.info("Successfully deleted After-sales from Farmer.")
    else:
        logger.warning(f"Failed to delete (or already deleted): {res_del.status_code} - {res_del.text}")
        
    # 2. Rename statuses in "Sifat Nazorati bosqichlari" (ID: 10427390)
    sifat_pipeline_id = 10427390
    
    logger.info("Updating Sifat Nazorati pipeline...")
    # Use the correct endpoint for updating a single pipeline
    url = f"{amocrm.base_url}/api/v4/leads/pipelines/{sifat_pipeline_id}"
    
    payload = {
        "name": "Sifat Nazorati bosqichlari",
        "_embedded": {
            "statuses": [
                {"id": 82391146, "name": "NPS / Fikr olish", "color": "#fffd7f"},
                {"id": 82391150, "name": "1-oy Cross-sell", "color": "#f9cbba"},
                {"id": 82391154, "name": "LTV / Doimiy mijoz", "color": "#e6e8ea"}
            ]
        }
    }
    
    res = requests.patch(url, headers=headers, json=payload)
    if res.status_code == 200:
        logger.info("Successfully renamed Sifat Nazorati stages!")
    else:
        logger.error(f"Failed to update stages: {res.status_code} - {res.text}")

if __name__ == "__main__":
    asyncio.run(setup_pipelines())
