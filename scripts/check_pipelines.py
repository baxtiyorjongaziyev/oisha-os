import json
import sys
import io
import requests

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')

token = json.load(open('data/amocrm_token.json', 'r', encoding='utf-8'))
headers = {'Authorization': f"Bearer {token['access_token']}"}
r = requests.get('https://jonbranding.amocrm.ru/api/v4/leads/pipelines', headers=headers, timeout=15)
print('Status:', r.status_code)
if r.status_code == 200:
    data = r.json()
    pipelines = []
    for p in data.get('_embedded', {}).get('pipelines', []):
        p_info = {'id': p['id'], 'name': p['name'], 'statuses': []}
        print(f"Pipeline: ID={p['id']}, Name='{p['name']}'")
        for s in p.get('_embedded', {}).get('statuses', []):
            p_info['statuses'].append({'id': s['id'], 'name': s['name']})
            print(f"   Status: ID={s['id']}, Name='{s['name']}'")
        pipelines.append(p_info)
    with open('data/amocrm_pipelines_dump.json', 'w', encoding='utf-8') as f:
        json.dump(pipelines, f, ensure_ascii=False, indent=2)
