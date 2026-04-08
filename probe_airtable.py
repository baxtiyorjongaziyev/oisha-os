import requests
import os
import sys
import json
from src.settings import settings

def probe_candidate_tables():
    api_key = settings.AIRTABLE_API_KEY.get_secret_value()
    headers = {"Authorization": f"Bearer {api_key}"}
    
    candidates = [
        {"base": "app8xoyx1XCumYFXV", "name": "Jon Branding", "table": "Loyihalar"},
        {"base": "appReuru2WxSLogpG", "name": "Tez Dizayn Scrum", "table": "Tasks"}
    ]
    
    for c in candidates:
        print(f"\nProbing Base: {c['name']} ({c['base']}) -> Table: {c['table']}")
        url = f"https://api.airtable.com/v0/{c['base']}/{c['table']}?maxRecords=3"
        r = requests.get(url, headers=headers)
        if r.status_code == 200:
            recs = r.json().get('records', [])
            print(f"✅ Found {len(recs)} records.")
            if recs:
                print(json.dumps(recs[0]['fields'], indent=2, ensure_ascii=False))
        else:
            print(f"❌ Failed ({r.status_code}): {r.text}")

if __name__ == "__main__":
    probe_candidate_tables()
