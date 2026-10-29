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

test_lid = 51857755
# Get current tags
r_before = requests.get(f'https://jonbranding.amocrm.ru/api/v4/leads/{test_lid}', headers=headers)
ld_before = r_before.json()
old_tags = [t['name'] for t in ld_before.get('_embedded', {}).get('tags', [])]
print(f"Lead {test_lid} before tags: {old_tags}")

# Replace farangiz with Mumtozmaxal
new_tags = [{'name': 'Mumtozmaxal' if t.lower() == 'farangiz' else t} for t in old_tags]
payload = [
    {
        "id": test_lid,
        "_embedded": {
            "tags": new_tags
        }
    }
]

print(f"Updating lead {test_lid} with new tags: {[t['name'] for t in new_tags]}...")
r_patch = requests.patch('https://jonbranding.amocrm.ru/api/v4/leads', headers=headers, json=payload, timeout=10)
print(f"PATCH status: {r_patch.status_code}")
if r_patch.status_code == 200:
    r_after = requests.get(f'https://jonbranding.amocrm.ru/api/v4/leads/{test_lid}', headers=headers)
    ld_after = r_after.json()
    after_tags = [t['name'] for t in ld_after.get('_embedded', {}).get('tags', [])]
    print(f"Lead {test_lid} after tags: {after_tags}")
else:
    print("PATCH error:", r_patch.text)
