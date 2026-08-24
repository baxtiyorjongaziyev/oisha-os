import urllib.request, json, sys

API_KEY = "patADXBB0784iii3w.7c1e4380a9736b30f1dd2cb539f6ac49ac097e3452f84f319dc2060834569fdb"
BASE_ID = "app8xoyx1XCumYFXV"
H = {"Authorization": f"Bearer {API_KEY}"}

def get_records(table_id, limit=100):
    url = f"https://api.airtable.com/v0/{BASE_ID}/{table_id}?maxRecords={limit}"
    req = urllib.request.Request(url, headers=H)
    with urllib.request.urlopen(req) as resp:
        return json.loads(resp.read().decode()).get("records", [])

print("1. TRANZAKSIYALAR:")
trx = get_records("tblrqxqIzyrvg7XpQ", 100)
print(f"   Tranzaksiyalar soni (oxirgi 100): {len(trx)}")
k_sum = sum((r["fields"].get("Kirim UZS", 0) or 0) for r in trx)
c_sum = sum((r["fields"].get("Chiqim UZS", 0) or 0) for r in trx)
print(f"   Jami Kirim: {k_sum:,} UZS | Jami Chiqim: {c_sum:,} UZS")

print("\n2. OYLIK P&L JADVALI:")
pnl = get_records("tblUgfwoxSn2fS4wJ", 10)
for r in pnl:
    f = r["fields"]
    print(f"   {f.get('Oy nomi')}: Kirim={f.get('Jami Kirim (UZS)',0):,} | COGS={f.get('Loyiha xarajatlari — COGS (UZS)',0):,} | OPEX={f.get('Operatsion xarajatlar — OPEX (UZS)',0):,} | Sof Foyda={f.get('SOLIQDAN KEYINGI SOF FOYDA (UZS)',0):,} | Zaxira={f.get('TAQSIMLANMAGAN FOYDA (UZS)',0):,}")

print("\n3. JADVALLAR KETMA-KETLIGI:")
req = urllib.request.Request(f"https://api.airtable.com/v0/meta/bases/{BASE_ID}/tables", headers=H)
with urllib.request.urlopen(req) as resp:
    tables = json.loads(resp.read().decode()).get("tables", [])
    for i, t in enumerate(tables, 1):
        print(f"   {i:2d}. {t['name']}")
