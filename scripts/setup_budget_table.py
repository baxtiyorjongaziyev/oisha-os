"""Setup and populate Oylik budjet table in Airtable."""
import json
import urllib.request
import urllib.parse

API_KEY = "patADXBB0784iii3w.7c1e4380a9736b30f1dd2cb539f6ac49ac097e3452f84f319dc2060834569fdb"
BASE_ID = "app8xoyx1XCumYFXV"
BUDGET_TABLE_ID = "tblSm2Jx5mTE4tEQ7"
CATEGORIES_TABLE_ID = "tblRt6aiU6Vy2yLCD"

HEADERS = {
    "Authorization": f"Bearer {API_KEY}",
    "Content-Type": "application/json"
}

def create_field(field_def):
    url = f"https://api.airtable.com/v0/meta/bases/{BASE_ID}/tables/{BUDGET_TABLE_ID}/fields"
    req = urllib.request.Request(url, data=json.dumps(field_def).encode('utf-8'), headers=HEADERS)
    try:
        with urllib.request.urlopen(req) as resp:
            print(f"Field {field_def['name']} created: {resp.status}")
    except Exception as e:
        print(f"Field {field_def['name']} info: {e}")

def get_categories():
    url = f"https://api.airtable.com/v0/{BASE_ID}/{CATEGORIES_TABLE_ID}"
    req = urllib.request.Request(url, headers=HEADERS)
    with urllib.request.urlopen(req) as resp:
        data = json.loads(resp.read().decode())
        return {r["fields"].get("Kategoriya"): r["id"] for r in data.get("records", [])}

def populate_sample_budget():
    cats = get_categories()
    print("Fetched categories:", list(cats.keys()))

    # Sample standard budget for 2026-08 (Avgust 2026)
    month_date = "2026-08-01"
    records_to_create = [
        # Daromadlar
        {
            "Budjet nomi": "Avgust 2026 — Branding loyihalari",
            "Oy": month_date,
            "Turi": "Daromad",
            "Kategoriya": [cats["Branding loyiha daromadi"]] if "Branding loyiha daromadi" in cats else [],
            "Reja (UZS)": 45000000,
            "Fakt (UZS)": 38000000,
            "Izoh": "Oyiga 6-8 ta vizual identifikatsiya va brending loyihasi"
        },
        {
            "Budjet nomi": "Avgust 2026 — Naming loyihalari",
            "Oy": month_date,
            "Turi": "Daromad",
            "Kategoriya": [cats["Naming loyiha daromadi"]] if "Naming loyiha daromadi" in cats else [],
            "Reja (UZS)": 15000000,
            "Fakt (UZS)": 12000000,
            "Izoh": "Oyiga 2-3 ta naming loyihasi"
        },
        # Xarajatlar
        {
            "Budjet nomi": "Avgust 2026 — Ofis va ijara",
            "Oy": month_date,
            "Turi": "Xarajat",
            "Kategoriya": [cats["Ofis va ijara"]] if "Ofis va ijara" in cats else [],
            "Reja (UZS)": 8000000,
            "Fakt (UZS)": 8000000,
            "Izoh": "Ofis oylik ijarasi va xizmatlari"
        },
        {
            "Budjet nomi": "Avgust 2026 — Jamoa maoshi va okladlar",
            "Oy": month_date,
            "Turi": "Xarajat",
            "Kategoriya": [cats["Ish haqi — oklad"]] if "Ish haqi — oklad" in cats else (
                [cats["Ish haqi – oklad"]] if "Ish haqi – oklad" in cats else []
            ),
            "Reja (UZS)": 20000000,
            "Fakt (UZS)": 18500000,
            "Izoh": "Asosiy doimiy jamoa okladlari"
        },
        {
            "Budjet nomi": "Avgust 2026 — Freelancer va autsorsing",
            "Oy": month_date,
            "Turi": "Xarajat",
            "Kategoriya": [cats["Freelancer va ishlab chiqarish"]] if "Freelancer va ishlab chiqarish" in cats else [],
            "Reja (UZS)": 6000000,
            "Fakt (UZS)": 4500000,
            "Izoh": "3D, motion va illyustratsiya freelancelari"
        },
        {
            "Budjet nomi": "Avgust 2026 — Marketing va reklama (Target)",
            "Oy": month_date,
            "Turi": "Xarajat",
            "Kategoriya": [cats["Marketing va reklama"]] if "Marketing va reklama" in cats else [],
            "Reja (UZS)": 7000000,
            "Fakt (UZS)": 6200000,
            "Izoh": "Meta Ads va kontekst reklama budjeti"
        },
        {
            "Budjet nomi": "Avgust 2026 — Dasturiy ta’minot va AI",
            "Oy": month_date,
            "Turi": "Xarajat",
            "Kategoriya": [cats["Dasturiy ta’minot"]] if "Dasturiy ta’minot" in cats else (
                [cats["Dasturiy ta\u2019minot"]] if "Dasturiy ta\u2019minot" in cats else []
            ),
            "Reja (UZS)": 2500000,
            "Fakt (UZS)": 2100000,
            "Izoh": "Figma, Adobe CC, OpenAI, Airtable, Midjourney"
        },
        {
            "Budjet nomi": "Avgust 2026 — Transport va kuryer",
            "Oy": month_date,
            "Turi": "Xarajat",
            "Kategoriya": [cats["Transport va xizmat safari"]] if "Transport va xizmat safari" in cats else [],
            "Reja (UZS)": 1500000,
            "Fakt (UZS)": 1100000,
            "Izoh": "Uchrashuvlar va yetkazib berish xarajatlari"
        }
    ]

    # Post records in batches of 10
    url = f"https://api.airtable.com/v0/{BASE_ID}/{BUDGET_TABLE_ID}"
    batch = [{"fields": r} for r in records_to_create]
    req = urllib.request.Request(url, data=json.dumps({"records": batch}).encode('utf-8'), headers=HEADERS)
    with urllib.request.urlopen(req) as resp:
        print("Created Budget records successfully: HTTP", resp.status)

if __name__ == "__main__":
    # Create fields
    create_field({
        "name": "Turi",
        "type": "singleSelect",
        "options": {
            "choices": [
                {"name": "Daromad", "color": "greenLight2"},
                {"name": "Xarajat", "color": "redLight2"}
            ]
        }
    })
    create_field({
        "name": "Farq (UZS)",
        "type": "formula",
        "options": {
            "formula": "IF({Turi} = 'Daromad', {Fakt (UZS)} - {Reja (UZS)}, {Reja (UZS)} - {Fakt (UZS)})"
        }
    })
    create_field({
        "name": "Ijro foizi (%)",
        "type": "formula",
        "options": {
            "formula": "IF({Reja (UZS)} > 0, {Fakt (UZS)} / {Reja (UZS)}, 0)"
        }
    })
    create_field({
        "name": "Budjet holati",
        "type": "formula",
        "options": {
            "formula": "IF({Turi} = 'Daromad', IF({Fakt (UZS)} >= {Reja (UZS)}, '🟢 Reja bajarildi', IF({Ijro foizi (%)} >= 0.7, '🟡 Rejaga yaqin', '🔴 Rejadan orqada')), IF({Fakt (UZS)} > {Reja (UZS)}, '🔴 Limitdan oshdi', IF({Ijro foizi (%)} >= 0.85, '🟡 Limitga yaqin', '🟢 Normada')))"
        }
    })

    # Populate
    populate_sample_budget()
