import json
import sys
import io
import requests

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')

token = json.load(open('data/amocrm_token.json', 'r', encoding='utf-8'))
headers = {'Authorization': f"Bearer {token['access_token']}"}

# 1. Fetch leads with tag 363339 or 'farangiz'
# In amoCRM v4: GET /api/v4/leads?filter[tags]=363339 or filter[tags][]=363339
print("Checking leads with tag 363339...", flush=True)
for param in ['filter[tags]=363339', 'filter[tags][]=363339', 'filter[tags]=farangiz']:
    r = requests.get(f'https://jonbranding.amocrm.ru/api/v4/leads?{param}&with=contacts', headers=headers, timeout=10)
    print(f"  {param}: status {r.status_code}", flush=True)
    if r.status_code == 200:
        leads = r.json().get('_embedded', {}).get('leads', [])
        print(f"    Found {len(leads)} leads")
        for l in leads:
            tags = [t['name'] for t in l.get('_embedded', {}).get('tags', []) or []]
            print(f"      Lead ID {l['id']}: '{l['name']}', tags: {tags}")

# 2. Fetch contacts with tag 365737 or 'farangiz'
print("\nChecking contacts with tag 365737...", flush=True)
for param in ['filter[tags]=365737', 'filter[tags][]=365737', 'filter[tags]=farangiz']:
    r = requests.get(f'https://jonbranding.amocrm.ru/api/v4/contacts?{param}&with=leads', headers=headers, timeout=10)
    print(f"  {param}: status {r.status_code}", flush=True)
    if r.status_code == 200:
        cnts = r.json().get('_embedded', {}).get('contacts', [])
        print(f"    Found {len(cnts)} contacts")
        for c in cnts:
            tags = [t['name'] for t in c.get('_embedded', {}).get('tags', []) or []]
            print(f"      Contact ID {c['id']}: '{c['name']}', tags: {tags}")

# 3. Check companies with tag 365737 or 'farangiz'
print("\nChecking companies with tag 365737...", flush=True)
for param in ['filter[tags]=365737', 'filter[tags][]=365737', 'filter[tags]=farangiz']:
    r = requests.get(f'https://jonbranding.amocrm.ru/api/v4/companies?{param}', headers=headers, timeout=10)
    print(f"  {param}: status {r.status_code}", flush=True)
    if r.status_code == 200:
        comps = r.json().get('_embedded', {}).get('companies', [])
        print(f"    Found {len(comps)} companies")
        for c in comps:
            tags = [t['name'] for t in c.get('_embedded', {}).get('tags', []) or []]
            print(f"      Company ID {c['id']}: '{c['name']}', tags: {tags}")
