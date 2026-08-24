"""Deep audit: check if P&L data is real or fake."""
import urllib.request, json, sys
sys.stdout.reconfigure(encoding='utf-8')

API_KEY = "patADXBB0784iii3w.7c1e4380a9736b30f1dd2cb539f6ac49ac097e3452f84f319dc2060834569fdb"
BASE_ID = "app8xoyx1XCumYFXV"
H = {"Authorization": f"Bearer {API_KEY}"}

def fetch(table_id, max_records=100):
    url = f"https://api.airtable.com/v0/{BASE_ID}/{table_id}?pageSize={max_records}"
    req = urllib.request.Request(url, headers=H)
    with urllib.request.urlopen(req) as resp:
        return json.loads(resp.read().decode()).get("records", [])

print("=" * 70)
print("SHAVQATSIZ AUDIT: AIRTABLE HAQIQIY HOLATI")
print("=" * 70)

# 1. P&L table - real or fabricated?
print("\n--- 1. OYLIK P&L JADVALI ---")
pnl = fetch("tblUgfwoxSn2fS4wJ")
for r in pnl:
    f = r["fields"]
    oy = f.get("Oy nomi", "?")
    kirim = f.get("Jami Kirim (UZS)", 0)
    cogs = f.get("Loyiha xarajatlari \u2014 COGS (UZS)", 0)
    opex = f.get("Operatsion xarajatlar \u2014 OPEX (UZS)", 0)
    soliq = f.get("Soliq xarajati (UZS)", 0)
    dividend = f.get("Taqsimlangan Dividendlar (UZS)", 0)
    print(f"  {oy}: Kirim={kirim:,} | COGS={cogs:,} | OPEX={opex:,} | Soliq={soliq:,} | Dividend={dividend:,}")

# 2. Real transactions
print("\n--- 2. HAQIQIY TRANZAKSIYALAR ---")
trx = fetch("tblrqxqIzyrvg7XpQ")
print(f"  Jami tranzaksiyalar soni: {len(trx)}")
kirim_total = 0
chiqim_total = 0
months = {}
for r in trx:
    f = r["fields"]
    turi = f.get("Turi", "")
    summa = f.get("Summa (UZS)", 0) or 0
    sana = f.get("Sana", "")
    oy_key = sana[:7] if sana else "???"
    if oy_key not in months:
        months[oy_key] = {"kirim": 0, "chiqim": 0, "count": 0}
    months[oy_key]["count"] += 1
    if turi == "Kirim":
        kirim_total += summa
        months[oy_key]["kirim"] += summa
    elif turi == "Chiqim":
        chiqim_total += summa
        months[oy_key]["chiqim"] += summa

print(f"  Jami haqiqiy kirimlar: {int(kirim_total):,} UZS")
print(f"  Jami haqiqiy chiqimlar: {int(chiqim_total):,} UZS")
print(f"  Oylar bo'yicha:")
for oy in sorted(months.keys()):
    m = months[oy]
    print(f"    {oy}: Kirim={int(m['kirim']):,} | Chiqim={int(m['chiqim']):,} | Trx={m['count']}")

# 3. Loyihalar real revenue
print("\n--- 3. LOYIHALAR HAQIQIY TUSHUM ---")
loy = fetch("tblJbUobSlygSwYAI")
total_narx = 0
total_tolangan = 0
faol = 0
yakunlangan = 0
toxtatilgan = 0
for r in loy:
    f = r["fields"]
    narx = f.get("Loyiha narxi (UZS)", 0) or 0
    tolangan = f.get("To'langan summa (UZS)", 0) or 0
    bosqich = f.get("Loyiha bosqichi", "")
    total_narx += narx
    total_tolangan += tolangan
    if bosqich == "Yakunlangan":
        yakunlangan += 1
    elif bosqich == "To'xtatilgan":
        toxtatilgan += 1
    elif bosqich:
        faol += 1
print(f"  Jami loyihalar: {len(loy)} (Faol: {faol}, Yakunlangan: {yakunlangan}, To'xtatilgan: {toxtatilgan})")
print(f"  Jami loyiha narxi: {int(total_narx):,} UZS")
print(f"  Jami to'langan: {int(total_tolangan):,} UZS")
print(f"  Undirilinmagan qarzdorlik: {int(total_narx - total_tolangan):,} UZS")

# 4. Check table order
print("\n--- 4. JADVALLAR KETMA-KETLIGI (HOZIRGI HOLAT) ---")
url = f"https://api.airtable.com/v0/meta/bases/{BASE_ID}/tables"
req = urllib.request.Request(url, headers=H)
with urllib.request.urlopen(req) as resp:
    tables = json.loads(resp.read().decode()).get("tables", [])
    for i, t in enumerate(tables, 1):
        fields_count = len(t.get("fields", []))
        views_count = len(t.get("views", []))
        print(f"  {i:2d}. {t['name']:30s} ({fields_count} fields, {views_count} views)")

# 5. P&L vs Reality comparison
print("\n" + "=" * 70)
print("XULOSA: P&L RAQAMLARI HAQIQIYGA MOS KELADIMI?")
print("=" * 70)
pnl_total_kirim = sum(r["fields"].get("Jami Kirim (UZS)", 0) for r in pnl)
print(f"  P&L jadvalidagi jami kirim:    {int(pnl_total_kirim):,} UZS")
print(f"  Tranzaksiyalardagi jami kirim: {int(kirim_total):,} UZS")
print(f"  Loyihalardan to'langan:        {int(total_tolangan):,} UZS")
if pnl_total_kirim > 0 and kirim_total > 0:
    diff = abs(pnl_total_kirim - kirim_total)
    print(f"  FARQ: {int(diff):,} UZS")
    if diff > 1000000:
        print(f"  !!! OGOHLANTIRISH: Raqamlar MOS KELMAYDI !!!")
elif pnl_total_kirim > 0 and kirim_total == 0:
    print(f"  !!! P&L da raqamlar bor lekin tranzaksiyalar bo'sh yoki 0 !!!")
