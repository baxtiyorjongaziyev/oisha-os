import json
import sys
import requests

sys.stdout.reconfigure(encoding="utf-8")

with open("data/amocrm_token.json", encoding="utf-8") as f:
    token = json.load(f)["access_token"]

headers = {"Authorization": f"Bearer {token}"}
r = requests.get("https://jonbranding.amocrm.ru/api/v4/leads/custom_fields", headers=headers, timeout=10)

if r.status_code == 200:
    cfs = r.json().get("_embedded", {}).get("custom_fields", [])
    print(f"Total Custom Fields on Leads: {len(cfs)}")
    for cf in cfs:
        print(f"ID: {cf['id']} | Name: {cf['name']} | Code: {cf.get('code')} | Type: {cf['type']}")
else:
    print(r.text)
