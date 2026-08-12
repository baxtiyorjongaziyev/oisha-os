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
    
    # Calculate timestamps
    thirty_days_ago = int((datetime.now() - timedelta(days=30)).timestamp())
    
    junk_leads = []
    reasons_count = {'bad_name': 0, 'no_contact': 0, 'stale_new': 0}
    
    page = 1
    total_checked = 0
    
    print("Fetching active leads to identify junk...")
    while True:
        # Fetch leads that are NOT closed (exclude status 142, 143)
        # However, filter by active statuses might be tricky in v4 without listing all.
        # We can just fetch all and filter in memory, or use filter[statuses].
        url = f'{amocrm.base_url}/api/v4/leads?with=contacts&limit=250&page={page}'
        resp = requests.get(url, headers=headers)
        if resp.status_code == 200:
            data = resp.json().get('_embedded', {}).get('leads', [])
            if not data:
                break
            
            for l in data:
                total_checked += 1
                
                # Skip already closed
                if l['status_id'] in (142, 143):
                    continue
                
                is_junk = False
                reasons = []
                
                # 1. Check for bad names
                if is_junk_name(l.get('name', '')):
                    is_junk = True
                    reasons.append("Shubhali ism (Test/Spam)")
                    reasons_count['bad_name'] += 1
                
                # 2. Check for missing contacts
                contacts = l.get('_embedded', {}).get('contacts', [])
                if not contacts:
                    is_junk = True
                    reasons.append("Kontakt biriktirilmagan")
                    reasons_count['no_contact'] += 1
                
                # 3. Stale in new status
                # 87609514 is "Yangi so'rov" in PRESALES, 87609510 is "Неразобранное"
                if l['status_id'] in (87609514, 87609510) and l['created_at'] < thirty_days_ago:
                    is_junk = True
                    reasons.append("1 oydan beri 'Yangi' bosqichida qolib ketgan")
                    reasons_count['stale_new'] += 1
                
                if is_junk:
                    junk_leads.append({
                        'id': l['id'],
                        'name': l.get('name'),
                        'status_id': l['status_id'],
                        'reasons': ", ".join(reasons)
                    })
                    
            page += 1
        else:
            break
            
    print(f"\nTotal checked leads: {total_checked}")
    print(f"Total JUNK leads identified: {len(junk_leads)}\n")
    print("Breakdown of reasons:")
    print(f" - Shubhali ism (Test/Spam): {reasons_count['bad_name']}")
    print(f" - Kontakt biriktirilmagan: {reasons_count['no_contact']}")
    print(f" - 1 oydan beri harakatsiz: {reasons_count['stale_new']}")
    
    print("\nSample junk leads (top 10):")
    for jl in junk_leads[:10]:
        print(f"ID: {jl['id']} | Nomi: {jl['name']} | Sabab: {jl['reasons']}")

if __name__ == "__main__":
    main()
