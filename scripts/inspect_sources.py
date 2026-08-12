import requests, json, os, sys
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
sample_ids = [48800976, 49305475, 48610170, 48832125]
for lid in sample_ids:
    url = f"{amocrm.base_url}/api/v4/leads/{lid}?with=source_id,contacts"
    resp = requests.get(url, headers=headers)
    if resp.status_code == 200:
        lead = resp.json()
        print(f"Lead ID: {lid}, Source ID: {lead.get('source_id')}")
        print(f"Name: {lead.get('name')}")
        
        # also check the chat endpoint to see if it's connected to a chat
        chat_url = f"{amocrm.base_url}/api/v4/leads/{lid}/links"
        c_resp = requests.get(chat_url, headers=headers)
        if c_resp.status_code == 200:
            print("Links:", json.dumps(c_resp.json(), indent=2))
        print('-'*20)
