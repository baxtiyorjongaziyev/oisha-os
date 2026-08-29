"""Add Client Success & Retention fields to Airtable Loyihalar table:
1. NPS Baho (1-10)
2. Mijoz Fikri (Review)
3. Onboarding Statusi
4. Keyingi Taklif (Upsell)
5. Upsell Holati
"""
import os
import urllib.request, json, sys

sys.stdout.reconfigure(encoding='utf-8')

API_KEY = os.environ.get("AIRTABLE_API_KEY", "").strip()
if not API_KEY:
    raise RuntimeError("AIRTABLE_API_KEY is required in the runtime secret configuration")
BASE_ID = "app8xoyx1XCumYFXV"
LOYIHALAR_TABLE_ID = "tblJbUobSlygSwYAI"

H = {
    "Authorization": f"Bearer {API_KEY}",
    "Content-Type": "application/json"
}

def api_get(url):
    req = urllib.request.Request(url, headers=H)
    with urllib.request.urlopen(req) as resp:
        return json.loads(resp.read().decode())

def api_post(url, data):
    req = urllib.request.Request(url, data=json.dumps(data).encode('utf-8'), headers=H, method='POST')
    try:
        with urllib.request.urlopen(req) as resp:
            return json.loads(resp.read().decode())
    except urllib.error.HTTPError as he:
        print("API Error:", he.read().decode())
        return None

tables = api_get(f"https://api.airtable.com/v0/meta/bases/{BASE_ID}/tables").get("tables", [])
loy_table = next(t for t in tables if t["id"] == LOYIHALAR_TABLE_ID)
existing_fields = {f["name"] for f in loy_table.get("fields", [])}

new_fields = [
    {
        "name": "NPS Baho (1-10)",
        "type": "number",
        "options": {"precision": 0}
    },
    {
        "name": "Mijoz Fikri (Review)",
        "type": "multilineText"
    },
    {
        "name": "Onboarding Statusi",
        "type": "singleSelect",
        "options": {
            "choices": [
                {"name": "⏳ Kutilmoqda", "color": "yellowLight2"},
                {"name": "✅ Yuborildi", "color": "greenLight2"},
                {"name": "💬 Muloqotda", "color": "blueLight2"}
            ]
        }
    },
    {
        "name": "Keyingi Taklif (Upsell)",
        "type": "singleSelect",
        "options": {
            "choices": [
                {"name": "🎨 Brandbook & Identika", "color": "tealLight2"},
                {"name": "📦 Qadoq & Etiketka dizayni", "color": "cyanLight2"},
                {"name": "🌐 Web-sayt & Landing", "color": "purpleLight2"},
                {"name": "⚖️ Patent va Savdo Belgisi", "color": "orangeLight2"},
                {"name": "🚀 SMM & Kontent dizayn", "color": "pinkLight2"},
                {"name": "— Hozircha yo‘q", "color": "grayLight2"}
            ]
        }
    },
    {
        "name": "Upsell Holati",
        "type": "singleSelect",
        "options": {
            "choices": [
                {"name": "⏳ Rejalashtirilmoqda (7 kun)", "color": "yellowLight2"},
                {"name": "📩 Taklif yuborildi", "color": "blueLight2"},
                {"name": "🎉 Qabul qilindi (Yangi Loyiha)", "color": "greenLight2"},
                {"name": "❌ Rad etildi", "color": "redLight2"}
            ]
        }
    }
]

for field in new_fields:
    fname = field["name"]
    if fname not in existing_fields:
        url = f"https://api.airtable.com/v0/meta/bases/{BASE_ID}/tables/{LOYIHALAR_TABLE_ID}/fields"
        res = api_post(url, field)
        if res:
            print(f"Field '{fname}' created successfully: {res.get('id')}")
    else:
        print(f"Field '{fname}' already exists.")

print("\nClient Success fields setup complete in Loyihalar table!")
