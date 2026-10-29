import json
import sys
import io

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')

contacts = json.load(open('data/amocrm_all_contacts.json', 'r', encoding='utf-8'))
print(f"Total contacts in local cache: {len(contacts)}")

farangiz_contacts = []
for c in contacts:
    tags = [t['name'] for t in c.get('_embedded', {}).get('tags', []) or []]
    for t in tags:
        if 'farangiz' in t.lower():
            farangiz_contacts.append({
                'id': c['id'],
                'name': c['name'],
                'tags': tags
            })
            break

print(f"Found {len(farangiz_contacts)} contacts with 'farangiz' tag in amocrm_all_contacts.json:")
for fc in farangiz_contacts:
    print(f"  ID {fc['id']}: {fc['name']} - Tags: {fc['tags']}")
