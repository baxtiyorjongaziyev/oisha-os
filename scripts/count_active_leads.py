import json
import sys
import requests

sys.stdout.reconfigure(encoding='utf-8')

with open('data/amocrm_token.json') as f:
    tok = json.load(f)['access_token']
headers = {'Authorization': f'Bearer {tok}'}
base = 'https://jonbranding.amocrm.ru'

r = requests.get(f'{base}/api/v4/leads/pipelines', headers=headers)
pipelines = r.json().get('_embedded', {}).get('pipelines', [])

total_active = 0
pipeline_active_counts = {}

for p in pipelines:
    pid = p['id']
    pname = p['name']
    statuses = [s for s in p.get('_embedded', {}).get('statuses', []) if s['id'] not in (142, 143)]
    
    pipe_total = 0
    print(f"\nChecking Pipeline '{pname}' (#{pid})...", flush=True)
    for s in statuses:
        sid = s['id']
        sname = s['name']
        # Query count for this status
        url = f'{base}/api/v4/leads?filter[statuses][0][pipeline_id]={pid}&filter[statuses][0][status_id]={sid}&limit=1'
        res = requests.get(url, headers=headers)
        if res.status_code == 200:
            # We can paginate to count
            count = 0
            page = 1
            while True:
                p_url = f'{base}/api/v4/leads?filter[statuses][0][pipeline_id]={pid}&filter[statuses][0][status_id]={sid}&limit=250&page={page}'
                p_res = requests.get(p_url, headers=headers)
                if p_res.status_code != 200:
                    break
                lds = p_res.json().get('_embedded', {}).get('leads', [])
                count += len(lds)
                if len(lds) < 250:
                    break
                page += 1
            if count > 0:
                print(f"   Status '{sname}' (#{sid}): {count} leads", flush=True)
                pipe_total += count
    print(f"Total active in '{pname}': {pipe_total}", flush=True)
    pipeline_active_counts[pname] = pipe_total
    total_active += pipe_total

print("\n" + "="*50)
print(f"GRAND TOTAL ACTIVE LEADS IN AMOCRM: {total_active}", flush=True)
print("="*50)
for pname, cnt in sorted(pipeline_active_counts.items(), key=lambda x: -x[1]):
    print(f"{pname}: {cnt} active leads", flush=True)
