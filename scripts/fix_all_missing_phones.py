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

    print("=== SCANNING RECENT LEADS FOR CONTACTS WITH MISSING PHONES ===")
    r = session.get(f'{base}/api/v4/leads?limit=100&order[updated_at]=desc&with=contacts')
    if r.status_code != 200:
        print("Error fetching leads:", r.status_code)
        return
        
    leads = r.json().get('_embedded', {}).get('leads', [])
    print(f"Fetched {len(leads)} leads")

    fixed_count = 0
    for ld in leads:
        lid = ld.get('id')
        lname = ld.get('name', '')
        c_list = ld.get('_embedded', {}).get('contacts', [])
        
        # Check if phone is mentioned in lead name
        phone_match = re.search(r'(\+?998\s?\(?\d{2}\)?\s?\d{3}\s?\d{2}\s?\d{2}|\b9\d{8}\b|\b7\d{8}\b|\b3\d{8}\b|\b8\d{8}\b)', lname)
        if not phone_match:
            continue
            
        raw_phone = phone_match.group(0).strip()
        digits = re.sub(r'\D', '', raw_phone)
        if len(digits) == 9:
            norm_phone = f"+998{digits}"
        elif len(digits) == 12:
            norm_phone = f"+{digits}"
        else:
            norm_phone = raw_phone
            
        for c in c_list:
            cid = c.get('id')
            time.sleep(0.1)
            try:
                rc = session.get(f'{base}/api/v4/contacts/{cid}')
                if rc.status_code != 200:
                    continue
                cdata = rc.json()
                cname = cdata.get('name', '')
                cf_values = cdata.get('custom_fields_values') or []
                
                has_phone = any(cf.get('field_code') == 'PHONE' and cf.get('values') for cf in cf_values)
                if not has_phone:
                    print(f"Lead #{lid} '{lname}': Contact #{cid} ('{cname}') has NO phone! Adding {norm_phone}...")
                    patch_payload = {
                        "custom_fields_values": [
                            {
                                "field_code": "PHONE",
                                "values": [
                                    {
                                        "value": norm_phone,
                                        "enum_code": "MOB"
                                    }
                                ]
                            }
                        ]
                    }
                    rp = session.patch(f'{base}/api/v4/contacts/{cid}', json=patch_payload)
                    if rp.status_code == 200:
                        print(f"  SUCCESS: Contact #{cid} updated with {norm_phone}")
                        fixed_count += 1
                    else:
                        print(f"  Error updating contact #{cid}: {rp.status_code} {rp.text}")
            except Exception as e:
                print(f"Exception for cid {cid}: {e}")

    print(f"\nScan completed. Fixed {fixed_count} contacts with missing phones.")

if __name__ == '__main__':
    main()
