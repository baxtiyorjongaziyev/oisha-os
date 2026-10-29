import json
import sys
import re
import requests

sys.stdout.reconfigure(encoding='utf-8')

def main():
    with open('data/amocrm_token.json') as f:
        tok = json.load(f)['access_token']
    headers = {'Authorization': f'Bearer {tok}', 'Content-Type': 'application/json'}
    base = 'https://jonbranding.amocrm.ru'

    print("=== SCANNING FOR LEADS WITH PHONE IN NAME/NOTES BUT MISSING IN CONTACT ===")
    r = requests.get(f'{base}/api/v4/leads?limit=250&order[updated_at]=desc&with=contacts', headers=headers)
    if r.status_code != 200:
        print("Error fetching leads:", r.status_code)
        return
        
    leads = r.json().get('_embedded', {}).get('leads', [])
    print(f"Total leads fetched: {len(leads)}")

    missing_contact_phones = []

    for ld in leads:
        lid = ld.get('id')
        lname = ld.get('name', '')
        c_list = ld.get('_embedded', {}).get('contacts', [])
        
        # Check if lead name contains a phone number
        phone_match = re.search(r'(\+?998\s?\(?\d{2}\)?\s?\d{3}\s?\d{2}\s?\d{2}|\b9\d{8}\b|\b7\d{8}\b|\b3\d{8}\b|\b8\d{8}\b)', lname)
        extracted_phone = phone_match.group(0) if phone_match else None
        
        if not extracted_phone:
            continue
            
        # Check contact details
        for c in c_list:
            cid = c.get('id')
            rc = requests.get(f'{base}/api/v4/contacts/{cid}', headers=headers)
            if rc.status_code == 200:
                cdata = rc.json()
                cname = cdata.get('name')
                contact_phones = []
                for cf in cdata.get('custom_fields_values') or []:
                    if cf.get('field_code') == 'PHONE':
                        contact_phones = [v.get('value') for v in cf.get('values', [])]
                
                if not contact_phones:
                    missing_contact_phones.append({
                        'lead_id': lid,
                        'lead_name': lname,
                        'contact_id': cid,
                        'contact_name': cname,
                        'extracted_phone': extracted_phone
                    })
                    print(f"FOUND MATCH: Lead #{lid} '{lname}' has phone '{extracted_phone}', but Contact #{cid} '{cname}' has NO phone!")

    print(f"\nTotal leads found where contact is missing the phone: {len(missing_contact_phones)}")
    for item in missing_contact_phones:
        print(item)

if __name__ == '__main__':
    main()
