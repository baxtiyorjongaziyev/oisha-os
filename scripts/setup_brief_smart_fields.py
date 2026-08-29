"""Setup smart summary fields on Logo Brief and Naming Brief tables."""
import json
import os
import urllib.request

API_KEY = os.environ.get("AIRTABLE_API_KEY", "").strip()
if not API_KEY:
    raise RuntimeError("AIRTABLE_API_KEY is required in the runtime secret configuration")
BASE_ID = "app8xoyx1XCumYFXV"
LOGO_BRIEF_TABLE = "tblkuQrZxVYUPcQgx"
NAMING_BRIEF_TABLE = "tbl88FVFDVemol9Iz"

HEADERS = {
    "Authorization": f"Bearer {API_KEY}",
    "Content-Type": "application/json"
}

def create_field(table_id, field_def):
    url = f"https://api.airtable.com/v0/meta/bases/{BASE_ID}/tables/{table_id}/fields"
    req = urllib.request.Request(
        url,
        data=json.dumps(field_def).encode('utf-8'),
        headers=HEADERS
    )
    try:
        with urllib.request.urlopen(req) as resp:
            print(f"Table {table_id}: Field '{field_def['name']}' created: HTTP {resp.status}")
    except Exception as e:
        print(f"Table {table_id}: Field '{field_def['name']}' result: {e}")

if __name__ == "__main__":
    # 1. Logo Brief Creative Summary
    create_field(LOGO_BRIEF_TABLE, {
        "name": "Dizayner uchun Qisqa Xulosa (Brief)",
        "type": "formula",
        "options": {
            "formula": "'🎯 BREND: ' & {Brend nomi} & IF({Slogan (agar bo‘lsa)}, ' (' & {Slogan (agar bo‘lsa)} & ')', '') & '\n' & '👥 AUDITORIYA: ' & {Maqsad auditoriya (kimlar uchun?)} & '\n' & '✨ KAYFIYAT: ' & {Logodan qanday his/tuyg‘u chiqishi kerak?} & '\n' & '🎨 RANGLAR: ' & {Afzal ko‘riladigan ranglar}"
        }
    })

    # 2. Naming Brief Summary
    create_field(NAMING_BRIEF_TABLE, {
        "name": "Naming Uchun Qisqa Kriteriyalar",
        "type": "formula",
        "options": {
            "formula": "'🏢 SOHA: ' & {Brend qaysi sohada faoliyat yuritadi?} & '\n' & '👥 AUDITORIYA: ' & {Brendning asosiy auditoriyasi (yosh, jinsi, hududi, daromad darajasi va boshqalar)} & '\n' & '💎 QADRIYATLAR: ' & {3 ta asosiy brend qadriyatingiz}"
        }
    })
