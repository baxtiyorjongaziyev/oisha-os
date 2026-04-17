
import asyncio
import os
import sys

# Add current directory to path
sys.path.append(os.getcwd())

from src.services.airtable_sync import AirtableSync
from src.settings import settings

async def main():
    at = AirtableSync()
    projects = at.get_projects()
    print(f"Total projects: {len(projects)}")
    for p in projects[:10]:
        fields = p.get('fields', {})
        name = fields.get('Loyihani nomi?') or fields.get('Project Name') or 'Unknown'
        pm = fields.get('PM') or fields.get('Manager') or 'No PM'
        print(f"Project: {name} | PM: {pm}")

if __name__ == "__main__":
    asyncio.run(main())
