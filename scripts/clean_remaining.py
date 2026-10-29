import json
import os
import sys
import requests

sys.path.insert(0, ".")
os.environ["AMOCRM_TOKEN_DB_PERSIST"] = "0"
sys.stdout.reconfigure(encoding="utf-8")

from src.services.core.crm.amocrm.sync import AmoCRMSync

def clean_remaining():
    with open("data/mumtoz_farangiz_transfer_audit.json", "r", encoding="utf-8") as f:
        data = json.load(f)

    pairs = data.get("created_leads", [])[20:]
    amo = AmoCRMSync()
    headers = amo._get_headers()

    for p in pairs:
        nid = p["new_lead_id"]
        name = p["name"]
        try:
            r = requests.patch(
                f"{amo.base_url}/api/v4/leads/{nid}",
                headers=headers,
                json={"status_id": 143, "name": f"[Dublikat bekor qilindi] {name}"},
                timeout=10
            )
            print(f"Dubl Lead {nid} status_id=143 ga o'tkazildi: {r.status_code}")
        except Exception as e:
            print(f"Xato {nid}: {e}")

if __name__ == "__main__":
    clean_remaining()
