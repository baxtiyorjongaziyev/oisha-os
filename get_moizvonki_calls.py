import json
import os
import requests
import time

API_KEY = os.environ.get("MOIZVONKI_API_KEY", "")
emails = ["jonbranding@agency.uz"]

for email in emails:
    payload = {
        "user_name": "jonbranding@agency.uz",
        "api_key": API_KEY,
        "action": "calls.list",
        "from_date": int(time.time()) - 7 * 24 * 3600, # last 7 days
        "max_results": 20
    }
    
    url = "https://jonbrandingagency.moizvonki.ru/api/v1"
    r = requests.post(url, json=payload)
    data = r.json()
    calls = data.get("results", [])
    recordings = [{"db_call_id": c.get("db_call_id"), "recording": c.get("recording"), "duration": c.get("duration")} for c in calls if c.get("recording")]
    print(json.dumps(recordings, indent=2))

