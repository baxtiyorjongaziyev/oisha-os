import requests, json, time
from datetime import datetime, timedelta
import os
import sys

sys.path.insert(0, os.path.abspath('.'))
from src.settings import settings
from src.services.core.crm.amocrm_sync import AmoCRMSync

def main():
    amocrm = AmoCRMSync(
        subdomain=settings.AMOCRM_SUBDOMAIN,
        client_id=settings.AMOCRM_CLIENT_ID,
        client_secret=settings.AMOCRM_CLIENT_SECRET,
        redirect_url=settings.AMOCRM_REDIRECT_URL,
    )
    headers = amocrm._get_headers()

    # 1 month ago
    one_month_ago = int((datetime.now() - timedelta(days=30)).timestamp())

    url = f'{amocrm.base_url}/api/v4/leads?filter[created_at][from]={one_month_ago}&limit=250'
    resp = requests.get(url, headers=headers)
    if resp.status_code == 200:
        leads = resp.json().get('_embedded', {}).get('leads', [])
        
        ig_leads = []
        page = 1
        while True:
            url = f'{amocrm.base_url}/api/v4/leads?filter[created_at][from]={one_month_ago}&with=source_id&limit=250&page={page}'
            resp = requests.get(url, headers=headers)
            if resp.status_code == 200:
                data = resp.json().get('_embedded', {}).get('leads', [])
                if not data:
                    break
                for l in data:
                    if l.get('source_id') is not None:
                        print(f"Lead {l['id']} has source_id: {l['source_id']}")
                        ig_leads.append(l)
                page += 1
            else:
                break
        
        print(f"Total leads with source_id in the last month: {len(ig_leads)}")




if __name__ == "__main__":
    main()
