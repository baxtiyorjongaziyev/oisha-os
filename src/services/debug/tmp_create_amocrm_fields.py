import requests
import json
import os
import sys

project_dir = r"c:\Users\baxti\.gemini\antigravity\playground\oisha-os"
sys.path.append(project_dir)
import settings

def create_custom_fields():
    token_file = os.path.join(project_dir, "amocrm_token.json")
    with open(token_file, "r") as f:
        token_data = json.load(f)
    
    access_token = token_data.get("access_token")
    subdomain = settings.settings.AMOCRM_SUBDOMAIN
    
    url = f"https://{subdomain}.amocrm.ru/api/v4/leads/custom_fields"
    headers = {
        "Authorization": f"Bearer {access_token}",
        "Content-Type": "application/json"
    }
    
    # Fields to create
    fields = [
        {
            "name": "Mijozning ehtiyoji (AI)",
            "type": "textarea"
        },
        {
            "name": "Budjet diapazoni (AI)",
            "type": "select",
            "enums": [
                {"value": "< 500$", "sort": 1},
                {"value": "500$ - 1500$", "sort": 2},
                {"value": "1500$ - 3000$", "sort": 3},
                {"value": "> 3000$", "sort": 4}
            ]
        }
    ]
    
    response = requests.post(url, headers=headers, json=fields)
    if response.status_code in [200, 201]:
        print("Successfully created custom fields:")
        print(json.dumps(response.json(), indent=2, ensure_ascii=False))
    else:
        print(f"Error {response.status_code}: {response.text}")

if __name__ == "__main__":
    create_custom_fields()
