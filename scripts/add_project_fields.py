"""Add smart project intelligence fields to Loyihalar table in Airtable."""
import json
import urllib.request

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
    # 1. Deadline Holati
    create_field({
        "name": "Deadline Holati",
        "type": "formula",
        "options": {
            "formula": "IF({Loyiha bosqichi} = 'Yakunlangan', '✅ Topshirilgan', IF({END sana} = BLANK(), '⚪️ Sanasiz', IF(DATETIME_DIFF({END sana}, TODAY(), 'days') < 0, '🔴 Kechikdi (' & ABS(DATETIME_DIFF({END sana}, TODAY(), 'days')) & ' kun)', IF(DATETIME_DIFF({END sana}, TODAY(), 'days') <= 3, '🟡 Shoshilinch (' & DATETIME_DIFF({END sana}, TODAY(), 'days') & ' kun qoldi)', '🟢 Rejada (' & DATETIME_DIFF({END sana}, TODAY(), 'days') & ' kun bor)'))))"
        }
    })

    # 2. Loyiha Davomiyligi
    create_field({
        "name": "Loyiha Davomiyligi",
        "type": "formula",
        "options": {
            "formula": "IF(AND({Start sana}, {END sana}), DATETIME_DIFF({END sana}, {Start sana}, 'days') & ' kun', '')"
        }
    })
