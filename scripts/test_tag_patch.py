import json
import sys
import io
import requests

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')

token = json.load(open('data/amocrm_token.json', 'r', encoding='utf-8'))
headers = {
    'Authorization': f"Bearer {token['access_token']}",
    'Content-Type': 'application/json'
}

# Test PATCH /api/v4/leads/tags
payload = [
    {
        "id": 363339,
        "name": "Mumtozmaxal"
    }
]

print("Testing PATCH /api/v4/leads/tags...", flush=True)
r = requests.patch('https://jonbranding.amocrm.ru/api/v4/leads/tags', headers=headers, json=payload, timeout=10)
print("Status:", r.status_code)
print("Response:", r.text)

# Also test contacts tags
payload_cnt = [
    {
        "id": 365737,
        "name": "Mumtozmaxal"
    }
]
print("\nTesting PATCH /api/v4/contacts/tags...", flush=True)
r_cnt = requests.patch('https://jonbranding.amocrm.ru/api/v4/contacts/tags', headers=headers, json=payload_cnt, timeout=10)
print("Status:", r_cnt.status_code)
print("Response:", r_cnt.text)
