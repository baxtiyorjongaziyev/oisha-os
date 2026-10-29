import json
import sys
import io
import requests

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')

token = json.load(open('data/amocrm_token.json', 'r', encoding='utf-8'))
headers = {'Authorization': f"Bearer {token['access_token']}"}

# 1. Fetch all leads with query 'farangiz'
all_farangiz_leads = []
page = 1
while True:
    r = requests.get(f'https://jonbranding.amocrm.ru/api/v4/leads?query=farangiz&limit=250&page={page}', headers=headers, timeout=15)
    if r.status_code == 200:
        lds = r.json().get('_embedded', {}).get('leads', [])
        all_farangiz_leads.extend(lds)
        print(f"Leads page {page}: got {len(lds)} leads", flush=True)
        if len(lds) < 250:
            break
        page += 1
    elif r.status_code == 204:
        break
    else:
        print(f"Leads page {page} error: {r.status_code}", flush=True)
        break

print(f"Total leads returned by query=farangiz: {len(all_farangiz_leads)}")

# Filter those that actually have 'farangiz' tag
leads_with_tag = []
leads_with_text_only = []

for l in all_farangiz_leads:
    tags = [t.get('name') for t in l.get('_embedded', {}).get('tags', []) or []]
    has_tag = any(t and t.lower() == 'farangiz' for t in tags)
    if has_tag:
        leads_with_tag.append(l)
    else:
        leads_with_text_only.append(l)

print(f"Leads that ACTUALLY have 'farangiz' tag: {len(leads_with_tag)}")
print(f"Leads with text only: {len(leads_with_text_only)}")

# 2. Fetch all contacts with query 'farangiz'
all_farangiz_contacts = []
page = 1
while True:
    r = requests.get(f'https://jonbranding.amocrm.ru/api/v4/contacts?query=farangiz&limit=250&page={page}', headers=headers, timeout=15)
    if r.status_code == 200:
        cnts = r.json().get('_embedded', {}).get('contacts', [])
        all_farangiz_contacts.extend(cnts)
        print(f"Contacts page {page}: got {len(cnts)} contacts", flush=True)
        if len(cnts) < 250:
            break
        page += 1
    elif r.status_code == 204:
        break
    else:
        print(f"Contacts page {page} error: {r.status_code}", flush=True)
        break

contacts_with_tag = []
for c in all_farangiz_contacts:
    tags = [t.get('name') for t in c.get('_embedded', {}).get('tags', []) or []]
    if any(t and t.lower() == 'farangiz' for t in tags):
        contacts_with_tag.append(c)

print(f"\nTotal contacts returned by query=farangiz: {len(all_farangiz_contacts)}")
print(f"Contacts that ACTUALLY have 'farangiz' tag: {len(contacts_with_tag)}")

# 3. Fetch companies with query 'farangiz'
all_farangiz_companies = []
r_comp = requests.get('https://jonbranding.amocrm.ru/api/v4/companies?query=farangiz&limit=250', headers=headers, timeout=15)
if r_comp.status_code == 200:
    all_farangiz_companies = r_comp.json().get('_embedded', {}).get('companies', [])

companies_with_tag = []
for c in all_farangiz_companies:
    tags = [t.get('name') for t in c.get('_embedded', {}).get('tags', []) or []]
    if any(t and t.lower() == 'farangiz' for t in tags):
        companies_with_tag.append(c)

print(f"\nTotal companies returned by query=farangiz: {len(all_farangiz_companies)}")
print(f"Companies that ACTUALLY have 'farangiz' tag: {len(companies_with_tag)}")

with open('data/farangiz_entities_to_update.json', 'w', encoding='utf-8') as f_out:
    json.dump({
        'leads': [{'id': l['id'], 'name': l['name'], 'tags': [t['name'] for t in l.get('_embedded', {}).get('tags', [])]} for l in leads_with_tag],
        'contacts': [{'id': c['id'], 'name': c['name'], 'tags': [t['name'] for t in c.get('_embedded', {}).get('tags', [])]} for c in contacts_with_tag],
        'companies': [{'id': c['id'], 'name': c['name'], 'tags': [t['name'] for t in c.get('_embedded', {}).get('tags', [])]} for c in companies_with_tag]
    }, f_out, ensure_ascii=False, indent=2)

print("\nSummary saved to data/farangiz_entities_to_update.json")
