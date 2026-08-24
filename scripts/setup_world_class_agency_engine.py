"""Setup World-Class Agency Engine in Airtable Loyihalar table.
Adds Scope/Revision Control and True Internal Costing & Effective Hourly Profitability.
"""
import json
import urllib.request
import sys

sys.stdout.reconfigure(encoding='utf-8')

API_KEY = "patADXBB0784iii3w.7c1e4380a9736b30f1dd2cb539f6ac49ac097e3452f84f319dc2060834569fdb"
BASE_ID = "app8xoyx1XCumYFXV"
TABLE_ID = "tblJbUobSlygSwYAI"
FIELDS_URL = f"https://api.airtable.com/v0/meta/bases/{BASE_ID}/tables/{TABLE_ID}/fields"

HEADERS = {
    "Authorization": f"Bearer {API_KEY}",
    "Content-Type": "application/json"
}

def create_field(field_def):
    req = urllib.request.Request(
        FIELDS_URL,
        data=json.dumps(field_def).encode('utf-8'),
        headers=HEADERS
    )
    try:
        with urllib.request.urlopen(req) as resp:
            print(f"Field '{field_def['name']}' created: HTTP {resp.status}")
    except Exception as e:
        print(f"Field '{field_def['name']}' result: {e}")

if __name__ == "__main__":
    print("=== 1. SCOPE & REVISION CONTROL (Pravkalar Chegarasi) ===")
    create_field({
        "name": "Pravkalar soni",
        "type": "number",
        "options": {"precision": 0}
    })
    create_field({
        "name": "Maksimal bepul pravka",
        "type": "number",
        "options": {"precision": 0}
    })
    create_field({
        "name": "Pravka holati",
        "type": "formula",
        "options": {
            "formula": "IF({Pravkalar soni} > {Maksimal bepul pravka}, '🔴 Pullik pravka (' & ({Pravkalar soni} - {Maksimal bepul pravka}) & ' ta ortiqcha)', IF({Pravkalar soni} = {Maksimal bepul pravka}, '🟡 Bepul limit tugadi (Keyingisi pullik)', '🟢 Bepul limitda (' & IF({Maksimal bepul pravka}, ({Maksimal bepul pravka} - {Pravkalar soni}), 2) & ' ta qoldi)'))"
        }
    })
    create_field({
        "name": "Qo‘shimcha pravka to‘lovi (UZS)",
        "type": "formula",
        "options": {
            "formula": "IF({Pravkalar soni} > {Maksimal bepul pravka}, ({Pravkalar soni} - {Maksimal bepul pravka}) * 500000, 0)"
        }
    })

    print("\n=== 2. TRUE INTERNAL COSTING & PROFITABILITY (Haqiqiy Tan Narx va Foydalilik) ===")
    create_field({
        "name": "Dizayner soatlari",
        "type": "number",
        "options": {"precision": 1}
    })
    create_field({
        "name": "PM va Muloqot soatlari",
        "type": "number",
        "options": {"precision": 1}
    })
    create_field({
        "name": "Jami sarflangan vaqt (Soat)",
        "type": "formula",
        "options": {
            "formula": "{Dizayner soatlari} + {PM va Muloqot soatlari}"
        }
    })
    create_field({
        "name": "Haqiqiy ichki tan narx (UZS)",
        "type": "formula",
        "options": {
            "formula": "({Jami sarflangan vaqt (Soat)} * 75000)"
        }
    })
    create_field({
        "name": "Haqiqiy Sof Foyda (UZS)",
        "type": "formula",
        "options": {
            "formula": "{Jami loyiha narxi (UZS)} - {Haqiqiy ichki tan narx (UZS)}"
        }
    })
    create_field({
        "name": "Haqiqiy Rentabellik (%)",
        "type": "formula",
        "options": {
            "formula": "IF({Jami loyiha narxi (UZS)} > 0, {Haqiqiy Sof Foyda (UZS)} / {Jami loyiha narxi (UZS)}, 0)"
        }
    })
    create_field({
        "name": "Loyiha Rentabellik Holati",
        "type": "formula",
        "options": {
            "formula": "IF({Haqiqiy Sof Foyda (UZS)} < 0, '🔴 ZARARDA (Minus)', IF({Haqiqiy Rentabellik (%)} < 0.4, '🟡 Past rentabellik (<40%)', '🟢 Yuqori foyda (>50%)'))"
        }
    })
    print("\n=== All World-Class Agency Fields Configured! ===")
