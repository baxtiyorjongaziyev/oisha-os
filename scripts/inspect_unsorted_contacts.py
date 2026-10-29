import json
import sys
import datetime
import requests

sys.stdout.reconfigure(encoding='utf-8')

def main():
    with open('data/amocrm_token.json') as f:
        tok = json.load(f)['access_token']
    headers = {'Authorization': f'Bearer {tok}', 'Content-Type': 'application/json'}
    base = 'https://jonbranding.amocrm.ru'

    c_ids = [59506805, 59176381, 59036081, 59033077, 58955443, 58884471, 58770891]
    
    print("=== 7 UNSORTED CONTACTS IN AMOCRM ===")
    for cid in c_ids:
        r = requests.get(f'{base}/api/v4/contacts/{cid}', headers=headers)
        if r.status_code == 200:
            c = r.json()
            c_name = c.get('name')
            cf = c.get('custom_fields_values')
            created = datetime.datetime.fromtimestamp(c.get('created_at', 0), tz=datetime.timezone.utc).strftime('%Y-%m-%d %H:%M')
            print(f"\nContact ID: {cid} | Name: {c_name} | Created: {created}")
            phone = "Yo'q (None)"
            if cf:
                for fld in cf:
                    code = fld.get('field_code')
                    val = [v.get('value') for v in fld.get('values', [])]
                    print(f"  Field {code} ({fld.get('field_name')}): {val}")
                    if code == 'PHONE':
                        phone = val
            print(f"  Phone: {phone}")
        else:
            print(f"Contact ID: {cid} error {r.status_code}")

if __name__ == '__main__':
    main()
