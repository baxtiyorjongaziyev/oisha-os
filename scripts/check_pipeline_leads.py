import json
import sys
import io
import requests

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')

token = json.load(open('data/amocrm_token.json', 'r', encoding='utf-8'))
headers = {'Authorization': f"Bearer {token['access_token']}"}

# Check leads count per pipeline
pipelines = [11162698, 11295630, 11322658, 11162702]
for pid in pipelines:
    r = requests.get(f'https://jonbranding.amocrm.ru/api/v4/leads?filter[pipeline_id]={pid}&limit=10', headers=headers, timeout=15)
    if r.status_code == 200:
        data = r.json()
        leads = data.get('_embedded', {}).get('leads', [])
        print(f"Pipeline {pid}: Found {len(leads)} sample leads")
        for l in leads[:3]:
            print(f"  - Lead ID {l['id']}: {l['name']} (status {l['status_id']})")
    elif r.status_code == 204:
        print(f"Pipeline {pid}: Empty (204 No Content)")
    else:
        print(f"Pipeline {pid}: HTTP {r.status_code}")
