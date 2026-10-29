import json
import os
import sys
import requests
from datetime import datetime

sys.path.insert(0, ".")
os.environ["AMOCRM_TOKEN_DB_PERSIST"] = "0"
sys.stdout.reconfigure(encoding="utf-8")

from src.services.core.crm.amocrm.sync import AmoCRMSync

def record_aslkids_sale():
    amo = AmoCRMSync()
    headers = amo._get_headers()

    lead_id = 36602701
    payload = {
        "name": "Aslbek (Asl kids) - Patent",
        "pipeline_id": 11162698, # Sotuv Bo'limi
        "status_id": 142,        # Sotuv bo'ldi
        "price": 5000000,        # 5,000,000 UZS
        "_embedded": {
            "tags": [
                {"name": "Mijoz"},
                {"name": "Sotuv"},
                {"name": "Patent"},
                {"name": "Asl kids"}
            ]
        }
    }

    print(f"Lead ID {lead_id} yangilanmoqda...")
    r = requests.patch(f"{amo.base_url}/api/v4/leads/{lead_id}", headers=headers, json=payload, timeout=20)
    print("PATCH status:", r.status_code)
    if r.status_code in (200, 204):
        print(f"Lead {lead_id} muvaffaqiyatli 'Sotuv bo'ldi' (142) statusiga o'tkazildi, narxi: 5,000,000 so'm.")
    else:
        print("Xatolik:", r.text)
        return

    # Add Note
    note_text = (
        "🎉 SOTUV / TO'LOV QAYD ETILDI!\n\n"
        "Mijoz: Aslbek (Asl kids)\n"
        "Xizmat turi: Patentlash\n"
        "To'lov summasi: 5 000 000 so'm\n"
        "Telefon: +998905084338\n"
        "Sana: 2026-10-20\n"
        "Holat: Sotuv bo'ldi (142)"
    )

    note_payload = [{
        "entity_id": lead_id,
        "note_type": "common",
        "params": {
            "text": note_text
        }
    }]
    r_note = requests.post(f"{amo.base_url}/api/v4/leads/{lead_id}/notes", headers=headers, json=note_payload, timeout=15)
    print("Note POST status:", r_note.status_code)

    # Append to sales_ledger.json
    ledger_file = "data/sales_ledger.json"
    ledger = []
    if os.path.exists(ledger_file):
        try:
            with open(ledger_file, "r", encoding="utf-8") as f:
                ledger = json.load(f)
        except Exception:
            ledger = []

    ledger.append({
        "timestamp": datetime.now().isoformat(),
        "lead_id": lead_id,
        "client": "Aslbek",
        "brand": "Asl kids",
        "service": "Patent",
        "phone": "+998905084338",
        "total_amount": 5000000,
        "status": "Sotuv bo'ldi (142)",
        "pipeline": "Sotuv Bo'limi (11162698)"
    })

    with open(ledger_file, "w", encoding="utf-8") as f:
        json.dump(ledger, f, ensure_ascii=False, indent=2)
    print("Moliya yozuvi data/sales_ledger.json ga saqlandi.")

if __name__ == "__main__":
    record_aslkids_sale()
