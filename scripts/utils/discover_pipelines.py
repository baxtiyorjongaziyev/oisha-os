import asyncio
import json
import logging
import requests
from src.services.amocrm_sync import AmoCRMSync
from src.settings import settings

logging.basicConfig(level=logging.INFO)

async def list_pipelines():
    amo = AmoCRMSync(
        subdomain=settings.AMOCRM_SUBDOMAIN,
        client_id=settings.AMOCRM_CLIENT_ID,
        client_secret=settings.AMOCRM_CLIENT_SECRET.get_secret_value() if settings.AMOCRM_CLIENT_SECRET else None,
        redirect_url=settings.AMOCRM_REDIRECT_URL
    )
    amo._load_token()
    
    url = f"{amo.base_url}/api/v4/leads/pipelines"
    resp = requests.get(url, headers=amo._get_headers())
    if resp.status_code == 200:
        pipelines = resp.json().get("_embedded", {}).get("pipelines", [])
        for p in pipelines:
            print(f"Pipeline: {p['name']} (ID: {p['id']})")
            for s in p.get("_embedded", {}).get("statuses", []):
                print(f"  - Status: {s['name']} (ID: {s['id']})")
    else:
        print(f"Error: {resp.status_code} - {resp.text}")

if __name__ == "__main__":
    asyncio.run(list_pipelines())
