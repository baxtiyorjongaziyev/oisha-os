"""Connect Tranzaksiyalar and Oylik P&L with dynamic link and rollups, and auto-link all transactions."""
import urllib.request, json, sys, time

sys.stdout.reconfigure(encoding='utf-8')

API_KEY = "patADXBB0784iii3w.7c1e4380a9736b30f1dd2cb539f6ac49ac097e3452f84f319dc2060834569fdb"
BASE_ID = "app8xoyx1XCumYFXV"
TRX_TABLE_ID = "tblrqxqIzyrvg7XpQ"
PNL_TABLE_ID = "tblUgfwoxSn2fS4wJ"
CAT_TABLE_ID = "tblRt6aiU6Vy2yLCD"
ACC_TABLE_ID = "tbl4AYh7E1tirgyqA"

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

def get_all_records(table_id):
    records = []
    offset = None
    while True:
        url = f"https://api.airtable.com/v0/{BASE_ID}/{table_id}?pageSize=100"
        if offset:
            url += f"&offset={offset}"
        data = api_get(url)
        records.extend(data.get("records", []))
        offset = data.get("offset")
        if not offset:
            break
    return records

print("--- 1. OYLIK P&L REKORDLARINI XARITASI ---")
pnl_records = get_all_records(PNL_TABLE_ID)
pnl_month_map = {}
for r in pnl_records:
    code = r["fields"].get("Oy nomi", "")[:7]
    if code:
        pnl_month_map[code] = r["id"]
print(f"Loaded {len(pnl_month_map)} months in Oylik P&L: {sorted(pnl_month_map.keys())}")

print("\n--- 2. TRANZAKSIYALARNI OYLIK P&L GA VA KATEGORIYALARGA BOG'LASH ---")
cats = get_all_records(CAT_TABLE_ID)
cat_name_to_id = {c["fields"].get("Kategoriya"): c["id"] for c in cats if "Kategoriya" in c["fields"]}
accs = get_all_records(ACC_TABLE_ID)
acc_name_to_id = {a["fields"].get("Hisob nomi"): a["id"] for a in accs if "Hisob nomi" in a["fields"]}

default_income_cat = cat_name_to_id.get("Branding loyiha daromadi") or list(cat_name_to_id.values())[0]
default_cogs_cat = cat_name_to_id.get("Freelancer va ishlab chiqarish") or list(cat_name_to_id.values())[0]
default_opex_cat = cat_name_to_id.get("Ofis va ijara") or list(cat_name_to_id.values())[0]
default_acc = acc_name_to_id.get("Kassa UZS") or list(acc_name_to_id.values())[0]

all_trx = get_all_records(TRX_TABLE_ID)
print(f"Loaded {len(all_trx)} transactions.")

trx_updates = []
for r in all_trx:
    f = r["fields"]
    sana = f.get("Sana", "")
    turi = f.get("Turi", "")
    izoh = (f.get("Izoh") or "").lower()
    
    fields_to_update = {}
    
    # 1. Link to Oylik P&L
    if sana and len(sana) >= 7:
        m_code = sana[:7]
        target_pnl_id = pnl_month_map.get(m_code)
        current_links = f.get("Oylik P&L", [])
        if target_pnl_id and (not current_links or current_links[0] != target_pnl_id):
            fields_to_update["Oylik P&L"] = [target_pnl_id]
            
    # 2. Fix empty category
    if not f.get("Kategoriya"):
        if turi == "Kirim":
            if "naming" in izoh:
                fields_to_update["Kategoriya"] = [cat_name_to_id.get("Naming loyiha daromadi", default_income_cat)]
            else:
                fields_to_update["Kategoriya"] = [default_income_cat]
        elif turi == "Chiqim":
            if any(k in izoh for k in ["dizayn", "frilans", "3d", "motion", "logo", "shrift"]):
                fields_to_update["Kategoriya"] = [default_cogs_cat]
            elif any(k in izoh for k in ["reklama", "target", "marketing"]):
                fields_to_update["Kategoriya"] = [cat_name_to_id.get("Marketing va reklama", default_opex_cat)]
            elif any(k in izoh for k in ["ijara", "ofis"]):
                fields_to_update["Kategoriya"] = [cat_name_to_id.get("Ofis va ijara", default_opex_cat)]
            elif any(k in izoh for k in ["dastur", "chatgpt", "figma", "midjourney"]):
                fields_to_update["Kategoriya"] = [cat_name_to_id.get("Dasturiy ta’minot", default_opex_cat)]
            else:
                fields_to_update["Kategoriya"] = [default_opex_cat]
                
    # 3. Fix empty account
    if not f.get("Hisob"):
        fields_to_update["Hisob"] = [default_acc]
        
    if fields_to_update:
        trx_updates.append({
            "id": r["id"],
            "fields": fields_to_update
        })

print(f"Total transactions to update: {len(trx_updates)}")
for i in range(0, len(trx_updates), 10):
    chunk = trx_updates[i:i+10]
    api_patch(f"https://api.airtable.com/v0/{BASE_ID}/{TRX_TABLE_ID}", {"records": chunk})
    time.sleep(0.2)
    if (i // 10) % 5 == 0:
        print(f"  Updated batch {i+1} to {min(i+10, len(trx_updates))}...")

print("\n--- 3. OYLIK P&L REKORDLARINI HAQIQIY TRANZAKSIYALAR BO'YICHA HISOBLASH ---")
all_trx_updated = get_all_records(TRX_TABLE_ID)
cat_lookup = {c["id"]: c["fields"] for c in cats}

monthly_sums = {}
for r in all_trx_updated:
    f = r["fields"]
    sana = f.get("Sana", "")
    if not sana or len(sana) < 7:
        continue
    m_code = sana[:7]
    if m_code not in monthly_sums:
        monthly_sums[m_code] = {"kirim": 0, "cogs": 0, "opex": 0, "soliq": 0}
        
    turi = f.get("Turi", "")
    summa = f.get("Summa UZS", 0) or 0
    kategoriya_ids = f.get("Kategoriya", [])
    cat_info = cat_lookup.get(kategoriya_ids[0], {}) if kategoriya_ids else {}
    cat_guruh = cat_info.get("Guruh", "")
    cat_nomi = cat_info.get("Kategoriya", "")
    
    if turi == "Kirim":
        monthly_sums[m_code]["kirim"] += summa
    elif turi == "Chiqim":
        if cat_guruh == "Loyiha xarajati" or "Freelancer" in cat_nomi:
            monthly_sums[m_code]["cogs"] += summa
        elif cat_guruh == "Soliq" or "Soliq" in cat_nomi:
            monthly_sums[m_code]["soliq"] += summa
        else:
            monthly_sums[m_code]["opex"] += summa

pnl_records = get_all_records(PNL_TABLE_ID)
pnl_updates = []
for r in pnl_records:
    m_code = r["fields"].get("Oy nomi", "")[:7]
    sums = monthly_sums.get(m_code, {"kirim": 0, "cogs": 0, "opex": 0, "soliq": 0})
    
    soliq = sums["soliq"] if sums["soliq"] > 0 else int(sums["kirim"] * 0.04)
    yalpi = sums["kirim"] - sums["cogs"]
    ebt = yalpi - sums["opex"]
    net_profit = ebt - soliq
    dividend = int(net_profit * 0.6) if net_profit > 0 else 0
    
    pnl_updates.append({
        "id": r["id"],
        "fields": {
            "Jami Kirim (UZS)": sums["kirim"],
            "Loyiha xarajatlari — COGS (UZS)": sums["cogs"],
            "Operatsion xarajatlar — OPEX (UZS)": sums["opex"],
            "Soliq xarajati (UZS)": soliq,
            "Taqsimlangan Dividendlar (UZS)": dividend
        }
    })

print(f"Updating {len(pnl_updates)} P&L records with real calculated figures...")
for i in range(0, len(pnl_updates), 10):
    chunk = pnl_updates[i:i+10]
    api_patch(f"https://api.airtable.com/v0/{BASE_ID}/{PNL_TABLE_ID}", {"records": chunk})
    time.sleep(0.2)

print("\nSUCCESS: Tranzaksiyalar va Oylik P&L to'liq jonli bog'landi va hisoblandi!")
