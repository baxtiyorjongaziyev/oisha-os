import json
import sys
import io
import requests

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')

token = json.load(open('data/amocrm_token.json', 'r', encoding='utf-8'))
headers = {'Authorization': f"Bearer {token['access_token']}"}

# Load the 89 leads that were updated to Mumtozmaxal
data = json.load(open('data/farangiz_entities_to_update.json', 'r', encoding='utf-8'))
lead_ids = [l['id'] for l in data.get('leads', [])]
print(f"Total Mumtozmaxal leads: {len(lead_ids)}")

# Check tasks for these leads
# In amoCRM API v4: GET /api/v4/tasks?filter[entity_type]=leads&filter[is_completed]=0
# or query per lead or batch filter
open_tasks = []
for i in range(0, min(len(lead_ids), 30), 10):
    chunk = lead_ids[i:i+10]
    for lid in chunk:
        r = requests.get(f'https://jonbranding.amocrm.ru/api/v4/tasks?filter[entity_id]={lid}&filter[entity_type]=leads&filter[is_completed]=0', headers=headers, timeout=10)
        if r.status_code == 200:
            ts = r.json().get('_embedded', {}).get('tasks', [])
            for t in ts:
                open_tasks.append({
                    'lead_id': lid,
                    'task_id': t['id'],
                    'text': t['text'],
                    'complete_till': t['complete_till'],
                    'responsible': t['responsible_user_id']
                })

print(f"Sample checked 30 leads: found {len(open_tasks)} open tasks")
for t in open_tasks[:5]:
    print(f"  Lead {t['lead_id']} -> Task {t['task_id']}: '{t['text'][:60]}...' (resp {t['responsible']})")
