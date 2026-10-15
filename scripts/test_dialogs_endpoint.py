import os
import requests
import json

url = 'https://oisha.jonbranding.uz/api/internal/mcp/dialogs?limit=10'
headers = {
    'X-Oisha-Internal-Secret': os.environ['OISHA_API_SECRET'],
    'Authorization': f"Bearer {os.environ['OISHA_API_SECRET']}"
}
try:
    r = requests.get(url, headers=headers, timeout=10)
    print(f'Status: {r.status_code}')
    if r.status_code == 200:
        dialogs = r.json().get('dialogs', [])
        for d in dialogs[:8]:
            print(f" - {d.get('name') or d.get('title')} (ID: {d.get('id')})")
    else:
        print(r.text[:200])
except Exception as e:
    print(f'Error: {e}')
