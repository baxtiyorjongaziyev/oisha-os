import json
import os
import sys
import re
import csv

sys.stdout.reconfigure(encoding="utf-8")

def generate_meta_audience_csv():
    json_path = "data/airtable_amocrm_enriched_capi.json"
    if not os.path.exists(json_path):
        print("Xatolik: data/airtable_amocrm_enriched_capi.json topilmadi!")
        return

    with open(json_path, "r", encoding="utf-8") as f:
        data = json.load(f)

    clients = data.get("clients", [])
    valid_rows = []

    for c in clients:
        phone = c.get("phone", "")
        # Clean phone to international E.164 without plus: e.g. 998901234567
        digits = re.sub(r"\D", "", phone or "")
        if len(digits) == 9:
            digits = "998" + digits
        if not digits or len(digits) < 11:
            continue

        email = c.get("email", "").strip().lower()
        full_name = c.get("name", "").strip()
        first_name = full_name.split()[0] if full_name else ""
        ltv = c.get("ltv", 0)

        valid_rows.append({
            "phone": digits,
            "email": email,
            "first_name": first_name,
            "value": int(ltv)
        })

    csv_path = "data/meta_custom_audience_buyers.csv"
    with open(csv_path, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=["phone", "email", "first_name", "value"])
        writer.writeheader()
        writer.writerows(valid_rows)

    print(f"✅ Meta Custom Audience uchun {len(valid_rows)} ta to'lovchi mijoz CSV faylga saqlandi:")
    print(f"Manzil: {csv_path}")

if __name__ == "__main__":
    generate_meta_audience_csv()
