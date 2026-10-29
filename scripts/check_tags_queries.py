import json
import sys
import io
import requests

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')

token = json.load(open('data/amocrm_token.json', 'r', encoding='utf-8'))
headers = {'Authorization': f"Bearer {token['access_token']}"}

for entity in ['leads', 'contacts', 'companies']:
    for q in ['farangiz', 'mumtoz', 'mumtozmaxal']:
        r = requests.get(f'https://jonbranding.amocrm.ru/api/v4/{entity}/tags?query={q}', headers=headers, timeout=10)
        if r.status_code == 200:
            data = r.json()
            tags = data.get('_embedded', {}).get('tags', [])
            print(f"{entity} tags (query='{q}'): Found {len(tags)}")
            for t in tags:
                print(f"  Tag ID {t.get('id')}: '{t.get('name')}'")
        elif r.status_code == 204:
            print(f"{entity} tags (query='{q}'): 204 No Content")
        else:
            print(f"{entity} tags (query='{q}'): HTTP {r.status_code}")
