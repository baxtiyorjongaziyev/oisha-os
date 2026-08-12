import os, requests, json
from src.settings import settings
from src.services.core.crm.amocrm_sync import AmoCRMSync
amocrm=AmoCRMSync(subdomain=settings.AMOCRM_SUBDOMAIN, client_id=settings.AMOCRM_CLIENT_ID, client_secret=settings.AMOCRM_CLIENT_SECRET, redirect_url=settings.AMOCRM_REDIRECT_URL)
headers = amocrm._get_headers()
leads = []
for p in range(1, 10):
    url = f"{amocrm.base_url}/api/v4/leads?filter[statuses][0][pipeline_id]=11162698&page={p}&limit=250"
    resp = requests.get(url, headers=headers)
    if resp.status_code == 200:
        leads.extend(resp.json().get('_embedded', {}).get('leads', []))
    else: break
print(f"Total leads in PRESALES: {len(leads)}")
if leads:
    statuses = {}
    for l in leads:
        st = l['status_id']
        statuses[st] = statuses.get(st, 0) + 1
    print("Status distribution:", statuses)
