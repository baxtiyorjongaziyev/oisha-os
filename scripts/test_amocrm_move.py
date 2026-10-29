import json
import sys
import io
import time
import requests

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')

token = json.load(open('data/amocrm_token.json', 'r', encoding='utf-8'))
headers = {
    'Authorization': f"Bearer {token['access_token']}",
    'Content-Type': 'application/json'
}

test_lead_id = 52114147 # Jasur (Card #76)

# 1. Update lead pipeline and status
patch_payload = [
    {
        "id": test_lead_id,
        "pipeline_id": 11162698, # Sotuv Bo'limi
        "status_id": 88871066,   # Kelishuv / Yopish
        "responsible_user_id": 13021974 # Sotuv bo'limi
    }
]

print(f"Testing PATCH lead {test_lead_id}...", flush=True)
r_patch = requests.patch('https://jonbranding.amocrm.ru/api/v4/leads', headers=headers, json=patch_payload, timeout=15)
print(f"PATCH status: {r_patch.status_code}", flush=True)
if r_patch.status_code == 200:
    print("PATCH success:", r_patch.json())
else:
    print("PATCH error:", r_patch.text)

# 2. Create task
# Deadline: today 18:00 Tashkent time (UTC+5)
# Tashkent is UTC+5. 2026-10-19 18:00:00 UTC+5 = 1792414800 unix timestamp approx
# Or dynamically: int(time.time()) + 4 * 3600
complete_till = int(time.time()) + 4 * 3600

task_payload = [
    {
        "entity_id": test_lead_id,
        "entity_type": "leads",
        "text": "🔥 SHOSHILINCH YOPISH: Mijoz sotuvga tayyor ('Sell' statusi). Zudlik bilan bog'lanib, shartnoma yoki to'lovni rasmiylashtiring!",
        "complete_till": complete_till,
        "task_type_id": 1,
        "responsible_user_id": 13021974
    }
]

print(f"Testing POST task for lead {test_lead_id}...", flush=True)
r_task = requests.post('https://jonbranding.amocrm.ru/api/v4/tasks', headers=headers, json=task_payload, timeout=15)
print(f"POST task status: {r_task.status_code}", flush=True)
if r_task.status_code == 200:
    print("POST task success:", r_task.json())
else:
    print("POST task error:", r_task.text)
