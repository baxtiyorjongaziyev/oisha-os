import json
import sys
import io
import requests

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')

token = json.load(open('data/amocrm_token.json', 'r', encoding='utf-8'))
headers = {'Authorization': f"Bearer {token['access_token']}"}

print("Fetching all leads in pipeline 11322658 (UTC)...", flush=True)
all_leads = []
for page in [1, 2]:
    r = requests.get(f'https://jonbranding.amocrm.ru/api/v4/leads?filter[pipeline_id]=11322658&limit=250&page={page}&with=contacts', headers=headers, timeout=15)
    if r.status_code == 200:
        leads = r.json().get('_embedded', {}).get('leads', [])
        all_leads.extend(leads)
        print(f"Page {page}: got {len(leads)} leads", flush=True)
    elif r.status_code == 204:
        break

print(f"Total leads fetched: {len(all_leads)}", flush=True)
with open('data/amocrm_utc_pipeline_leads.json', 'w', encoding='utf-8') as f:
    json.dump(all_leads, f, ensure_ascii=False, indent=2)

print("Saved to data/amocrm_utc_pipeline_leads.json", flush=True)
