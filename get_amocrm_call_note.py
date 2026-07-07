import asyncio
import json
import os
import sys

sys.path.insert(0, '/home/ubuntu/oisha-os')
os.chdir('/home/ubuntu/oisha-os')

from src.api_server import _get_amocrm_instance

async def run():
    amocrm = _get_amocrm_instance()
    
    # Let's search for notes with call type
    headers = amocrm._get_headers()
    import requests
    # Let's query recent contact notes
    # We can get notes from /api/v4/contacts/notes or leads/notes
    url = f"https://{amocrm.subdomain}.amocrm.ru/api/v4/contacts/notes"
    r = requests.get(url, headers=headers, params={"limit": 20})
    print("Status:", r.status_code)
    try:
        notes = r.json()
        print(json.dumps(notes, indent=2))
    except Exception as e:
        print("Error:", e)
        print("Raw response:", r.text[:2000])

asyncio.run(run())
