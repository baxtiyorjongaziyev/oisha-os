import json
import sys
import re
from datetime import datetime
from collections import defaultdict

sys.stdout.reconfigure(encoding="utf-8")

with open("data/airtable_all_mijozlar.json", "r", encoding="utf-8") as f:
    mijozlar = json.load(f)

with open("data/airtable_all_loyihalar.json", "r", encoding="utf-8") as f:
    loyihalar = json.load(f)

with open("data/airtable_all_tranzaksiyalar.json", "r", encoding="utf-8") as f:
    tranzaksiyalar = json.load(f)

with open("data/amocrm_all_contacts.json", "r", encoding="utf-8") as f:
    amocrm_contacts = json.load(f)

print(f"Loaded: {len(mijozlar)} Mijozlar, {len(loyihalar)} Loyihalar, {len(tranzaksiyalar)} Tranzaksiyalar, {len(amocrm_contacts)} amoCRM Contacts.")

def clean_phone(p: str) -> str:
    if not p:
        return ""
    digits = re.sub(r"\D", "", str(p))
    if len(digits) == 9:
        return "998" + digits
    if len(digits) == 12 and digits.startswith("998"):
        return digits
    return digits

# 1. Index amoCRM contacts by phone and name
amo_phone_map = {}
for c in amocrm_contacts:
    cid = c.get("id")
    cname = c.get("name")
    for cf in c.get("custom_fields_values", []) or []:
        if cf.get("field_code") == "PHONE":
            for val in cf.get("values", []):
                p_clean = clean_phone(val.get("value"))
                if p_clean and len(p_clean) >= 9:
                    amo_phone_map[p_clean[-9:]] = c

print(f"Indexed amoCRM unique 9-digit phones: {len(amo_phone_map)}")

# 2. Build Loyihalar lookup by record ID
proj_map = {p["id"]: p.get("fields", {}) for p in loyihalar}

# 3. Build Tranzaksiyalar lookup for Kirim transactions
# Group kirim by project ID or client name in Izoh
kirim_by_proj = defaultdict(list)
earliest_kirim_by_izoh = []

for t in tranzaksiyalar:
    f = t.get("fields", {})
    turi = f.get("Turi")
    if str(turi).lower() == "kirim":
        sana = f.get("Sana") or "2099-12-31"
        summa = f.get("Summa", 0)
        valyuta = f.get("Valyuta", "UZS")
        izoh = f.get("Izoh", "")
        projs = f.get("Loyiha", [])
        if projs:
            for pid in projs:
                kirim_by_proj[pid].append({
                    "sana": sana,
                    "summa": summa,
                    "valyuta": valyuta,
                    "izoh": izoh
                })
        earliest_kirim_by_izoh.append({
            "sana": sana,
            "summa": summa,
            "valyuta": valyuta,
            "izoh": izoh,
            "projs": projs
        })

# 4. Process all Airtable Mijozlar
paying_clients = []
for m in mijozlar:
    mf = m.get("fields", {})
    name = mf.get("Mijoz ismi") or "Noma'lum"
    brand = mf.get("Brands") or ""
    phone = mf.get("Telefon raqami") or ""
    clean_p = clean_phone(phone)
    faoliyat = mf.get("Faoliyat turi") or ""
    ltv = mf.get("LTV (real tushum)", 0)
    services = mf.get("Xizmat turi", [])
    first_date = mf.get("CAC — ilk to‘lovli loyiha starti") or mf.get("CAC — birinchi mijoz oyi (proksi)")
    
    # Check linked projects
    client_projs = []
    proj_dates = []
    for pid in mf.get("Loyihalari", []):
        if pid in proj_map:
            pf = proj_map[pid]
            pname = pf.get("Loyiha nomi", "")
            pstart = pf.get("Start sana") or pf.get("CAC — to‘lovli loyiha starti", "")
            if pstart:
                proj_dates.append(pstart[:10])
            client_projs.append({
                "id": pid,
                "name": pname,
                "start": pstart,
                "status": pf.get("To‘lov statusi", ""),
                "price": pf.get("Kelishilgan narx", 0),
                "paid": pf.get("Jami to'langan (UZS)", 0),
                "services": pf.get("Xizmat turi", [])
            })
    
    if proj_dates:
        min_proj_date = min(proj_dates)
        if not first_date or min_proj_date < first_date:
            first_date = min_proj_date

    # Cross-match with amoCRM contact
    matched_amo = None
    if clean_p and len(clean_p) >= 9:
        matched_amo = amo_phone_map.get(clean_p[-9:])

    paying_clients.append({
        "airtable_id": m["id"],
        "name": name,
        "brand": brand,
        "phone": phone,
        "clean_phone": clean_p,
        "faoliyat": faoliyat,
        "ltv": ltv,
        "services": services,
        "first_payment_date": first_date or "Noma'lum",
        "projects": client_projs,
        "matched_amocrm_contact": {
            "id": matched_amo.get("id"),
            "name": matched_amo.get("name"),
            "linked_leads_count": len(matched_amo.get("_embedded", {}).get("leads", []))
        } if matched_amo else None
    })

# Sort chronologically by first payment date
# Put valid dates first ascending, then 'Noma'lum'
def sort_key(x):
    d = x["first_payment_date"]
    if d and d != "Noma'lum" and len(d) >= 4 and d[0].isdigit():
        return (0, d)
    return (1, d)

paying_clients.sort(key=sort_key)

print(f"\nTop 15 earliest paying clients in Airtable history:")
for idx, c in enumerate(paying_clients[:15], 1):
    amo_str = f"amoCRM ID: {c['matched_amocrm_contact']['id']}" if c['matched_amocrm_contact'] else "amoCRM: Topilmadi"
    print(f"{idx:2d}. [{c['first_payment_date']}] {c['name']:20s} | Brand: {c['brand']:16s} | LTV: {c['ltv']:10,d} UZS | Tel: {c['phone']} | {amo_str}")

with open("data/airtable_paying_clients_processed.json", "w", encoding="utf-8") as f:
    json.dump(paying_clients, f, ensure_ascii=False, indent=2)

print("\nSaved data/airtable_paying_clients_processed.json successfully!")
