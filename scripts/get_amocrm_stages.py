import json
import sys
import requests

sys.stdout.reconfigure(encoding='utf-8')

with open("data/amocrm_token.json", encoding="utf-8") as f:
    token = json.load(f)["access_token"]

headers = {"Authorization": f"Bearer {token}"}
r = requests.get("https://jonbranding.amocrm.ru/api/v4/leads/pipelines/11162698", headers=headers, timeout=10)
print(f"Status code: {r.status_code}")

if r.status_code == 200:
    data = r.json()
    print(f"Pipeline Name: {data.get('name')}")
    statuses = data.get("_embedded", {}).get("statuses", [])
    for s in statuses:
        print(f"ID: {s['id']} | Name: {s['name']}")

r_users = requests.get("https://jonbranding.amocrm.ru/api/v4/users", headers=headers, timeout=10)
if r_users.status_code == 200:
    print("\n--- AmoCRM Users / Managers ---")
    users = r_users.json().get("_embedded", {}).get("users", [])
    for u in users:
        print(f"User ID: {u['id']} | Name: {u['name']} | Email: {u.get('email', '')}")

elif r.status_code == 401:
    print("Token expired, need refresh!")
else:
    print(r.text)
