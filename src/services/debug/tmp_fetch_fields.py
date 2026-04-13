import asyncio
import logging
import sys
import os
import json

# Project root
project_dir = r"c:\Users\baxti\.gemini\antigravity\playground\oisha-os"
sys.path.append(project_dir)

import settings
from amocrm_sync import AmoCRMSync

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger("field_audit")

async def fetch_field_ids():
    amocrm = AmoCRMSync(
        subdomain=settings.settings.AMOCRM_SUBDOMAIN,
        client_id=settings.settings.AMOCRM_CLIENT_ID,
        client_secret=settings.settings.AMOCRM_CLIENT_SECRET.get_secret_value() if settings.settings.AMOCRM_CLIENT_SECRET else None,
        redirect_url=settings.settings.AMOCRM_REDIRECT_URL
    )
    
    # Load token
    amocrm._load_token()
    
    # Try to refresh token if needed
    if not amocrm.access_token:
        logger.error("No access token found.")
        return

    # Get custom fields for leads
    url = f"{amocrm.base_url}/api/v4/leads/custom_fields"
    
    import requests
    resp = requests.get(url, headers=amocrm._get_headers())
    
    if resp.status_code == 401:
        logger.info("Token expired, refreshing...")
        if amocrm.refresh_token():
             resp = requests.get(url, headers=amocrm._get_headers())

    if resp.status_code == 200:
        fields = resp.json().get("_embedded", {}).get("custom_fields", [])
        logger.info(f"Found {len(fields)} custom fields.")
        results = []
        for field in fields:
            name = field.get("name")
            f_id = field.get("id")
            if "AI" in name or "ehtiyoj" in name or "Budjet" in name:
                logger.info(f"Field Found: '{name}' (ID: {f_id})")
                results.append({"name": name, "id": f_id})
        
        with open("amocrm_fields_audit.json", "w") as f:
            json.dump(results, f, indent=4)
    else:
        logger.error(f"Error fetching fields: {resp.status_code} - {resp.text}")

if __name__ == "__main__":
    asyncio.run(fetch_field_ids())
