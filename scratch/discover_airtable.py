
import asyncio
import os
import sys
import json

# Add current directory to path
sys.path.append(os.getcwd())

from src.services.airtable_sync import AirtableSync
from src.settings import settings

async def main():
    at = AirtableSync()
    projects = at.get_projects()
    print(f"Total projects: {len(projects)}")
    for p in projects:
        fields = p.get('fields', {})
        pm = fields.get('PM') or fields.get('Manager')
        if pm and isinstance(pm, list):
            print(f"Found PM link: {pm}")
            # Try to see if there is a mapping we can discover
            break
    
    # Try to find other tables
    import requests
    base_url = f"https://api.airtable.com/v0/{at.base_id}"
    tables_to_try = ["Team", "Managers", "Menejerlar", "Xodimlar", "Users"]
    for table in tables_to_try:
        url = f"{base_url}/{table}"
        resp = requests.get(url, headers=at.headers)
        if resp.status_code == 200:
            print(f"SUCCESS: Table '{table}' exists!")
            records = resp.json().get('records', [])
            for r in records[:3]:
                print(f"Record from {table}: {json.dumps(r.get('fields'), indent=2)}")
        else:
            print(f"Table '{table}' not found ({resp.status_code})")

if __name__ == "__main__":
    asyncio.run(main())
