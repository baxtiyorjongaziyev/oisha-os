import json
import sys
import re
import time
import requests

sys.stdout.reconfigure(encoding='utf-8')

def main():
    with open('data/amocrm_token.json') as f:
        tok = json.load(f)['access_token']
    session = requests.Session()
    session.headers.update({'Authorization': f'Bearer {tok}', 'Content-Type': 'application/json'})
    base = 'https://jonbranding.amocrm.ru'

    print("=== 1. CHECKING INSTAGRAM TALKS AND RECENT LEADS ===")
    
    # Fetch talks
    r_talks = session.get(f'{base}/api/v4/talks?limit=100')
    talks = r_talks.json().get('_embedded', {}).get('talks', []) if r_talks.status_code == 200 else []
    print(f"Total talks fetched: {len(talks)}")

    updated_contacts = []

    for t in talks:
        cid = t.get('contact_id')
        lid = t.get('entity_id')
        if not cid:
            continue
            
        time.sleep(0.15)
        # Fetch contact
        rc = session.get(f'{base}/api/v4/contacts/{cid}')
        if rc.status_code != 200:
            continue
            
        cdata = rc.json()
        cname = cdata.get('name', '')
        cf_values = cdata.get('custom_fields_values') or []
        
        has_phone = False
        existing_phone = []
        for cf in cf_values:
            if cf.get('field_code') == 'PHONE':
                has_phone = True
                existing_phone = [v.get('value') for v in cf.get('values', [])]

        # Fetch lead if exists
        lname = ''
        if lid:
            time.sleep(0.15)
            rl = session.get(f'{base}/api/v4/leads/{lid}')
            if rl.status_code == 200:
                lname = rl.json().get('name', '')

        # Check if phone is in contact name or lead name
        search_text = f"{cname} {lname}"
        phone_match = re.search(r'(\+?998\s?\(?\d{2}\)?\s?\d{3}\s?\d{2}\s?\d{2}|\b9\d{8}\b|\b7\d{8}\b|\b3\d{8}\b|\b8\d{8}\b)', search_text)
        
        if phone_match and not has_phone:
            raw_phone = phone_match.group(0).strip()
            # Normalize phone
            digits = re.sub(r'\D', '', raw_phone)
            if len(digits) == 9:
                formatted_phone = f"+998{digits}"
            elif len(digits) == 12:
                formatted_phone = f"+{digits}"
            else:
                formatted_phone = raw_phone

            print(f"Adding phone {formatted_phone} to Contact #{cid} ('{cname}') from Lead #{lid} ('{lname}')...")
            
            patch_data = {
                "custom_fields_values": [
                    {
                        "field_code": "PHONE",
                        "values": [
                            {
                                "value": formatted_phone,
                                "enum_code": "MOB"
                            }
                        ]
                    }
                ]
            }
            time.sleep(0.2)
            rp = session.patch(f'{base}/api/v4/contacts/{cid}', json=patch_data)
            if rp.status_code == 200:
                print(f"  SUCCESS: Contact #{cid} updated with phone {formatted_phone}!")
                updated_contacts.append({
                    'contact_id': cid,
                    'contact_name': cname,
                    'phone': formatted_phone,
                    'lead_id': lid,
                    'lead_name': lname
                })
            else:
                print(f"  FAILED to update contact #{cid}: {rp.status_code} {rp.text}")

    print("\n=== 2. CHECKING ALL RECENT LEADS FOR CONTACTS WITH MISSING PHONES ===")
    r_leads = session.get(f'{base}/api/v4/leads?limit=100&order[updated_at]=desc&with=contacts')
    leads = r_leads.json().get('_embedded', {}).get('leads', []) if r_leads.status_code == 200 else []
    
    for ld in leads:
        lid = ld.get('id')
        lname = ld.get('name', '')
        c_list = ld.get('_embedded', {}).get('contacts', [])
        
        phone_match = re.search(r'(\+?998\s?\(?\d{2}\)?\s?\d{3}\s?\d{2}\s?\d{2}|\b9\d{8}\b|\b7\d{8}\b|\b3\d{8}\b|\b8\d{8}\b)', lname)
        if not phone_match:
            continue
            
        raw_phone = phone_match.group(0).strip()
        digits = re.sub(r'\D', '', raw_phone)
        if len(digits) == 9:
            formatted_phone = f"+998{digits}"
        elif len(digits) == 12:
            formatted_phone = f"+{digits}"
        else:
            formatted_phone = raw_phone
            
        for c in c_list:
            cid = c.get('id')
            time.sleep(0.15)
            rc = session.get(f'{base}/api/v4/contacts/{cid}')
            if rc.status_code != 200:
                continue
            cdata = rc.json()
            cname = cdata.get('name', '')
            cf_values = cdata.get('custom_fields_values') or []
            
            has_phone = any(cf.get('field_code') == 'PHONE' for cf in cf_values)
            if not has_phone:
                print(f"Adding phone {formatted_phone} to Contact #{cid} ('{cname}') from Lead #{lid} ('{lname}')...")
                patch_data = {
                    "custom_fields_values": [
                        {
                            "field_code": "PHONE",
                            "values": [
                                {
                                    "value": formatted_phone,
                                    "enum_code": "MOB"
                                }
                            ]
                        }
                    ]
                }
                time.sleep(0.2)
                rp = session.patch(f'{base}/api/v4/contacts/{cid}', json=patch_data)
                if rp.status_code == 200:
                    print(f"  SUCCESS: Contact #{cid} updated with phone {formatted_phone}!")
                    updated_contacts.append({
                        'contact_id': cid,
                        'contact_name': cname,
                        'phone': formatted_phone,
                        'lead_id': lid,
                        'lead_name': lname
                    })
                else:
                    print(f"  FAILED to update contact #{cid}: {rp.status_code} {rp.text}")

    print(f"\n=== SUMMARY: TOTAL CONTACTS UPDATED WITH PHONES: {len(updated_contacts)} ===")
    for u in updated_contacts:
        print(f"- Contact #{u['contact_id']} ('{u['contact_name']}') -> Phone: {u['phone']} (Lead #{u['lead_id']}: '{u['lead_name']}')")

if __name__ == '__main__':
    main()
