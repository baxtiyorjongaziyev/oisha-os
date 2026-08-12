import requests, json, sys, os
sys.path.insert(0, os.path.abspath('.'))
from src.settings import settings
from src.services.core.crm.amocrm_sync import AmoCRMSync

amocrm = AmoCRMSync(
    subdomain=settings.AMOCRM_SUBDOMAIN,
    client_id=settings.AMOCRM_CLIENT_ID,
    client_secret=settings.AMOCRM_CLIENT_SECRET,
    redirect_url=settings.AMOCRM_REDIRECT_URL,
)
headers = amocrm._get_headers()
url = f'{amocrm.base_url}/api/v4/leads/48768000'
resp = requests.get(url, headers=headers)
lead = resp.json()
print(f'Current pipeline: {lead.get("pipeline_id")}')
patch_data = [{'id': lead['id'], 'status_id': 143, 'pipeline_id': lead['pipeline_id']}]
patch_resp = requests.patch(f'{amocrm.base_url}/api/v4/leads', headers=headers, json=patch_data)
print('Patch response:', patch_resp.status_code, patch_resp.text)
