import os
import requests
from dotenv import dotenv_values

for p in ["/home/ubuntu/oisha-os/.env", "/root/oisha-os/.env", "/home/ubuntu/.env"]:
    if not os.path.exists(p):
        continue
    env = dotenv_values(p)
    tok = env.get("BOT_TOKEN", "").strip()
    if tok:
        try:
            r = requests.get(f"https://api.telegram.org/bot{tok}/getMe", timeout=5)
            print(f"{p} -> status {r.status_code}, username: @{r.json().get('result', {}).get('username')}")
        except Exception as e:
            print(f"{p} -> error {e}")
    else:
        print(f"{p} -> no BOT_TOKEN")
