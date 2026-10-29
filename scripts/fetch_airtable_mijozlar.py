import requests
import json
import sys

sys.stdout.reconfigure(encoding="utf-8")

env_path = r"C:\Users\baxti\playground\oisha-os_backup_\.env"
env = {}
with open(env_path, "r", encoding="utf-8") as f:
    for l in f:
        if "=" in l and not l.startswith("#"):
            k, v = l.strip().split("=", 1)
            env[k.strip()] = v.strip()

key = env.get("AIRTABLE_API_KEY")
base_id = "app8xoyx1XCumYFXV"
headers = {"Authorization": f"Bearer {key}"}

# Get all records from Mijozlar (tblYeFpWhQIMmrWPZ)
records = []
offset = None
while True:
    url = f"https://api.airtable.com/v0/{base_id}/tblYeFpWhQIMmrWPZ?pageSize=100"
    if offset:
        url += f"&offset={offset}"
    r = requests.get(url, headers=headers)
    if r.status_code == 200:
        data = r.json()
        records.extend(data.get("records", []))
        offset = data.get("offset")
        if not offset:
            break
    else:
        print("Error:", r.text)
        break

print(f"Total Mijozlar in Airtable: {len(records)}")
if records:
    print("Sample Mijoz record:")
    print(json.dumps(records[0], indent=2, ensure_ascii=False))

with open("data/airtable_all_mijozlar.json", "w", encoding="utf-8") as f:
    json.dump(records, f, ensure_ascii=False, indent=2)
