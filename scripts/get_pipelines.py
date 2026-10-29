import json
import sys
import requests

sys.stdout.reconfigure(encoding='utf-8')

with open('data/amocrm_token.json') as f:
    tok = json.load(f)['access_token']
headers = {'Authorization': f'Bearer {tok}'}
r = requests.get('https://jonbranding.amocrm.ru/api/v4/leads/pipelines', headers=headers)
print('Status:', r.status_code, flush=True)
for p in r.json().get('_embedded', {}).get('pipelines', []):
    print(f"\nPipeline: {p['name']} (id={p['id']})", flush=True)
    for s in p.get('_embedded', {}).get('statuses', []):
        print(f"   Status: {s['name']} (id={s['id']})", flush=True)
