import requests, json, sys, os
from datetime import datetime, timedelta

sys.path.insert(0, os.path.abspath('.'))
from src.settings import settings
from src.services.core.crm.amocrm_sync import AmoCRMSync

def is_junk_name(name):
    lower_name = str(name).lower()
    junk_keywords = ['test', 'тест', 'spam', 'спам', '123', 'qwe', 'asd']
    for kw in junk_keywords:
        if kw in lower_name:
            return True
    return False

def main():
    amocrm = AmoCRMSync(
        subdomain=settings.AMOCRM_SUBDOMAIN,
        client_id=settings.AMOCRM_CLIENT_ID,
        client_secret=settings.AMOCRM_CLIENT_SECRET,
        redirect_url=settings.AMOCRM_REDIRECT_URL,
    )
    headers = amocrm._get_headers()
    thirty_days_ago = int((datetime.now() - timedelta(days=30)).timestamp())
    
    leads_to_tag = []
    page = 1
    
    print("Fetching active leads and analyzing...")
    while True:
        url = f'{amocrm.base_url}/api/v4/leads?with=contacts&limit=250&page={page}'
        resp = requests.get(url, headers=headers)
        if resp.status_code == 200:
            data = resp.json().get('_embedded', {}).get('leads', [])
            if not data:
                break
            
            for l in data:
                if l['status_id'] in (142, 143):
                    continue
                
                is_junk = False
                
                if is_junk_name(l.get('name', '')):
                    is_junk = True
                
                contacts = l.get('_embedded', {}).get('contacts', [])
                if not contacts:
                    is_junk = True
                
                if l['status_id'] in (87609514, 87609510) and l['created_at'] < thirty_days_ago:
                    is_junk = True
                
                if is_junk:
                    # Get existing tags
                    existing_tags = []
                    for t in l.get('_embedded', {}).get('tags', []):
                        existing_tags.append({"id": t["id"]}) # or just name
                    
                    # Add our new tag
                    existing_tags.append({"name": "Keraksiz (Junk)"})
                    
                    leads_to_tag.append({
                        'id': l['id'],
                        '_embedded': {
                            'tags': existing_tags
                        }
                    })
            page += 1
        else:
            break
            
    print(f"Total JUNK leads identified: {len(leads_to_tag)}")
    
    if leads_to_tag:
        print("Adding 'Keraksiz (Junk)' tag...")
        batch_size = 250
        for i in range(0, len(leads_to_tag), batch_size):
            batch = leads_to_tag[i:i+batch_size]
            patch_resp = requests.patch(f"{amocrm.base_url}/api/v4/leads", headers=headers, json=batch)
            if patch_resp.status_code in (200, 202):
                print(f"Batch {i//batch_size + 1} tagged successfully.")
            else:
                print(f"Error updating batch {i//batch_size + 1}: {patch_resp.text}")

if __name__ == "__main__":
    main()
