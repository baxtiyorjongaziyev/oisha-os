import json
import sys
import io
import requests

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')

token = json.load(open('data/amocrm_token.json', 'r', encoding='utf-8'))
headers = {'Authorization': f"Bearer {token['access_token']}"}

# Fetch all leads in pipeline 11322658 (UTC)
page = 1
utc_leads = []
while True:
    r = requests.get(f'https://jonbranding.amocrm.ru/api/v4/leads?filter[pipeline_id]=11322658&limit=250&page={page}', headers=headers, timeout=15)
    if r.status_code == 200:
        data = r.json()
        leads = data.get('_embedded', {}).get('leads', [])
        utc_leads.extend(leads)
        if len(leads) < 250:
            break
        page += 1
    elif r.status_code == 204:
        break
    else:
        print(f"Error {r.status_code}")
        break

print(f"Total leads in UTC pipeline (11322658): {len(utc_leads)}")
status_counts = {}
for l in utc_leads:
    s = l['status_id']
    status_counts[s] = status_counts.get(s, 0) + 1
print("Status counts:", status_counts)

# Also check active leads or tags in 11322658
for l in utc_leads[:15]:
    tags = [t['name'] for t in l.get('_embedded', {}).get('tags', [])]
    print(f"ID={l['id']}, Status={l['status_id']}, Name={l['name']}, Tags={tags}")
