import asyncio
import json
import os
import sys

sys.path.insert(0, '/home/ubuntu/oisha-os')
os.chdir('/home/ubuntu/oisha-os')

from src.api_server import _get_amocrm_instance

async def run():
    amocrm = _get_amocrm_instance()
    
    # Let's get users list
    headers = amocrm._get_headers()
    import requests
    url = f"https://{amocrm.subdomain}.amocrm.ru/api/v4/users"
    r = requests.get(url, headers=headers)
    print("Status:", r.status_code)
    try:
        users = r.json()
        print(json.dumps(users, indent=2))
    except Exception as e:
        print("Error:", e)
        print("Raw response:", r.text)

asyncio.run(run())
