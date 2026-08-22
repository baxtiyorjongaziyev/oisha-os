import requests
import json

url = 'https://oisha.jonbranding.uz/api/internal/mcp/dialogs?limit=10'
headers = {
    'X-Oisha-Internal-Secret': '8f94b1a8d052b66bf130c007137f7a22bf7230b77b7ccb8a',
    'Authorization': 'Bearer 8f94b1a8d052b66bf130c007137f7a22bf7230b77b7ccb8a'
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
