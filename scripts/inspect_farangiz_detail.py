import json
import sys
import io
import datetime
import requests

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')

token = json.load(open('data/amocrm_token.json', 'r', encoding='utf-8'))
headers = {'Authorization': f"Bearer {token['access_token']}"}

sample_lead_ids = [51857755, 52080213, 52116195]
for lid in sample_lead_ids:
    r = requests.get(f'https://jonbranding.amocrm.ru/api/v4/leads/{lid}?with=contacts', headers=headers, timeout=10)
    if r.status_code == 200:
        ld = r.json()
        dt = datetime.datetime.fromtimestamp(ld.get('created_at', 0))
        print(f"Lead {lid}: {ld.get('name')}")
        print(f"  Created at: {dt} (unix: {ld.get('created_at')})")
        print(f"  Pipeline: {ld.get('pipeline_id')}, Status: {ld.get('status_id')}")
        print(f"  Responsible: {ld.get('responsible_user_id')}")
        print(f"  Tags: {[t['name'] for t in ld.get('_embedded', {}).get('tags', [])]}")
        print(f"  Contacts: {[c['id'] for c in ld.get('_embedded', {}).get('contacts', [])]}")
