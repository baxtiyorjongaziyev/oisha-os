import json
import sys
import io
import requests

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')

token = json.load(open('data/amocrm_token.json', 'r', encoding='utf-8'))
headers = {'Authorization': f"Bearer {token['access_token']}"}

# Inspect the 3 leads found
sample_lead_ids = [51857755, 52080213, 52116195]
for lid in sample_lead_ids:
    r = requests.get(f'https://jonbranding.amocrm.ru/api/v4/leads/{lid}', headers=headers, timeout=10)
    if r.status_code == 200:
        ld = r.json()
        tags = ld.get('_embedded', {}).get('tags', [])
        print(f"Lead {lid}: '{ld.get('name')}', Pipeline: {ld.get('pipeline_id')}, Status: {ld.get('status_id')}")
        print("  Tags:", tags)
