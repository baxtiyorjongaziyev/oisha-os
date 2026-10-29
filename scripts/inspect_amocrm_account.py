import json
import sys
import io
import requests

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')

token = json.load(open('data/amocrm_token.json', 'r', encoding='utf-8'))
headers = {'Authorization': f"Bearer {token['access_token']}"}

# Task types
r = requests.get('https://jonbranding.amocrm.ru/api/v4/account?with=task_types,users', headers=headers, timeout=15)
if r.status_code == 200:
    acc = r.json()
    print("Users:")
    for u in acc.get('_embedded', {}).get('users', []):
        print(f"  User ID={u['id']}: {u['name']} ({u.get('email', '')})")
    print("\nTask Types:")
    for t in acc.get('_embedded', {}).get('task_types', []):
        print(f"  Task Type ID={t['id']}: {t['name']}")
