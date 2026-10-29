import json
import sys
import io
import requests

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')

token = json.load(open('data/amocrm_token.json', 'r', encoding='utf-8'))
headers = {'Authorization': f"Bearer {token['access_token']}"}

# In amoCRM API v4 documentation:
# GET /api/v4/leads?filter[tags][0]=363339 or filter[tags]=363339?
# Wait! In amoCRM v4, is filter by tag supported?
# Let's check amoCRM account filters or test with lead ID 52649567

# Let's test if query matches lead name 'shahzod yusupov'
r = requests.get('https://jonbranding.amocrm.ru/api/v4/leads?query=shahzod', headers=headers, timeout=10)
print("query=shahzod status:", r.status_code)
if r.status_code == 200:
    for l in r.json().get('_embedded', {}).get('leads', []):
        print(" ", l['id'], l['name'], [t['name'] for t in l.get('_embedded', {}).get('tags', [])])

# What if query=farangiz in leads?
r_f = requests.get('https://jonbranding.amocrm.ru/api/v4/leads?query=farangiz', headers=headers, timeout=10)
print("query=farangiz status:", r_f.status_code)
# Why did query=farangiz return 204 earlier? Because none of the leads have 'farangiz' in their NAME!
