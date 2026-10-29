import json
import os
import sys
import requests
from datetime import datetime

sys.path.insert(0, ".")
os.environ["AMOCRM_TOKEN_DB_PERSIST"] = "0"
sys.stdout.reconfigure(encoding="utf-8")

from src.services.core.crm.amocrm.sync import AmoCRMSync

def record_sale():
    amo = AmoCRMSync()
    headers = amo._get_headers()

    lead_id = 52282551
    # 1. Update lead in amoCRM: pipeline_id=11162698, status_id=142, price=6320000
    payload = {
        "name": "Inomjon aka (Sokin Jalyuzi)",
        "pipeline_id": 11162698,
        "status_id": 142, # Sotuv bo'ldi
        "price": 6320000,
        "_embedded": {
            "tags": [
                {"name": "Mijoz"},
                {"name": "Sotuv"},
                {"name": "Naqd"},
                {"name": "Ofisga keldi"},
                {"name": "Target"}
            ]
        }
    }

    print(f"Lead ID {lead_id} yangilanmoqda...")
    r = requests.patch(f"{amo.base_url}/api/v4/leads/{lead_id}", headers=headers, json=payload, timeout=20)
    print("PATCH status:", r.status_code)
    if r.status_code in (200, 204):
        print(f"Lead {lead_id} muvaffaqiyatli 'Sotuv bo'ldi' (142) statusiga o'tkazildi, narxi: 6,320,000 so'm.")
    else:
        print("Xatolik:", r.text)
        return

    # 2. Add detailed Note
    note_text = (
        "🎉 SOTUV / KIRIM QAYD ETILDI!\n\n"
        "To'lov turi: #kirim naqd\n"
        "Sana: 2026-10-20 16:19\n"
        "Mijoz: Inomjon aka\n"
        "Brend: Sokin Jalyuzi\n"
        "Telefon: +998884567787 (qo'shimcha: +998337555587)\n\n"
        "To'lov taqsimoti:\n"
        "• Expert tekshiruv: 1 320 000 so'm\n"
        "• Agentlik xizmati: 5 000 000 so'm\n"
        "JAMI: 6 320 000 so'm\n\n"
        "Ofisga shaxsan kelib naqd to'lov amalga oshirildi."
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

    # 3. Log to data/sales_ledger.json
    ledger_file = "data/sales_ledger.json"
    ledger = []
    if os.path.exists(ledger_file):
        try:
            with open(ledger_file, "r", encoding="utf-8") as f:
                ledger = json.load(f)
        except Exception:
            ledger = []

    ledger.append({
        "timestamp": "2026-10-20T16:19:00",
        "lead_id": lead_id,
        "client": "Inomjon aka",
        "brand": "Sokin Jalyuzi",
        "phone": "+998884567787",
        "payment_type": "Naqd",
        "expert_check": 1320000,
        "agency_service": 5000000,
        "total_amount": 6320000,
        "status": "Sotuv bo'ldi (142)",
        "pipeline": "Sotuv Bo'limi (11162698)"
    })

    with open(ledger_file, "w", encoding="utf-8") as f:
        json.dump(ledger, f, ensure_ascii=False, indent=2)
    print("Moliya yozuvi data/sales_ledger.json ga muhrlandi.")

if __name__ == "__main__":
    record_sale()
