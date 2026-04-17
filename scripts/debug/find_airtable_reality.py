import requests
import os
import sys
import json
from src.settings import settings

def find_airtable_reality():
    api_key = settings.AIRTABLE_API_KEY.get_secret_value()
    
    headers = {
        "Authorization": f"Bearer {api_key}",
    }
    
    print("🔍 [REALITY CHECK] Finding all Airtable bases...")
    
    # 1. List all bases
    url_bases = "https://api.airtable.com/v0/meta/bases"
    r = requests.get(url_bases, headers=headers)
    
    if r.status_code == 200:
        bases = r.json().get('bases', [])
        print(f"✅ Found {len(bases)} accessible bases:")
        for b in bases:
            print(f"- {b['name']} (ID: {b['id']})")
            
            # 2. For each base, list tables
            url_tables = f"https://api.airtable.com/v0/meta/bases/{b['id']}/tables"
            r_t = requests.get(url_tables, headers=headers)
            if r_t.status_code == 200:
                tables = r_t.json().get('tables', [])
                for t in tables:
                    print(f"  └─ Table: '{t['name']}' (ID: {t['id']})")
                    # Check for project-like fields
                    fields = [f['name'] for f in t['fields']]
                    print(f"     Fields: {fields[:5]}...")
                    if any(k in fields for k in ["Loyiha nomi", "Project Name", "Deadline", "Muddati"]):
                        print(f"     ✨ POTENTIAL PROJECT TABLE: '{t['name']}' in Base '{b['name']}'")
            else:
                print(f"  ❌ Could not list tables for {b['name']} ({r_t.status_code})")
    else:
        print(f"❌ Could not list bases ({r.status_code}): {r.text}")

if __name__ == "__main__":
    find_airtable_reality()
