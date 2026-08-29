"""Inspect categories, accounts, and build dynamic link between Tranzaksiyalar and Oylik P&L."""
import os
import urllib.request, json, sys
sys.stdout.reconfigure(encoding='utf-8')

API_KEY = os.environ.get("AIRTABLE_API_KEY", "").strip()
if not API_KEY:
    raise RuntimeError("AIRTABLE_API_KEY is required in the runtime secret configuration")
BASE_ID = "app8xoyx1XCumYFXV"
H = {"Authorization": f"Bearer {API_KEY}"}

def get_records(table_id, limit=50):
    url = f"https://api.airtable.com/v0/{BASE_ID}/{table_id}?maxRecords={limit}"
    req = urllib.request.Request(url, headers=H)
    with urllib.request.urlopen(req) as resp:
        return json.loads(resp.read().decode()).get("records", [])

def get_schema(table_id):
    url = f"https://api.airtable.com/v0/meta/bases/{BASE_ID}/tables"
    req = urllib.request.Request(url, headers=H)
    with urllib.request.urlopen(req) as resp:
        tables = json.loads(resp.read().decode()).get("tables", [])
        for t in tables:
            if t["id"] == table_id or t["name"] == table_id:
                return t
    return None

print("=== 1. MOLIYA KATEGORIYALARI ===")
cats = get_records("tblRt6aiU6Vy2yLCD", 50)
for r in cats:
    f = r["fields"]
    print(f"  {r['id']}: {f}")

print("\n=== 2. HISOBLAR ===")
accs = get_records("tbl4AYh7E1tirgyqA", 50)
for r in accs:
    f = r["fields"]
    print(f"  {r['id']}: {f}")

print("\n=== 3. TRANZAKSIYALAR MAYDONLARI ===")
t_schema = get_schema("tblrqxqIzyrvg7XpQ")
for f in t_schema.get("fields", []):
    print(f"  {f['name']} ({f['type']}) -> ID: {f['id']}")

print("\n=== 4. OYLIK P&L MAYDONLARI ===")
pnl_schema = get_schema("tblUgfwoxSn2fS4wJ")
for f in pnl_schema.get("fields", []):
    print(f"  {f['name']} ({f['type']}) -> ID: {f['id']}")
