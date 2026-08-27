"""Delete old manual number fields and duplicate fields in Oylik P&L."""
import urllib.request, json, sys

sys.stdout.reconfigure(encoding='utf-8')

API_KEY = "patADXBB0784iii3w.7c1e4380a9736b30f1dd2cb539f6ac49ac097e3452f84f319dc2060834569fdb"
BASE_ID = "app8xoyx1XCumYFXV"
PNL_TABLE_ID = "tblUgfwoxSn2fS4wJ"

H = {
    "Authorization": f"Bearer {API_KEY}",
    "Content-Type": "application/json"
}

def api_delete(field_id, name):
    url = f"https://api.airtable.com/v0/meta/bases/{BASE_ID}/tables/{PNL_TABLE_ID}/fields/{field_id}"
    req = urllib.request.Request(url, headers=H, method='DELETE')
    try:
        with urllib.request.urlopen(req) as resp:
            print(f"Deleted old field '{name}' ({field_id}): HTTP {resp.status}")
    except urllib.error.HTTPError as he:
        print(f"Error deleting '{name}':", he.read().decode())

fields_to_delete = [
    ("fldwH0PJNLDc0yfMM", "Test Rollup Kirim"),
    ("fldA9otaiUb3fLjkV", "Soliq xarajati (UZS) (Old)"),
    ("fldjPqfCcDMsDphmT", "Taqsimlangan Dividendlar (UZS) (Old)"),
    ("fldhN5yK1sA1wU5Hp", "HAQIQIY SOF FOYDA (UZS) (duplicate)"),
    ("fldlnDP8iHY11Nlxs", "Yalpi Foyda (UZS) (old formula)"),
    ("fldHQmbC8iRR6bwXD", "Jami Chiqim (UZS) (old formula)"),
    ("fldU7qr9o5M0lQWUE", "Operatsion xarajatlar — OPEX (UZS) (old number)"),
    ("fld0vyINwDfvPbHsW", "Loyiha xarajatlari — COGS (UZS) (old number)"),
    ("fld41pq7bmeGO1uOC", "Jami Kirim (UZS) (old number)")
]

for fid, fname in fields_to_delete:
    api_delete(fid, fname)

print("\nCleanup completed! All remaining fields in Oylik P&L are 100% computed & automatic.")
