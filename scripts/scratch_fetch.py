import urllib.request
import json
import os

# Load .env
with open("/home/ubuntu/oisha-os/.env", "r") as f:
    for line in f:
        if line.startswith("OISHA_API_SECRET="):
            os.environ["OISHA_API_SECRET"] = line.strip().split("=", 1)[1]

secret = os.environ.get("OISHA_API_SECRET", "").strip()
headers = {"Authorization": f"Bearer {secret}"}
req = urllib.request.Request("http://127.0.0.1:8080/internal/mcp/analyze_private_chats", headers=headers)

try:
    with urllib.request.urlopen(req, timeout=90) as r:
        res = json.loads(r.read().decode("utf-8"))
        with open("/home/ubuntu/oisha-os/data/private_chats_data.json", "w", encoding="utf-8") as out:
            json.dump(res, out, indent=2, ensure_ascii=False)
        print("SUCCESS_FETCHED_ON_VPS")
except Exception as e:
    if hasattr(e, "read"):
         print("ERROR:", e.code, e.read().decode())
    else:
         print("ERROR:", e)
