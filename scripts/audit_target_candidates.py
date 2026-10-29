import json
import sys
import io
import re
import requests

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')

token = json.load(open('data/amocrm_token.json', 'r', encoding='utf-8'))
headers = {'Authorization': f"Bearer {token['access_token']}"}

# Load UTC target leads
utc_data = json.load(open('data/utc_cache/leads_with_recordings.json', 'r', encoding='utf-8'))
target_items = [x for x in utc_data if x.get('lead', {}).get('board') == 'target_leads']

# Identify candidates closest to sale:
# Sell, V_PROTSESSE, Perezvon, or talk duration >= 120s
def get_max_dur(x):
    durs = [r.get('duration', 0) for r in x.get('recordings', [])]
    return max(durs) if durs else 0

for x in target_items:
    x['max_dur'] = get_max_dur(x)

candidates = []
for x in target_items:
    l = x['lead']
    st = l.get('status', '')
    dur = x['max_dur']
    if st in ['Sell', 'V_PROTSESSE', 'Perezvon'] or dur >= 180:
        candidates.append(x)

print(f"Total candidates closest to sale: {len(candidates)}")

# Cross-reference with amoCRM leads
# First load amocrm_all_contacts.json or search by phone
contacts = json.load(open('data/amocrm_all_contacts.json', 'r', encoding='utf-8'))
phone_to_contact = {}
for c in contacts:
    for f in c.get('custom_fields_values', []) or []:
        if f.get('field_code') == 'PHONE':
            for v in f.get('values', []):
                val = v.get('value', '').replace('+', '').replace(' ', '').replace('-', '').replace('(', '').replace(')', '')
                if val:
                    phone_to_contact[val] = c
                    if val.startswith('998') and len(val) == 12:
                        phone_to_contact[val[3:]] = c

print(f"Mapped {len(phone_to_contact)} phone variations to amoCRM contacts")

# Also fetch all leads in amoCRM pipeline 11322658 (UTC) and 11162698 (Sotuv Bo'limi)
leads_map_by_phone = {}
for pid in [11322658, 11162698]:
    page = 1
    while True:
        r = requests.get(f'https://jonbranding.amocrm.ru/api/v4/leads?filter[pipeline_id]={pid}&limit=250&page={page}&with=contacts', headers=headers, timeout=15)
        if r.status_code == 200:
            data = r.json()
            leads = data.get('_embedded', {}).get('leads', [])
            for ld in leads:
                # check contacts
                ld_contacts = ld.get('_embedded', {}).get('contacts', [])
                for c_ref in ld_contacts:
                    c_id = c_ref.get('id')
                    leads_map_by_phone[f"cid_{c_id}"] = ld
                # check lead name for phone digits
                digits = ''.join(re.findall(r'\d+', ld.get('name', '')))
                if len(digits) >= 9:
                    leads_map_by_phone[digits[-9:]] = ld
            if len(leads) < 250:
                break
            page += 1
        elif r.status_code == 204:
            break
        else:
            break

print(f"Loaded amoCRM leads cache: {len(leads_map_by_phone)} mappings")

results = []
for c in candidates:
    l = c['lead']
    card_no = l.get('cardNo')
    name = l.get('name')
    phone = (l.get('phoneNormalized') or l.get('phoneNumber') or '').replace('+', '').replace(' ', '').replace('-', '').replace('(', '').replace(')', '')
    st = l.get('status')
    dur = c['max_dur']
    
    # find amo lead
    amo_lead = None
    if phone[-9:] in leads_map_by_phone:
        amo_lead = leads_map_by_phone[phone[-9:]]
    elif phone in phone_to_contact:
        cnt = phone_to_contact[phone]
        cid = cnt.get('id')
        if f"cid_{cid}" in leads_map_by_phone:
            amo_lead = leads_map_by_phone[f"cid_{cid}"]
            
    results.append({
        'card_no': card_no,
        'name': name,
        'phone': phone,
        'utc_status': st,
        'call_dur': dur,
        'amo_lead_id': amo_lead.get('id') if amo_lead else None,
        'amo_pipeline': amo_lead.get('pipeline_id') if amo_lead else None,
        'amo_status': amo_lead.get('status_id') if amo_lead else None,
        'amo_name': amo_lead.get('name') if amo_lead else None,
    })

print("\n--- RESULTS OF CANDIDATES ---")
for r in results:
    p_name = "Sotuv Bo'limi" if r['amo_pipeline'] == 11162698 else ("UTC" if r['amo_pipeline'] == 11322658 else "NONE")
    print(f"Card #{r['card_no']:3d} | {r['name']:20s} | {r['phone']:12s} | UTC: {r['utc_status']:12s} | Call: {r['call_dur']:3d}s | amoID: {str(r['amo_lead_id']):8s} | Pipe: {p_name:13s} (status {r['amo_status']})")

with open('data/target_leads_candidates_audit.json', 'w', encoding='utf-8') as f:
    json.dump(results, f, ensure_ascii=False, indent=2)
