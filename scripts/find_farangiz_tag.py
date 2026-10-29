import json
import sys
import io
import requests

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')

token = json.load(open('data/amocrm_token.json', 'r', encoding='utf-8'))
headers = {'Authorization': f"Bearer {token['access_token']}"}

# 1. Search leads with query 'farangiz'
print("Searching leads with query 'farangiz'...", flush=True)
r_leads = requests.get('https://jonbranding.amocrm.ru/api/v4/leads?query=farangiz&with=contacts,only_deleted', headers=headers, timeout=15)
print(f"Leads query status: {r_leads.status_code}", flush=True)
if r_leads.status_code == 200:
    leads = r_leads.json().get('_embedded', {}).get('leads', [])
    print(f"Found {len(leads)} leads by query")
    for l in leads:
        tags = [t['name'] for t in l.get('_embedded', {}).get('tags', []) or []]
        print(f"  Lead ID {l['id']}: '{l['name']}', tags: {tags}")

# 2. Search contacts with query 'farangiz'
print("\nSearching contacts with query 'farangiz'...", flush=True)
r_cnt = requests.get('https://jonbranding.amocrm.ru/api/v4/contacts?query=farangiz&with=leads', headers=headers, timeout=15)
print(f"Contacts query status: {r_cnt.status_code}", flush=True)
if r_cnt.status_code == 200:
    cnts = r_cnt.json().get('_embedded', {}).get('contacts', [])
    print(f"Found {len(cnts)} contacts by query")
    for c in cnts:
        tags = [t['name'] for t in c.get('_embedded', {}).get('tags', []) or []]
        print(f"  Contact ID {c['id']}: '{c['name']}', tags: {tags}")

# 3. Check tags endpoints
for entity in ['leads', 'contacts', 'companies']:
    r_tags = requests.get(f'https://jonbranding.amocrm.ru/api/v4/{entity}/tags?query=farangiz', headers=headers, timeout=10)
    print(f"\n{entity} tags search status: {r_tags.status_code}")
    if r_tags.status_code == 200:
        data = r_tags.json()
        tags = data.get('_embedded', {}).get('tags', [])
        print(f"  Found {len(tags)} tags in {entity}:")
        for t in tags:
            print(f"    Tag ID {t.get('id')}: '{t.get('name')}'")
