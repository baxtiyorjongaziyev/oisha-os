import json
import requests

with open('data/utc_session.json', 'r', encoding='utf-8') as f:
    sess = json.load(f)

headers = {
    'Authorization': f'Bearer {sess["token"]}',
    'x-company-id': sess.get('company', 'company_default'),
    'Accept': 'application/json',
    'User-Agent': 'Mozilla/5.0'
}

url = 'https://sales.kontaktmarkazi.com/api/leads?take=5'
r = requests.get(url, headers=headers)
print('Status:', r.status_code)
data = r.json()
print('Success:', data.get('success'))
leads = data.get('data', {}).get('leads', [])
print('Leads count:', len(leads))
total = data.get('data', {}).get('total')
print('Total leads:', total)
