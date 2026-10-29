import json
import sys
import io
import time
import requests

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')

token = json.load(open('data/amocrm_token.json', 'r', encoding='utf-8'))
headers = {
    'Authorization': f"Bearer {token['access_token']}",
    'Content-Type': 'application/json'
}

entities_file = 'data/farangiz_entities_to_update.json'
data = json.load(open(entities_file, 'r', encoding='utf-8'))

leads_list = data.get('leads', [])
contacts_list = data.get('contacts', [])

print(f"Total leads to update: {len(leads_list)}", flush=True)
print(f"Total contacts to update: {len(contacts_list)}", flush=True)

# 1. Update Leads in batches of 25
batch_size = 25
updated_leads_count = 0
failed_leads = []

for i in range(0, len(leads_list), batch_size):
    chunk = leads_list[i:i + batch_size]
    patch_payload = []
    
    for l in chunk:
        lid = l['id']
        current_tags = l.get('tags', [])
        new_tags = []
        for t in current_tags:
            if t.lower() == 'farangiz':
                new_tags.append({'name': 'Mumtozmaxal'})
            else:
                new_tags.append({'name': t})
                
        # Deduplicate tag names while preserving case
        seen = set()
        dedup_tags = []
        for t in new_tags:
            t_name = t['name']
            if t_name.lower() not in seen:
                seen.add(t_name.lower())
                dedup_tags.append(t)
                
        patch_payload.append({
            'id': lid,
            '_embedded': {
                'tags': dedup_tags
            }
        })
        
    print(f"Sending batch {i//batch_size + 1} ({len(patch_payload)} leads)...", flush=True)
    r = requests.patch('https://jonbranding.amocrm.ru/api/v4/leads', headers=headers, json=patch_payload, timeout=20)
    if r.status_code == 200:
        updated_leads_count += len(patch_payload)
        print(f"  Batch {i//batch_size + 1} SUCCESS! (HTTP 200)", flush=True)
    else:
        print(f"  Batch {i//batch_size + 1} FAILED! Status {r.status_code}: {r.text}", flush=True)
        failed_leads.extend([l['id'] for l in chunk])
        
    time.sleep(0.5)

print(f"\nLeads update completed: {updated_leads_count}/{len(leads_list)} successful.", flush=True)

# 2. Update Contacts
updated_contacts_count = 0
if contacts_list:
    contact_payload = []
    for c in contacts_list:
        cid = c['id']
        current_tags = c.get('tags', [])
        new_tags = []
        for t in current_tags:
            if t.lower() == 'farangiz':
                new_tags.append({'name': 'Mumtozmaxal'})
            else:
                new_tags.append({'name': t})
        contact_payload.append({
            'id': cid,
            '_embedded': {
                'tags': new_tags
            }
        })
        
    print(f"\nUpdating {len(contact_payload)} contact(s)...", flush=True)
    r_c = requests.patch('https://jonbranding.amocrm.ru/api/v4/contacts', headers=headers, json=contact_payload, timeout=15)
    if r_c.status_code == 200:
        updated_contacts_count += len(contact_payload)
        print(f"  Contacts update SUCCESS! (HTTP 200)", flush=True)
    else:
        print(f"  Contacts update FAILED! Status {r_c.status_code}: {r_c.text}", flush=True)

# 3. Post-verification
print("\n--- POST-VERIFICATION AUDIT ---", flush=True)
# Check tag Mumtozmaxal in leads tags
r_mumtoz = requests.get('https://jonbranding.amocrm.ru/api/v4/leads/tags?query=Mumtozmaxal', headers=headers, timeout=10)
if r_mumtoz.status_code == 200:
    tags = r_mumtoz.json().get('_embedded', {}).get('tags', [])
    print(f"Verified 'Mumtozmaxal' tag created in amoCRM leads dictionary: {tags}")

# Check leads still with 'farangiz' tag
r_check = requests.get('https://jonbranding.amocrm.ru/api/v4/leads?query=farangiz&limit=250', headers=headers, timeout=15)
remaining_farangiz = []
if r_check.status_code == 200:
    for l in r_check.json().get('_embedded', {}).get('leads', []):
        tags = [t['name'] for t in l.get('_embedded', {}).get('tags', []) or []]
        if any(t.lower() == 'farangiz' for t in tags):
            remaining_farangiz.append(l['id'])

print(f"Remaining leads with 'farangiz' tag: {len(remaining_farangiz)}")

# Check sample leads with 'Mumtozmaxal'
r_sample = requests.get('https://jonbranding.amocrm.ru/api/v4/leads?query=Mumtozmaxal&limit=5', headers=headers, timeout=15)
if r_sample.status_code == 200:
    sample_leads = r_sample.json().get('_embedded', {}).get('leads', [])
    print(f"Verified {len(sample_leads)} sample leads with 'Mumtozmaxal':")
    for sl in sample_leads:
        tags = [t['name'] for t in sl.get('_embedded', {}).get('tags', [])]
        print(f"  Lead ID {sl['id']}: '{sl['name']}', tags: {tags}")

with open('data/tag_rename_audit_report.json', 'w', encoding='utf-8') as f_audit:
    json.dump({
        'updated_leads': updated_leads_count,
        'updated_contacts': updated_contacts_count,
        'failed_leads': failed_leads,
        'remaining_farangiz': remaining_farangiz
    }, f_audit, ensure_ascii=False, indent=2)

print("\nAudit report saved to data/tag_rename_audit_report.json!", flush=True)
