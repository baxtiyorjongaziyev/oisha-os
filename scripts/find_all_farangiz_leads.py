import json
import sys
import io

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')

# 1. Check in amocrm_sotuv_active_leads.json
leads_sotuv = json.load(open('data/amocrm_sotuv_active_leads.json', 'r', encoding='utf-8'))
print(f"Total leads in sotuv active cache: {len(leads_sotuv)}")

farangiz_sotuv = []
for l in leads_sotuv:
    tags = [t['name'].lower() for t in l.get('_embedded', {}).get('tags', []) or []]
    if 'farangiz' in tags:
        farangiz_sotuv.append(l)

print(f"Found {len(farangiz_sotuv)} leads with 'farangiz' tag in Sotuv Bo'limi active:")
for fl in farangiz_sotuv:
    tags = [t['name'] for t in fl.get('_embedded', {}).get('tags', []) or []]
    print(f"  ID {fl['id']}: '{fl['name']}' (status {fl['status_id']}) - tags: {tags}")

# 2. Check in amocrm_utc_pipeline_leads.json
leads_utc = json.load(open('data/amocrm_utc_pipeline_leads.json', 'r', encoding='utf-8'))
print(f"\nTotal leads in UTC pipeline cache: {len(leads_utc)}")
farangiz_utc = []
for l in leads_utc:
    tags = [t['name'].lower() for t in l.get('_embedded', {}).get('tags', []) or []]
    if 'farangiz' in tags:
        farangiz_utc.append(l)

print(f"Found {len(farangiz_utc)} leads with 'farangiz' tag in UTC pipeline:")
for fl in farangiz_utc:
    tags = [t['name'] for t in fl.get('_embedded', {}).get('tags', []) or []]
    print(f"  ID {fl['id']}: '{fl['name']}' (status {fl['status_id']}) - tags: {tags}")
