import requests
import os
import sys
import json
from datetime import datetime

# Path setup to import from src
sys.path.append(os.getcwd())

from src.settings import settings

def inspect():
    print("🔍 [INSPECT] Starting Airtable Investigation...")
    
    api_key = settings.AIRTABLE_API_KEY.get_secret_value()
    base_id = settings.AIRTABLE_BASE_ID
    
    # Common table names to try
    tables = ["Projects", "Tasks", "Loyihalar", "Workflow", "Kanban", "Portfolio"]
    
    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json"
    }
    
    for table in tables:
        url = f"https://api.airtable.com/v0/{base_id}/{table}?maxRecords=3"
        print(f"Trying table: '{table}'...")
        r = requests.get(url, headers=headers)
        
        if r.status_code == 200:
            data = r.json()
            records = data.get("records", [])
            print(f"✅ Table '{table}' FOUND! Records found: {len(records)}")
            if records:
                print(f"Sample Record Fields: {json.dumps(records[0].get('fields', {}), indent=2, ensure_ascii=False)}")
                # Break if we found the main projects table (usually has 'Project Name' or 'Loyiha' or 'Deadline')
                fields = records[0].get('fields', {})
                if any(k in fields for k in ["Project Name", "Loyiha nomi", "Deadline", "Status", "Stage"]):
                    print(f"✨ IDENTIFIED: '{table}' seems to be the main Project table.")
        else:
            print(f"❌ Table '{table}' not found or error ({r.status_code}).")

if __name__ == "__main__":
    inspect()
