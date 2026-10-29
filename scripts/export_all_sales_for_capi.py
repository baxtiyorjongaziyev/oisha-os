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

def build_capi_data():
    amo = AmoCRMSync()
    headers = amo._get_headers()

    print("amoCRM dan barcha 142 ('Sotuv bo'ldi') statusidagi bitimlar olinmoqda...")
    # Fetch all won leads (page by page if needed)
    all_leads = []
    page = 1
    while True:
        url = f"{amo.base_url}/api/v4/leads"
        params = {
            "filter[status][]": 142,
            "with": "contacts",
            "limit": 250,
            "page": page
        }
        r = requests.get(url, headers=headers, params=params, timeout=25)
        if r.status_code != 200:
            break
        leads = r.json().get("_embedded", {}).get("leads", [])
        if not leads:
            break
        all_leads.extend(leads)
        page += 1

    print(f"Jami olingan sotuv bitimlari: {len(all_leads)} ta.")

    capi_events = []
    sales_summary = []

    # Cache contacts to avoid duplicate GETs
    contact_cache = {}

    for idx, lead in enumerate(all_leads, 1):
        lid = lead["id"]
        name = lead["name"]
        price = float(lead.get("price") or 0)
        closed_at = lead.get("closed_at") or lead.get("updated_at") or int(time.time())

        # Find contact phone & email
        contact_ids = [c["id"] for c in lead.get("_embedded", {}).get("contacts", [])]
        phone = ""
        email = ""
        contact_name = ""

        if contact_ids:
            cid = contact_ids[0]
            if cid in contact_cache:
                cdata = contact_cache[cid]
            else:
                try:
                    r_c = requests.get(f"{amo.base_url}/api/v4/contacts/{cid}", headers=headers, timeout=10)
                    cdata = r_c.json() if r_c.status_code == 200 else {}
                    contact_cache[cid] = cdata
                except Exception:
                    cdata = {}

            contact_name = cdata.get("name", "")
            for cf in cdata.get("custom_fields_values", []) or []:
                code = cf.get("field_code")
                vals = cf.get("values", [])
                if code == "PHONE" and vals and not phone:
                    phone = str(vals[0].get("value") or "")
                elif code == "EMAIL" and vals and not email:
                    email = str(vals[0].get("value") or "")

        # Look for Meta Lead ID in custom fields
        meta_lead_id = ""
        for cf in lead.get("custom_fields_values", []) or []:
            fn = cf.get("field_name", "").lower()
            vals = cf.get("values", [])
            if "meta" in fn or "leadgen" in fn:
                if vals:
                    meta_lead_id = str(vals[0].get("value") or "")

        # Meta CAPI User Data
        user_data = {}
        if phone:
            ph_hash = format_phone_hash(phone)
            if ph_hash:
                user_data["ph"] = [ph_hash]
        if email:
            em_hash = sha256_hash(email)
            if em_hash:
                user_data["em"] = [em_hash]
        if meta_lead_id:
            user_data["lead_id"] = meta_lead_id

        # Even without meta_lead_id, Meta CAPI matches via phone hash (ph) and email (em)
        event_payload = {
            "event_name": "Purchase",
            "event_time": int(closed_at),
            "event_id": f"amo-lead-{lid}-purchase",
            "action_source": "system_generated",
            "user_data": user_data,
            "custom_data": {
                "currency": "UZS",
                "value": price if price > 0 else 5000000.0,
                "event_source": "crm",
                "lead_event_source": "Oisha-OS",
                "content_name": name
            }
        }

        capi_events.append(event_payload)
        sales_summary.append({
            "lead_id": lid,
            "name": name,
            "price": price,
            "phone": phone,
            "email": email,
            "meta_lead_id": meta_lead_id,
            "closed_at": datetime.fromtimestamp(closed_at).strftime("%Y-%m-%d %H:%M:%S")
        })

    # Save to data/capi_purchase_payloads.json
    output_data = {
        "generated_at": datetime.now().isoformat(),
        "total_sales_count": len(capi_events),
        "events": capi_events,
        "summary": sales_summary
    }

    with open("data/capi_purchase_payloads.json", "w", encoding="utf-8") as f:
        json.dump(output_data, f, ensure_ascii=False, indent=2)

    print(f"\n✅ Jami {len(capi_events)} ta to'lov qilgan mijoz ma'lumotlari CAPI formatida tayyorlandi.")
    print("Fayl: data/capi_purchase_payloads.json")

if __name__ == "__main__":
    build_capi_data()
