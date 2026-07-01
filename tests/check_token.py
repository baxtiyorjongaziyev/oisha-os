import httpx, json, time

token_file = "data/amocrm_token.json"
with open(token_file) as f:
    data = json.load(f)

token = data["access_token"]
expires_at = data["expires_at"]
now = int(time.time())

print(f"Token: {token[:30]}...")
print(f"Expires at: {expires_at}")
print(f"Now: {now}")
print(f"Expired: {now > expires_at}")

# Test API call
url = "https://jonbrandingagency.amocrm.ru/api/v4/account"
headers = {"Authorization": f"Bearer {token}"}
resp = httpx.get(url, headers=headers, timeout=10)
print(f"Status: {resp.status_code}")
if resp.status_code == 200:
    print("Token ISHLAYAPTI!")
else:
    print(f"Error: {resp.text[:200]}")
