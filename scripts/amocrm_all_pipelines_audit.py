import asyncio
import logging
import sys
import requests

project_dir = r"c:\Users\baxti\.gemini\antigravity\playground\oisha-os"
sys.path.append(project_dir)

import settings
import amocrm_sync

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger("all_pipelines_audit")

async def get_all_pipelines():
    amocrm = amocrm_sync.AmoCRMSync(
        subdomain=settings.settings.AMOCRM_SUBDOMAIN,
        client_id=settings.settings.AMOCRM_CLIENT_ID,
        client_secret=settings.settings.AMOCRM_CLIENT_SECRET.get_secret_value() if settings.settings.AMOCRM_CLIENT_SECRET else None,
        redirect_url=settings.settings.AMOCRM_REDIRECT_URL
    )
    
    amocrm._load_token()
    headers = amocrm._get_headers()
    
    url = f"{amocrm.base_url}/api/v4/leads/pipelines"
    res = requests.get(url, headers=headers)
    if res.status_code == 200:
        pipelines = res.json().get("_embedded", {}).get("pipelines", [])
        for p in pipelines:
            name = p.get("name")
            p_id = p.get("id")
            logger.info(f"PIPELINE: {name} (ID: {p_id})")
            statuses = p.get("_embedded", {}).get("statuses", [])
            for s in statuses:
                logger.info(f"  - Stage: {s.get('name')} (ID: {s.get('id')})")
    else:
        logger.error(f"Failed to fetch pipelines: {res.status_code}")

if __name__ == "__main__":
    asyncio.run(get_all_pipelines())
