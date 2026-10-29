import json
import sys
import io
import requests

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')

token = json.load(open('data/amocrm_token.json', 'r', encoding='utf-8'))
headers = {'Authorization': f"Bearer {token['access_token']}"}

# Test different filter params for tags in amoCRM v4
tests = [
    'filter[tags][]=363339',
    'filter[tags]=363339',
    'filter[tags][0]=363339',
    'filter[tags][]=farangiz',
    'filter[tags]=farangiz',
    'filter[tags][0]=farangiz',
    'filter[tag][]=363339',
    'filter[tag]=363339',
    'filter[tag]=farangiz',
    'filter[tag][]=farangiz',
    'filter[custom_fields_values][tags][]=363339',
    'filter[custom_fields_values][tags]=363339'
]

for t in tests:
    r = requests.get(f'https://jonbranding.amocrm.ru/api/v4/leads?{t}&limit=10', headers=headers, timeout=10)
    if r.status_code == 200:
        items = r.json().get('_embedded', {}).get('leads', [])
        # check how many have tag 363339
        has_tag = sum(1 for x in items if any(tag.get('id') == 363339 for tag in x.get('_embedded', {}).get('tags', []) or []))
        print(f"{t} -> HTTP 200, count={len(items)}, has_farangiz={has_tag}")
    elif r.status_code == 204:
        print(f"{t} -> HTTP 204")
    else:
        print(f"{t} -> HTTP {r.status_code}")
