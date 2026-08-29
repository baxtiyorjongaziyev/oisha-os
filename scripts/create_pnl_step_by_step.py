"""Create Oylik P&L table step by step in Airtable."""
import json
import os
import urllib.request
import sys

sys.stdout.reconfigure(encoding='utf-8')

API_KEY = os.environ.get("AIRTABLE_API_KEY", "").strip()
if not API_KEY:
    raise RuntimeError("AIRTABLE_API_KEY is required in the runtime secret configuration")
BASE_ID = "app8xoyx1XCumYFXV"

HEADERS = {
    "Authorization": f"Bearer {API_KEY}",
    "Content-Type": "application/json"
}

def create_table():
    url = f"https://api.airtable.com/v0/meta/bases/{BASE_ID}/tables"
    payload = {
        "name": "Oylik P&L",
        "description": "Kompaniyaning oylik Tushumi, Chiqimlari, Yalpi va Haqiqiy Sof Foydasi (Net Profit) hisob-kitob dvigateli.",
        "fields": [
            {
                "name": "Oy nomi",
                "type": "singleLineText"
            },
            {
                "name": "Sana",
                "type": "date",
                "options": {
                    "dateFormat": {"name": "iso"}
                }
            },
            {
                "name": "Jami Kirim (UZS)",
                "type": "number",
                "options": {"precision": 0}
            },
            {
                "name": "Loyiha xarajatlari — COGS (UZS)",
                "type": "number",
                "options": {"precision": 0}
            },
            {
                "name": "Operatsion xarajatlar — OPEX (UZS)",
                "type": "number",
                "options": {"precision": 0}
            }
        ]
    }
    req = urllib.request.Request(
        url,
        data=json.dumps(payload).encode('utf-8'),
        headers=HEADERS
    )
    try:
        with urllib.request.urlopen(req) as resp:
            data = json.loads(resp.read().decode())
            table_id = data.get('id')
            print(f"Created table 'Oylik P&L' with ID: {table_id}")
            return table_id
    except urllib.error.HTTPError as he:
        print("HTTP Error:", he.read().decode())
        return None

def add_field(table_id, field_def):
    url = f"https://api.airtable.com/v0/meta/bases/{BASE_ID}/tables/{table_id}/fields"
    req = urllib.request.Request(
        url,
        data=json.dumps(field_def).encode('utf-8'),
        headers=HEADERS
    )
    try:
        with urllib.request.urlopen(req) as resp:
            print(f"Field '{field_def['name']}' created: HTTP {resp.status}")
    except urllib.error.HTTPError as he:
        print(f"Field '{field_def['name']}' error:", he.read().decode())

def populate_pnl(table_id):
    records = [
        {
            "fields": {
                "Oy nomi": "2026-08 (Avgust 2026)",
                "Sana": "2026-08-01",
                "Jami Kirim (UZS)": 50000000,
                "Loyiha xarajatlari — COGS (UZS)": 6500000,
                "Operatsion xarajatlar — OPEX (UZS)": 22000000
            }
        },
        {
            "fields": {
                "Oy nomi": "2026-07 (Iyul 2026)",
                "Sana": "2026-07-01",
                "Jami Kirim (UZS)": 44000000,
                "Loyiha xarajatlari — COGS (UZS)": 5500000,
                "Operatsion xarajatlar — OPEX (UZS)": 20000000
            }
        },
        {
            "fields": {
                "Oy nomi": "2026-06 (Iyun 2026)",
                "Sana": "2026-06-01",
                "Jami Kirim (UZS)": 38000000,
                "Loyiha xarajatlari — COGS (UZS)": 5000000,
                "Operatsion xarajatlar — OPEX (UZS)": 18500000
            }
        },
        {
            "fields": {
                "Oy nomi": "2026-05 (May 2026)",
                "Sana": "2026-05-01",
                "Jami Kirim (UZS)": 32000000,
                "Loyiha xarajatlari — COGS (UZS)": 4200000,
                "Operatsion xarajatlar — OPEX (UZS)": 17000000
            }
        }
    ]
    url = f"https://api.airtable.com/v0/{BASE_ID}/{table_id}"
    req = urllib.request.Request(
        url,
        data=json.dumps({"records": records}).encode('utf-8'),
        headers=HEADERS
    )
    with urllib.request.urlopen(req) as resp:
        print("Populated P&L data successfully: HTTP", resp.status)

if __name__ == "__main__":
    t_id = create_table()
    if t_id:
        # Add formulas
        add_field(t_id, {
            "name": "Jami Chiqim (UZS)",
            "type": "formula",
            "options": {
                "formula": "{Loyiha xarajatlari — COGS (UZS)} + {Operatsion xarajatlar — OPEX (UZS)}"
            }
        })
        add_field(t_id, {
            "name": "Yalpi Foyda (UZS)",
            "type": "formula",
            "options": {
                "formula": "{Jami Kirim (UZS)} - {Loyiha xarajatlari — COGS (UZS)}"
            }
        })
        add_field(t_id, {
            "name": "HAQIQIY SOF FOYDA (UZS)",
            "type": "formula",
            "options": {
                "formula": "{Jami Kirim (UZS)} - ({Loyiha xarajatlari — COGS (UZS)} + {Operatsion xarajatlar — OPEX (UZS)})"
            }
        })
        add_field(t_id, {
            "name": "SOF FOYDA MARJASI (%)",
            "type": "formula",
            "options": {
                "formula": "IF({Jami Kirim (UZS)} > 0, {HAQIQIY SOF FOYDA (UZS)} / {Jami Kirim (UZS)}, 0)"
            }
        })
        add_field(t_id, {
            "name": "Oylik Moliyaviy Holat",
            "type": "formula",
            "options": {
                "formula": "IF({HAQIQIY SOF FOYDA (UZS)} < 0, '🔴 ZARARDA (Minus)', IF({SOF FOYDA MARJASI (%)} < 0.25, '🟡 Past sof marja (<25%)', '🟢 YUQORI SOF FOYDA (>25%)'))"
            }
        })

        populate_pnl(t_id)
