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

r = requests.get(f"https://api.airtable.com/v0/meta/bases/{base_id}/tables", headers=headers)
print("Meta tables status:", r.status_code)
if r.status_code == 200:
    tables = r.json().get("tables", [])
    print(f"Total tables in base: {len(tables)}")
    for t in tables:
        t_id = t["id"]
        t_name = t["name"]
        print(f"Table: {t_id} | {t_name}")
else:
    print("Error:", r.text)
