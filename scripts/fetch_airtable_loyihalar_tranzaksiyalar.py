import requests
import json
import sys
import os

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

def fetch_table(table_id: str, name: str, out_file: str):
    print(f"Fetching {name} ({table_id})...")
    records = []
    offset = None
    while True:
        url = f"https://api.airtable.com/v0/{base_id}/{table_id}?pageSize=100"
        if offset:
            url += f"&offset={offset}"
        r = requests.get(url, headers=headers, timeout=20)
        if r.status_code == 200:
            data = r.json()
            records.extend(data.get("records", []))
            offset = data.get("offset")
            if not offset:
                break
        else:
            print(f"Error fetching {name}: {r.status_code} {r.text}")
            break
    print(f"Total {name} fetched: {len(records)}")
    with open(out_file, "w", encoding="utf-8") as f:
        json.dump(records, f, ensure_ascii=False, indent=2)
    return records

fetch_table("tblJbUobSlygSwYAI", "Loyihalar", "data/airtable_all_loyihalar.json")
fetch_table("tblrqxqIzyrvg7XpQ", "Tranzaksiyalar", "data/airtable_all_tranzaksiyalar.json")
print("Done fetching Airtable projects and transactions!")
