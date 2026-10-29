import json
import sys
import requests

sys.stdout.reconfigure(encoding='utf-8')

def main():
    with open('data/amocrm_token.json') as f:
        tok = json.load(f)['access_token']
    headers = {'Authorization': f'Bearer {tok}', 'Content-Type': 'application/json'}
    base = 'https://jonbranding.amocrm.ru'

    # Check the specific contacts found earlier
    test_cids = [42907059, 42981445, 42825245, 42816939, 42961711, 42834915]
    print("=== INSPECTING PREVIOUS CONTACTS ===")
    for cid in test_cids:
        r = requests.get(f'{base}/api/v4/contacts/{cid}?with=leads', headers=headers)
        if r.status_code == 200:
            c = r.json()
            print(f"\nContact ID: {cid} | Name: '{c.get('name')}'")
            leads = c.get('_embedded', {}).get('leads', [])
            print(f"  Linked leads: {[ld.get('id') for ld in leads]}")
            for cf in c.get('custom_fields_values') or []:
                if cf.get('field_code') == 'PHONE':
                    print(f"  Phone field values: {cf.get('values')}")
        else:
            print(f"Contact ID: {cid} status: {r.status_code}")

    # Now let's fetch ALL contacts with pagination (up to 1000) to find REAL cross-contact duplicates (different IDs with same phone)
    print("\n=== SCANNING ALL CONTACTS FOR DUPLICATES ACROSS DIFFERENT IDS ===")
    phone_to_contacts = {}
    page = 1
    total_contacts = 0
    while True:
        r = requests.get(f'{base}/api/v4/contacts?limit=250&page={page}&with=leads', headers=headers)
        if r.status_code != 200:
            break
        data = r.json()
        contacts = data.get('_embedded', {}).get('contacts', [])
        if not contacts:
            break
        total_contacts += len(contacts)
        for c in contacts:
            cid = c.get('id')
            cname = c.get('name')
            leads = [ld.get('id') for ld in c.get('_embedded', {}).get('leads', [])]
            for cf in c.get('custom_fields_values') or []:
                if cf.get('field_code') == 'PHONE':
                    for val in cf.get('values', []):
                        raw_val = val.get('value', '').replace(' ', '').replace('-', '').replace('+', '').replace('(', '').replace(')', '')
                        if raw_val:
                            # Normalize Uzbekistan phone
                            if len(raw_val) == 9:
                                raw_val = '998' + raw_val
                            phone_to_contacts.setdefault(raw_val, []).append({
                                'contact_id': cid,
                                'name': cname,
                                'leads': leads
                            })
        page += 1
        if page > 10:
            break

    print(f"Total contacts scanned: {total_contacts}")
    
    # Filter for real duplicates (different contact IDs for same phone)
    real_dup_contacts = {}
    intra_contact_dups = {} # same contact having duplicate phone values
    for p, clist in phone_to_contacts.items():
        unique_cids = {c['contact_id'] for c in clist}
        if len(unique_cids) > 1:
            real_dup_contacts[p] = clist
        elif len(clist) > 1:
            intra_contact_dups[p] = clist

    print(f"\nREAL DUPLICATE CONTACTS (Different Contact IDs sharing same phone): {len(real_dup_contacts)}")
    for p, clist in real_dup_contacts.items():
        print(f" Phone: {p}")
        for c in clist:
            print(f"   - Contact #{c['contact_id']} '{c['name']}' | Leads: {c['leads']}")

    print(f"\nINTRA-CONTACT DUPLICATES (Single Contact having duplicate phone entries): {len(intra_contact_dups)}")
    for p, clist in intra_contact_dups.items():
        print(f" Phone: {p} on Contact #{clist[0]['contact_id']} '{clist[0]['name']}' ({len(clist)} entries)")

    # Also check duplicate leads (multiple active leads for same contact or company)
    print("\n=== SCANNING ALL ACTIVE LEADS FOR DUPLICATES ===")
    page = 1
    total_leads = 0
    contact_to_leads = {}
    while True:
        r = requests.get(f'{base}/api/v4/leads?limit=250&page={page}&with=contacts', headers=headers)
        if r.status_code != 200:
            break
        data = r.json()
        leads = data.get('_embedded', {}).get('leads', [])
        if not leads:
            break
        total_leads += len(leads)
        for ld in leads:
            lid = ld.get('id')
            lname = ld.get('name')
            sid = ld.get('status_id')
            pid = ld.get('pipeline_id')
            price = ld.get('price')
            c_list = [c.get('id') for c in ld.get('_embedded', {}).get('contacts', [])]
            for cid in c_list:
                contact_to_leads.setdefault(cid, []).append({
                    'lead_id': lid,
                    'name': lname,
                    'status_id': sid,
                    'pipeline_id': pid,
                    'price': price
                })
        page += 1
        if page > 10:
            break

    dup_lead_contacts = {cid: lds for cid, lds in contact_to_leads.items() if len(lds) > 1}
    print(f"Contacts with MULTIPLE LEADS: {len(dup_lead_contacts)}")
    for cid, lds in list(dup_lead_contacts.items())[:10]:
        print(f" Contact #{cid} has {len(lds)} leads:")
        for ld in lds:
            print(f"   - Lead #{ld['lead_id']}: '{ld['name']}' | Status: {ld['status_id']} | Price: {ld['price']}")

if __name__ == '__main__':
    main()
