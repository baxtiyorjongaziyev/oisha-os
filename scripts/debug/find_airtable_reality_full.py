import requests
import os
import sys
import json
from src.settings import settings

def find_airtable_reality_full():
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
        print(f"✅ Found {len(bases)} accessible bases.")
        for b in bases:
            base_id = b['id']
            base_name = b['name']
            print(f"\n--- BASE: {base_name} ({base_id}) ---")
            
            # 2. For each base, list tables
            url_tables = f"https://api.airtable.com/v0/meta/bases/{base_id}/tables"
            r_t = requests.get(url_tables, headers=headers)
            if r_t.status_code == 200:
                tables = r_t.json().get('tables', [])
                for t in tables:
                    table_name = t['name']
                    print(f"  └─ Table: '{table_name}'")
                    # Try to fetch 1 record to see actual field values
                    url_rec = f"https://api.airtable.com/v0/{base_id}/{table_name}?maxRecords=1"
                    r_rec = requests.get(url_rec, headers=headers)
                    if r_rec.status_code == 200:
                        recs = r_rec.json().get('records', [])
                        if recs:
                            print(f"     Real Fields: {list(recs[0]['fields'].keys())}")
                            # Check for any field that looks like a project name
                            fields = recs[0]['fields']
                            for k, v in fields.items():
                                if isinstance(v, str) and len(v) > 2:
                                    print(f"     Sample Value for '{k}': {v[:30]}...")
            else:
                print(f"  ❌ Could not list tables ({r_t.status_code})")
    else:
        print(f"❌ Could not list bases ({r.status_code}): {r.text}")

if __name__ == "__main__":
    find_airtable_reality_full()
