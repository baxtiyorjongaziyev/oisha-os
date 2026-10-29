import os
import dotenv
import requests

for env_path in ['/home/ubuntu/oisha-os/.env', '/root/oisha-os/.env']:
    if not os.path.exists(env_path):
        continue
    print(f"--- Checking {env_path} ---")
    env = dotenv.dotenv_values(env_path)
    for k, v in env.items():
        if not v:
            continue
        # Check Telegram bot tokens
        if ':' in v and len(v) > 25 and not v.startswith('http'):
            try:
                r = requests.get(f'https://api.telegram.org/bot{v}/getMe', timeout=5).json()
                print(f"Key {k}: ok={r.get('ok')} username=@{r.get('result', {}).get('username')} desc={r.get('description')}")
            except Exception as e:
                print(f"Key {k}: request failed: {e}")
        # Check Cloudflare
        elif 'CLOUDFLARE' in k:
            masked = v[:4] + '...' + v[-4:] if len(v) > 8 else 'set'
            print(f"Key {k}: {masked}")
