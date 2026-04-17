import requests
import os
import sys
import json
from src.settings import settings

def check_airtable_structure():
    api_key = settings.AIRTABLE_API_KEY.get_secret_value()
    base_id = settings.AIRTABLE_BASE_ID
    
    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json"
    }
    
    # Let's try to get ALL tables using metadata API (Requires scope 'schema.bases:read')
    # If this fails, we will try standard table names.
    print(f"🔍 Investigating Base: {base_id}")
    
    url_meta = f"https://api.airtable.com/v0/meta/bases/{base_id}/tables"
    r = requests.get(url_meta, headers=headers)
    
    if r.status_code == 200:
        tables = r.json().get('tables', [])
        print(f"✅ Found {len(tables)} tables!")
        for t in tables:
            print(f"Table: {t['name']} (ID: {t['id']})")
            print(f"Fields: {[f['name'] for f in t['fields']]}")
            print("-" * 20)
    else:
        print(f"❌ Meta API failed ({r.status_code}): {r.text}")
        print("💡 Trying common table names manually...")
        for table in ["Projects", "Tasks", "Loyihalar", "Workflow"]:
            r = requests.get(f"https://api.airtable.com/v0/{base_id}/{table}?maxRecords=1", headers=headers)
            if r.status_code == 200:
                print(f"✅ Found Table: {table}")
                recs = r.json().get('records', [])
                if recs:
                    print(f"Fields: {list(recs[0]['fields'].keys())}")
            else:
                print(f"❌ Table '{table}' not found.")

if __name__ == "__main__":
    check_airtable_structure()
