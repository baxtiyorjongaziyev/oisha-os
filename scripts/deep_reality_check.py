"""Deep reality check: true transactions, true projects, true table order, true P&L."""
import urllib.request, json, sys
sys.stdout.reconfigure(encoding='utf-8')

API_KEY = "patADXBB0784iii3w.7c1e4380a9736b30f1dd2cb539f6ac49ac097e3452f84f319dc2060834569fdb"
BASE_ID = "app8xoyx1XCumYFXV"
H = {"Authorization": f"Bearer {API_KEY}"}

def fetch_all(table_id):
    records = []
    offset = None
    while True:
        url = f"https://api.airtable.com/v0/{BASE_ID}/{table_id}?pageSize=100"
        if offset:
            url += f"&offset={offset}"
        req = urllib.request.Request(url, headers=H)
        with urllib.request.urlopen(req) as resp:
            d = json.loads(resp.read().decode())
            records.extend(d.get("records", []))
            offset = d.get("offset")
            if not offset:
                break
    return records

print("=" * 80)
print("HAQIQAT AUDITI: AIRTABLE NIMALARDA XATO VA QAYERDA KAMCHILIK BOR?")
print("=" * 80)

# 1. Tranzaksiyalar
trx = fetch_all("tblrqxqIzyrvg7XpQ")
monthly = {}
uncategorized = 0
unconfirmed = 0
for r in trx:
    f = r["fields"]
    turi = f.get("Turi", "")
    kirim_uzs = f.get("Kirim UZS", 0) or 0
    chiqim_uzs = f.get("Chiqim UZS", 0) or 0
    sana = f.get("Sana", "")
    holat = f.get("Holat", "")
    kategoriya = f.get("Kategoriya", [])
    if not kategoriya:
        uncategorized += 1
    if holat != "Tasdiqlangan":
        unconfirmed += 1
    oy = sana[:7] if sana else "Sanasiz"
    if oy not in monthly:
        monthly[oy] = {"kirim": 0, "chiqim": 0, "count": 0}
    monthly[oy]["kirim"] += kirim_uzs
    monthly[oy]["chiqim"] += chiqim_uzs
    monthly[oy]["count"] += 1

print(f"\n1. TRANZAKSIYALAR AUDITI (Jami {len(trx)} ta):")
print(f"   - Kategoriyasiz tranzaksiyalar: {uncategorized} ta (Tizimda tartibsizlik bor!)")
print(f"   - Tasdiqlanmagan tranzaksiyalar: {unconfirmed} ta")
print("\n   Haqiqiy oylik tushum va chiqimlar:")
print(f"   {'Oy':12} | {'Kirim (UZS)':18} | {'Chiqim (UZS)':18} | {'Sof Pul Oqimi (UZS)':20} | {'Trx'}")
print("   " + "-" * 75)
for oy in sorted(monthly.keys()):
    m = monthly[oy]
    sof = m["kirim"] - m["chiqim"]
    print(f"   {oy:12} | {int(m['kirim']):18,d} | {int(m['chiqim']):18,d} | {int(sof):20,d} | {m['count']}")

# 2. Loyihalar
loy = fetch_all("tblJbUobSlygSwYAI")
unpaid_projects = []
for r in loy:
    f = r["fields"]
    nomi = f.get("Loyihani nomi?", "Nomsiz")
    narx = f.get("Jami loyiha narxi (UZS)", 0) or 0
    tolangan = f.get("Jami to'langan (UZS)", 0) or 0
    qoldiq = f.get("Qoldiq to‘lov uzs", 0) or (narx - tolangan)
    bosqich = f.get("Loyiha bosqichi", "")
    if qoldiq > 0 and bosqich != "To'xtatilgan" and bosqich != "Taklif":
        unpaid_projects.append((nomi, narx, tolangan, qoldiq, bosqich))

print(f"\n2. LOYIHALAR AUDITI (Jami {len(loy)} ta):")
print(f"   - Qoldiq qarzdorligi bor faol loyihalar: {len(unpaid_projects)} ta")
for p in unpaid_projects[:5]:
    print(f"     * {p[0]}: Narx: {int(p[1]):,} | To'langan: {int(p[2]):,} | QARZ: {int(p[3]):,} | Bosqich: {p[4]}")

# 3. Oylik P&L jadvali haqiqiyligi
pnl = fetch_all("tblUgfwoxSn2fS4wJ")
print(f"\n3. OYLIK P&L JADVALI HOLATI:")
for r in pnl:
    f = r["fields"]
    oy = f.get("Oy nomi", "")
    pnl_kirim = f.get("Jami Kirim (UZS)", 0) or 0
    pnl_chiqim = f.get("Jami Chiqim (UZS)", 0) or 0
    pnl_sof = f.get("SOLIQDAN KEYINGI SOF FOYDA (UZS)", 0) or 0
    pnl_zaxira = f.get("TAQSIMLANMAGAN FOYDA (UZS)", 0) or 0
    
    # Real kirim from transactions for matching month
    oy_code = oy[:7]
    real_m = monthly.get(oy_code, {"kirim": 0, "chiqim": 0})
    diff_k = pnl_kirim - real_m["kirim"]
    print(f"   Oy: {oy}")
    print(f"     * P&L da yozilgan Kirim:     {int(pnl_kirim):15,d} UZS")
    print(f"     * Tranzaksiyadagi haqiqiy:   {int(real_m['kirim']):15,d} UZS (Farq: {int(diff_k):,})")
    print(f"     * P&L da yozilgan Chiqim:    {int(pnl_chiqim):15,d} UZS")
    print(f"     * Tranzaksiyadagi haqiqiy:   {int(real_m['chiqim']):15,d} UZS")
    print(f"     * Hisoblangan Sof Foyda:     {int(pnl_sof):15,d} UZS")
    print(f"     * Taqsimlanmagan Zaxira:     {int(pnl_zaxira):15,d} UZS")

# 4. Table order
url = f"https://api.airtable.com/v0/meta/bases/{BASE_ID}/tables"
req = urllib.request.Request(url, headers=H)
with urllib.request.urlopen(req) as resp:
    tables = json.loads(resp.read().decode()).get("tables", [])
print(f"\n4. JADVALLAR KETMA-KETLIGI ({len(tables)} ta jadval):")
for i, t in enumerate(tables, 1):
    print(f"   {i:2d}. {t['name']}")
