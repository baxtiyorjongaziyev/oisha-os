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

# 1. Inspect Mijozlar
print("--- 1. MIJOZLAR (tblYeFpWhQIMmrWPZ) ---")
r_m = requests.get(f"https://api.airtable.com/v0/{base_id}/tblYeFpWhQIMmrWPZ?maxRecords=10", headers=headers)
if r_m.status_code == 200:
    recs = r_m.json().get("records", [])
    print(f"Total sample Mijozlar: {len(recs)}")
    for r in recs[:5]:
        print("Mijoz:", json.dumps(r.get("fields", {}), ensure_ascii=False))

# 2. Inspect Loyihalar
print("\n--- 2. LOYIHALAR (tblJbUobSlygSwYAI) ---")
r_l = requests.get(f"https://api.airtable.com/v0/{base_id}/tblJbUobSlygSwYAI?maxRecords=10", headers=headers)
if r_l.status_code == 200:
    recs = r_l.json().get("records", [])
    print(f"Total sample Loyihalar: {len(recs)}")
    for r in recs[:5]:
        print("Loyiha:", json.dumps(r.get("fields", {}), ensure_ascii=False))

# 3. Inspect Tranzaksiyalar (Kirim)
print("\n--- 3. TRANZAKSIYALAR (tblrqxqIzyrvg7XpQ) ---")
# Filter where Turi = 'Kirim'
r_t = requests.get(f"https://api.airtable.com/v0/{base_id}/tblrqxqIzyrvg7XpQ?filterByFormula={{Turi}}='Kirim'&sort[0][field]=Sana&sort[0][direction]=asc&maxRecords=10", headers=headers)
if r_t.status_code == 200:
    recs = r_t.json().get("records", [])
    print(f"Earliest Kirim transactions count: {len(recs)}")
    for r in recs[:10]:
        f = r.get("fields", {})
        print(f"Sana: {f.get('Sana')} | Summa: {f.get('Summa')} {f.get('Valyuta')} | Kategoriya: {f.get('Kategoriya')} | Izoh: {f.get('Izoh')}")
else:
    print("Tranzaksiyalar query error:", r_t.text)
