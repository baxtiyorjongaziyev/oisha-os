"""Populate all months and link all transactions to the new clean Oylik P&L table (tblAgVaGlVory2yAW)."""
import urllib.request, json, sys, time

sys.stdout.reconfigure(encoding='utf-8')

API_KEY = "patADXBB0784iii3w.7c1e4380a9736b30f1dd2cb539f6ac49ac097e3452f84f319dc2060834569fdb"
BASE_ID = "app8xoyx1XCumYFXV"
NEW_PNL_ID = "tblAgVaGlVory2yAW"
TRX_TABLE_ID = "tblrqxqIzyrvg7XpQ"

H = {
    "Authorization": f"Bearer {API_KEY}",
    "Content-Type": "application/json"
}

def api_get(url):
    req = urllib.request.Request(url, headers=H)
    with urllib.request.urlopen(req) as resp:
        return json.loads(resp.read().decode())

def api_post(url, data):
    req = urllib.request.Request(url, data=json.dumps(data).encode('utf-8'), headers=H, method='POST')
    with urllib.request.urlopen(req) as resp:
        return json.loads(resp.read().decode())

def api_patch(url, data):
    req = urllib.request.Request(url, data=json.dumps(data).encode('utf-8'), headers=H, method='PATCH')
    with urllib.request.urlopen(req) as resp:
        return json.loads(resp.read().decode())

# 1. Populate all months (2025-02 to 2027-12)
uzbek_months = {
    "01": "Yanvar", "02": "Fevral", "03": "Mart", "04": "Aprel",
    "05": "May", "06": "Iyun", "07": "Iyul", "08": "Avgust",
    "09": "Sentabr", "10": "Oktabr", "11": "Noyabr", "12": "Dekabr"
}

all_months = []
# 2025 months
for m in range(2, 13):
    m_str = f"{m:02d}"
    all_months.append({"fields": {"Oy nomi": f"2025-{m_str} ({uzbek_months[m_str]} 2025)", "Sana": f"2025-{m_str}-01"}})
# 2026 months
for m in range(1, 13):
    m_str = f"{m:02d}"
    all_months.append({"fields": {"Oy nomi": f"2026-{m_str} ({uzbek_months[m_str]} 2026)", "Sana": f"2026-{m_str}-01"}})
# 2027 months
for m in range(1, 13):
    m_str = f"{m:02d}"
    all_months.append({"fields": {"Oy nomi": f"2027-{m_str} ({uzbek_months[m_str]} 2027)", "Sana": f"2027-{m_str}-01"}})

month_id_map = {}
for i in range(0, len(all_months), 10):
    chunk = all_months[i:i+10]
    res = api_post(f"https://api.airtable.com/v0/{BASE_ID}/{NEW_PNL_ID}", {"records": chunk})
    for r in res.get("records", []):
        code = r["fields"].get("Oy nomi", "")[:7]
        month_id_map[code] = r["id"]

print(f"Created {len(month_id_map)} months in new table!")

# 2. Link all transactions to the new clean table
print("Fetching all transactions...")
all_trx = []
offset = None
while True:
    url = f"https://api.airtable.com/v0/{BASE_ID}/{TRX_TABLE_ID}?pageSize=100"
    if offset:
        url += f"&offset={offset}"
    d = api_get(url)
    all_trx.extend(d.get("records", []))
    offset = d.get("offset")
    if not offset:
        break

trx_updates = []
for r in all_trx:
    sana = r["fields"].get("Sana", "")
    if sana and len(sana) >= 7:
        m_code = sana[:7]
        target_id = month_id_map.get(m_code)
        if target_id:
            trx_updates.append({
                "id": r["id"],
                "fields": {
                    "P&L Oy": [target_id]
                }
            })

print(f"Updating {len(trx_updates)} transactions with new P&L Oy link...")
for i in range(0, len(trx_updates), 10):
    chunk = trx_updates[i:i+10]
    api_patch(f"https://api.airtable.com/v0/{BASE_ID}/{TRX_TABLE_ID}", {"records": chunk})
    time.sleep(0.1)

print("\nSUCCESS: All records populated and dynamically linked to clean table!")
