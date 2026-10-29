import requests
import json
import sys

sys.stdout.reconfigure(encoding="utf-8")

with open("data/amocrm_token.json", encoding="utf-8") as f:
    token = json.load(f)["access_token"]

headers = {"Authorization": f"Bearer {token}"}

# Check first page of contacts
r = requests.get("https://jonbranding.amocrm.ru/api/v4/contacts?limit=5&with=leads", headers=headers, timeout=10)
print("amoCRM contacts status:", r.status_code)
if r.status_code == 200:
    data = r.json()
    contacts = data.get("_embedded", {}).get("contacts", [])
    print(f"Sample contact keys: {list(contacts[0].keys()) if contacts else 'Empty'}")
    if contacts:
        c0 = contacts[0]
        print(f"Sample contact: ID={c0.get('id')} Name={c0.get('name')}")
        for cf in c0.get("custom_fields_values", []) or []:
            print(f"  Field: {cf.get('field_name')} ({cf.get('field_code')}): {cf.get('values')}")
        leads = c0.get("_embedded", {}).get("leads", [])
        print(f"  Linked leads count: {len(leads)}")
