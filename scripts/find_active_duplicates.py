import json
import re
import sys
from collections import defaultdict
import requests

sys.stdout.reconfigure(encoding='utf-8')

with open('data/amocrm_token.json') as f:
    tok = json.load(f)['access_token']
headers = {'Authorization': f'Bearer {tok}'}
base = 'https://jonbranding.amocrm.ru'

# Pipelines and statuses
r = requests.get(f'{base}/api/v4/leads/pipelines', headers=headers)
pipelines = r.json().get('_embedded', {}).get('pipelines', [])
pipe_map = {p['id']: p['name'] for p in pipelines}
status_map = {}
for p in pipelines:
    for s in p.get('_embedded', {}).get('statuses', []):
        status_map[s['id']] = s['name']

# Fetch all active leads with contacts
active_statuses = [
    # Sotuv Bo'limi
    (11162698, 87609510), (11162698, 89067962), (11162698, 87609518),
    (11162698, 87609522), (11162698, 87609526), (11162698, 88871066),
    # Reactivation
    (10947042, 86076846),
    # Partnership
    (10947046, 86076870), (10947046, 86076874), (10947046, 86076878),
    # Farmer
    (10123318, 80215338), (10123318, 80215438),
    # Vacancy
    (10963570, 86197550)
]

all_leads = []
print("Fetching all 540 active leads with contact details...", flush=True)

contact_ids = set()
for pid, sid in active_statuses:
    page = 1
    while True:
        url = f'{base}/api/v4/leads?filter[statuses][0][pipeline_id]={pid}&filter[statuses][0][status_id]={sid}&limit=250&page={page}&with=contacts'
        res = requests.get(url, headers=headers)
        if res.status_code != 200:
            break
        lds = res.json().get('_embedded', {}).get('leads', [])
        for ld in lds:
            all_leads.append(ld)
            for c in ld.get('_embedded', {}).get('contacts', []):
                contact_ids.add(c['id'])
        if len(lds) < 250:
            break
        page += 1

print(f"Total active leads fetched: {len(all_leads)}", flush=True)
print(f"Total unique contacts linked: {len(contact_ids)}", flush=True)

# Fetch contact phone numbers in chunks of 50
print("Fetching contact phone numbers...", flush=True)
contact_phones = {}
contact_names = {}
c_list = list(contact_ids)
chunk_size = 50
for i in range(0, len(c_list), chunk_size):
    chunk = c_list[i:i+chunk_size]
    # AmoCRM filter by id: filter[id][0]=...
    params = '&'.join([f'filter[id][]={cid}' for cid in chunk])
    url = f'{base}/api/v4/contacts?{params}'
    res = requests.get(url, headers=headers)
    if res.status_code == 200:
        c_data = res.json().get('_embedded', {}).get('contacts', [])
        for c in c_data:
            cid = c['id']
            contact_names[cid] = c.get('name', '')
            for cf in c.get('custom_fields_values') or []:
                if cf.get('field_code') == 'PHONE':
                    for val in cf.get('values', []):
                        raw_v = re.sub(r'\D', '', val.get('value', ''))
                        if raw_v:
                            if len(raw_v) == 9:
                                raw_v = '998' + raw_v
                            contact_phones[cid] = raw_v

print(f"Loaded phones for {len(contact_phones)} contacts", flush=True)

# Map leads to phone and contact
leads_by_phone = defaultdict(list)
leads_by_contact = defaultdict(list)
leads_by_name = defaultdict(list)

for ld in all_leads:
    lid = ld['id']
    lname = ld.get('name', '').strip()
    pid = ld.get('pipeline_id')
    sid = ld.get('status_id')
    created = ld.get('created_at')
    price = ld.get('price', 0)
    pname = pipe_map.get(pid, pid)
    sname = status_map.get(sid, sid)
    
    c_ids = [c['id'] for c in ld.get('_embedded', {}).get('contacts', [])]
    lead_info = {
        'id': lid,
        'name': lname,
        'pipeline_id': pid,
        'pipeline': pname,
        'status_id': sid,
        'status': sname,
        'created_at': created,
        'price': price,
        'contact_ids': c_ids,
        'phones': [contact_phones[cid] for cid in c_ids if cid in contact_phones]
    }
    
    leads_by_name[lname.lower()].append(lead_info)
    for cid in c_ids:
        leads_by_contact[cid].append(lead_info)
        phone = contact_phones.get(cid)
        if phone:
            leads_by_phone[phone].append(lead_info)

# 1. PHONE DUPLICATES
dup_phones = {p: lds for p, lds in leads_by_phone.items() if len(lds) > 1}
print(f"\n{'='*60}")
print(f"1. PHONE DUPLICATES: {len(dup_phones)} phone numbers have MULTIPLE active deals")
print(f"{'='*60}")
total_phone_dup_deals = sum(len(lds) - 1 for lds in dup_phones.values())
print(f"Total excess duplicate deals from shared phones: {total_phone_dup_deals}")

for p, lds in sorted(dup_phones.items(), key=lambda x: -len(x[1]))[:25]:
    print(f"\nPhone: +{p} ({len(lds)} active deals):")
    for ld in lds:
        c_names = [contact_names.get(cid, str(cid)) for cid in ld['contact_ids']]
        print(f"  - Deal #{ld['id']} '{ld['name']}' | {ld['pipeline']} -> {ld['status']} | Created: {ld['created_at']} | Contacts: {c_names}")

# 2. CONTACT DUPLICATES
dup_contacts = {cid: lds for cid, lds in leads_by_contact.items() if len(lds) > 1}
print(f"\n{'='*60}")
print(f"2. CONTACT DUPLICATES: {len(dup_contacts)} contacts have MULTIPLE active deals")
print(f"{'='*60}")
total_contact_dup_deals = sum(len(lds) - 1 for lds in dup_contacts.values())
print(f"Total excess duplicate deals from same contact: {total_contact_dup_deals}")

for cid, lds in sorted(dup_contacts.items(), key=lambda x: -len(x[1]))[:25]:
    cname = contact_names.get(cid, 'Unknown')
    phone = contact_phones.get(cid, 'No phone')
    print(f"\nContact #{cid} '{cname}' (+{phone}) has {len(lds)} active deals:")
    for ld in lds:
        print(f"  - Deal #{ld['id']} '{ld['name']}' | {ld['pipeline']} -> {ld['status']} | Created: {ld['created_at']}")

# 3. EXACT NAME DUPLICATES (where name != empty and != 'Yangi bitim')
dup_names = {name: lds for name, lds in leads_by_name.items() if len(lds) > 1 and name not in ('', 'yangi bitim', 'bez nazvaniya')}
print(f"\n{'='*60}")
print(f"3. EXACT NAME DUPLICATES: {len(dup_names)} distinct deal names have MULTIPLE active deals")
print(f"{'='*60}")
total_name_dup_deals = sum(len(lds) - 1 for lds in dup_names.values())
print(f"Total excess duplicate deals from exact names: {total_name_dup_deals}")

for name, lds in sorted(dup_names.items(), key=lambda x: -len(x[1]))[:20]:
    print(f"\nName '{name}' ({len(lds)} active deals):")
    for ld in lds:
        phones = ld['phones']
        print(f"  - Deal #{ld['id']} | {ld['pipeline']} -> {ld['status']} | Created: {ld['created_at']} | Phones: {phones}")

# 4. LEADS WITH NO CONTACT OR NO PHONE
no_contact_leads = [ld for ld in all_leads if not ld.get('_embedded', {}).get('contacts', [])]
no_phone_leads = []
for ld in all_leads:
    c_ids = [c['id'] for c in ld.get('_embedded', {}).get('contacts', [])]
    if c_ids and not any(cid in contact_phones for cid in c_ids):
        no_phone_leads.append(ld)
print(f"\n{'='*60}")
print(f"4. ANOMALIES & JUNK LEADS:")
print(f"   - Leads with NO contact attached: {len(no_contact_leads)}")
print(f"   - Leads with contact but NO phone number: {len(no_phone_leads)}")
print(f"   - Leads in Reactivation 'Sovuq baza': 42")
print(f"{'='*60}")

# Save full results to json for surgical merging/closing
with open('data/active_duplicates_report.json', 'w', encoding='utf-8') as f:
    json.dump({
        'total_active': len(all_leads),
        'phone_duplicates_count': len(dup_phones),
        'total_phone_dup_deals': total_phone_dup_deals,
        'contact_duplicates_count': len(dup_contacts),
        'total_contact_dup_deals': total_contact_dup_deals,
        'name_duplicates_count': len(dup_names),
        'total_name_dup_deals': total_name_dup_deals,
        'no_contact_leads': [ld['id'] for ld in no_contact_leads],
        'phone_duplicates': {p: lds for p, lds in dup_phones.items()}
    }, f, ensure_ascii=False, indent=2)

print("\nSaved full audit data to data/active_duplicates_report.json")
