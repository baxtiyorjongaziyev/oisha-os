import json
import os
import sys
import re
import hashlib
import time
import requests
from datetime import datetime

sys.path.insert(0, ".")
os.environ["AMOCRM_TOKEN_DB_PERSIST"] = "0"
sys.stdout.reconfigure(encoding="utf-8")

from src.services.core.crm.amocrm.sync import AmoCRMSync

def sha256_hash(value: str) -> str:
    clean = (value or "").strip().lower()
    return hashlib.sha256(clean.encode("utf-8")).hexdigest() if clean else ""

def format_phone_hash(phone: str) -> str:
    digits = re.sub(r"\D", "", phone or "")
    if len(digits) == 9:
        digits = "998" + digits
    return sha256_hash(digits) if digits else ""

def clean_phone_display(phone: str) -> str:
    digits = re.sub(r"\D", "", phone or "")
    if len(digits) == 9:
        digits = "998" + digits
    if len(digits) >= 12:
        return f"+{digits}"
    return phone

def search_amocrm_contact(query: str, amo: AmoCRMSync, headers: dict) -> dict:
    if not query or len(query.strip()) < 3:
        return {}
    try:
        url = f"{amo.base_url}/api/v4/contacts"
        params = {"query": query.strip(), "limit": 5}
        r = requests.get(url, headers=headers, params=params, timeout=10)
        if r.status_code == 200:
            contacts = r.json().get("_embedded", {}).get("contacts", [])
            if contacts:
                # Pick the first matching contact that has a phone number
                for c in contacts:
                    phone = ""
                    email = ""
                    for cf in c.get("custom_fields_values", []) or []:
                        code = cf.get("field_code")
                        vals = cf.get("values", [])
                        if code == "PHONE" and vals and not phone:
                            phone = str(vals[0].get("value") or "")
                        elif code == "EMAIL" and vals and not email:
                            email = str(vals[0].get("value") or "")
                    if phone:
                        return {
                            "contact_id": c["id"],
                            "contact_name": c.get("name", ""),
                            "phone": phone,
                            "email": email
                        }
        time.sleep(0.15)
    except Exception:
        pass
    return {}

def enrich_and_build():
    source_path = "C:/Users/baxti/.gemini/antigravity/brain/c9d60b95-4130-412b-bdd0-84d46c0b80b5/.system_generated/steps/853/output.txt"
    with open(source_path, "r", encoding="utf-8") as f:
        data = json.load(f)

    records = data.get("records", [])
    paying_records = [r for r in records if (r.get("fields", {}).get("LTV (real tushum)") or 0) > 0]
    print(f"Airtable dagi to'lov qilgan jami mijozlar: {len(paying_records)} ta.\n")

    amo = AmoCRMSync()
    headers = amo._get_headers()

    enriched_clients = []
    capi_events = []
    found_in_amo_count = 0

    for idx, r in enumerate(paying_records, 1):
        fields = r.get("fields", {})
        rec_id = r["id"]
        client_name = fields.get("Mijoz ismi", "").strip()
        phone = fields.get("Telefon raqami", "") or ""
        email = fields.get("Email", "") or ""
        ltv = float(fields.get("LTV (real tushum)") or 0)
        brands = fields.get("Brands", "") or ""
        service = fields.get("Xizmat turi", "") or ""

        match_source = "Airtable"
        amo_contact_id = None

        # Agar telefon raqami yo'q bo'lsa, amoCRM kontaktlaridan qidiramiz
        if not phone:
            search_terms = []
            # Term 1: To'liq ism
            if client_name:
                search_terms.append(client_name)
            # Term 2: "aka", "opa", "SAM", "DF" kabi so'zlarni olib tashlab
            cleaned_name = re.sub(r"\b(aka|opa|SAM|TN|Gr|PCG|DF|SAT|VIP)\b", "", client_name, flags=re.IGNORECASE).strip()
            if cleaned_name and cleaned_name != client_name:
                search_terms.append(cleaned_name)
            # Term 3: Brands
            if brands:
                search_terms.append(brands)

            # Maxsus kalit so'zlar: masalan "Master mould", "Asalhotel", "basito", "Aziya less"
            words = client_name.split()
            for w in words:
                if len(w) > 4 and w.lower() not in ["mijoz", "qurilish", "kompaniya", "bo'yicha", "uchun"]:
                    search_terms.append(w)

            amo_res = {}
            for term in search_terms:
                amo_res = search_amocrm_contact(term, amo, headers)
                if amo_res and amo_res.get("phone"):
                    phone = amo_res["phone"]
                    if not email and amo_res.get("email"):
                        email = amo_res["email"]
                    match_source = f"amoCRM (so'rov: '{term}')"
                    amo_contact_id = amo_res["contact_id"]
                    found_in_amo_count += 1
                    break

        clean_ph = clean_phone_display(phone)
        ph_hash = format_phone_hash(phone)
        em_hash = sha256_hash(email)

        user_data = {}
        if ph_hash:
            user_data["ph"] = [ph_hash]
        if em_hash:
            user_data["em"] = [em_hash]

        # Meta CAPI Purchase event payload
        event_obj = {
            "event_name": "Purchase",
            "event_time": int(time.time()),
            "event_id": f"airtable-{rec_id}-purchase",
            "action_source": "system_generated",
            "user_data": user_data,
            "custom_data": {
                "currency": "UZS",
                "value": ltv,
                "event_source": "crm",
                "lead_event_source": "Oisha-OS",
                "content_name": f"{client_name} ({brands or service or 'Jon Branding'})"
            }
        }
        capi_events.append(event_obj)

        enriched_clients.append({
            "airtable_id": rec_id,
            "name": client_name,
            "phone": clean_ph or "TOPILMADI",
            "email": email or "",
            "ltv": ltv,
            "brands": brands,
            "service": service,
            "phone_source": match_source,
            "amo_contact_id": amo_contact_id
        })

        status_str = f"✅ Tel: {clean_ph} ({match_source})" if phone else "❌ Tel topilmadi"
        print(f"[{idx}/{len(paying_records)}] {client_name} | LTV: {ltv:,.0f} UZS | {status_str}")

    print("\n==================================================")
    print("XULOSA:")
    print(f"Jami to'lov qilgan mijozlar: {len(paying_records)} ta")
    print(f"Airtable'da telefon raqami bor edi: {len(paying_records) - len([c for c in enriched_clients if c['phone_source'] != 'Airtable'])} ta")
    print(f"amoCRM kontaktlaridan topib boyitildi: {found_in_amo_count} ta")
    print(f"Jami Meta CAPI ga tayyorlangan Purchase eventlari: {len(capi_events)} ta")
    print("==================================================")

    output = {
        "generated_at": datetime.now().isoformat(),
        "total_clients": len(enriched_clients),
        "found_in_amocrm_count": found_in_amo_count,
        "clients": enriched_clients,
        "capi_events": capi_events
    }

    with open("data/airtable_amocrm_enriched_capi.json", "w", encoding="utf-8") as f:
        json.dump(output, f, ensure_ascii=False, indent=2)

    print("To'liq natijalar data/airtable_amocrm_enriched_capi.json ga saqlandi.")

if __name__ == "__main__":
    enrich_and_build()
