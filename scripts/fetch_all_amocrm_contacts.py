import requests
import json
import sys
import time

sys.stdout.reconfigure(encoding="utf-8")

with open("data/amocrm_token.json", encoding="utf-8") as f:
    token = json.load(f)["access_token"]

headers = {"Authorization": f"Bearer {token}"}

all_contacts = []
page = 1
limit = 250

print("Fetching all contacts from amoCRM...")
while True:
    url = f"https://jonbranding.amocrm.ru/api/v4/contacts?limit={limit}&page={page}&with=leads"
    r = requests.get(url, headers=headers, timeout=20)
    if r.status_code == 204:
        print(f"Reached end of contacts at page {page} (204 No Content)")
        break
    if r.status_code != 200:
        print(f"Error at page {page}: {r.status_code} {r.text}")
        break

    data = r.json()
    contacts = data.get("_embedded", {}).get("contacts", [])
    if not contacts:
        print(f"No more contacts at page {page}")
        break

    all_contacts.extend(contacts)
    print(f"Page {page:2d}: fetched {len(contacts)} contacts (Total: {len(all_contacts)})")
    
    # Check if next page exists
    links = data.get("_links", {})
    if "next" not in links:
        print("No 'next' link, finished.")
        break

    page += 1
    time.sleep(0.15)

print(f"\nTotal contacts fetched from amoCRM: {len(all_contacts)}")
with open("data/amocrm_all_contacts.json", "w", encoding="utf-8") as f:
    json.dump(all_contacts, f, ensure_ascii=False, indent=2)
print("Saved data/amocrm_all_contacts.json successfully!")
