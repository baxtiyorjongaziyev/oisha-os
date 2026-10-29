import json
import sys
import io
import requests

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')

token = json.load(open('data/amocrm_token.json', 'r', encoding='utf-8'))
headers = {'Authorization': f"Bearer {token['access_token']}"}

# Active statuses in Sotuv Bo'limi (11162698)
active_statuses = [87609510, 89067962, 87609518, 87609522, 87609526, 89380154, 88871066]
sotuv_leads = []
for st in active_statuses:
    r = requests.get(f'https://jonbranding.amocrm.ru/api/v4/leads?filter[statuses][0]={st}&limit=250&with=contacts', headers=headers, timeout=15)
    if r.status_code == 200:
        lds = r.json().get('_embedded', {}).get('leads', [])
        sotuv_leads.extend(lds)
        print(f"Status {st}: {len(lds)} leads", flush=True)

print(f"Total active leads in Sotuv Bo'limi: {len(sotuv_leads)}", flush=True)
with open('data/amocrm_sotuv_active_leads.json', 'w', encoding='utf-8') as f:
    json.dump(sotuv_leads, f, ensure_ascii=False, indent=2)
