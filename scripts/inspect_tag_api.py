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

# Check Tag details
# Leads tag: 363339
# Contacts/Companies tag: 365737

for entity, tag_id in [('leads', 363339), ('contacts', 365737)]:
    print(f"\n--- Checking {entity} tag {tag_id} ---", flush=True)
    r = requests.get(f'https://jonbranding.amocrm.ru/api/v4/{entity}/tags/{tag_id}', headers=headers)
    print(f"GET /{entity}/tags/{tag_id}: status {r.status_code}", flush=True)
    if r.status_code == 200:
        print("Details:", r.json())

# Check how filter by tag works in v4
# Let's test with filter[tag]=farangiz or filter[tags]=farangiz or filter[tags][0]=363339
for entity, tag_id in [('leads', 363339), ('contacts', 365737)]:
    print(f"\nTesting filter for {entity}...", flush=True)
    for q in [f'filter[tags][0]={tag_id}', f'filter[tags]={tag_id}', 'filter[tag]=farangiz', 'filter[tags]=farangiz', f'filter[tags][0]=farangiz']:
        r = requests.get(f'https://jonbranding.amocrm.ru/api/v4/{entity}?{q}', headers=headers, timeout=10)
        if r.status_code == 200:
            items = r.json().get('_embedded', {}).get(entity, [])
            # check if items actually have the tag
            matching = [x for x in items if any(t.get('name', '').lower() == 'farangiz' or t.get('id') == tag_id for t in x.get('_embedded', {}).get('tags', []) or [])]
            print(f"  {q}: HTTP 200, Total {len(items)} items, Matching tags: {len(matching)}")
            for m in matching:
                print(f"    -> ID {m['id']}: {m.get('name')}")
        elif r.status_code == 204:
            print(f"  {q}: HTTP 204 (Empty)")
        else:
            print(f"  {q}: HTTP {r.status_code}")
