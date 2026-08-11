import requests, json, time, os, sys
from datetime import datetime, timedelta

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
    one_month_ago = int((datetime.now() - timedelta(days=30)).timestamp())
    
    # Get all sources to confirm their names if possible
    sources_resp = requests.get(f"{amocrm.base_url}/api/v4/sources", headers=headers)
    print("Sources text:", sources_resp.text[:500])

    ig_source_ids = [23507791, 23507789]
    leads_to_close = []
    page = 1
    while True:
        url = f'{amocrm.base_url}/api/v4/leads?filter[created_at][from]={one_month_ago}&with=source_id&limit=250&page={page}'
        resp = requests.get(url, headers=headers)
        if resp.status_code == 200:
            data = resp.json().get('_embedded', {}).get('leads', [])
            if not data:
                break
            for l in data:
                # If source is one of the instagram ones, and it's not already closed
                if l.get('source_id') in ig_source_ids and l['status_id'] != 143:
                    leads_to_close.append({
                        "id": l['id'],
                        "status_id": 143
                    })
            page += 1
        else:
            break
            
    print(f"Total IG leads to close: {len(leads_to_close)}")
    
    if leads_to_close:
        batch_size = 250
        for i in range(0, len(leads_to_close), batch_size):
            batch = leads_to_close[i:i+batch_size]
            patch_resp = requests.patch(f"{amocrm.base_url}/api/v4/leads", headers=headers, json=batch)
            if patch_resp.status_code in (200, 202):
                print(f"Batch {i//batch_size + 1} updated successfully.")
            else:
                print(f"Error updating batch {i//batch_size + 1}: {patch_resp.text}")

if __name__ == "__main__":
    main()
