import os
import dotenv
import requests

env = dotenv.dotenv_values('/root/oisha-os/.env')
account_id = env.get('CLOUDFLARE_ACCOUNT_ID')
token = env.get('CLOUDFLARE_AI_API_TOKEN')

url = f"https://api.cloudflare.com/client/v4/accounts/{account_id}/ai/run/@cf/meta/llama-3.1-8b-instruct"
headers = {"Authorization": f"Bearer {token}"}
resp = requests.post(url, headers=headers, json={"messages": [{"role": "user", "content": "hello"}]}, timeout=10)
print("CF Status:", resp.status_code)
print("CF Body:", resp.text[:200])
