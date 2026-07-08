import os
import requests

API_KEY = os.environ.get("MOIZVONKI_API_KEY", "")
url = "https://jonbrandingagency.moizvonki.ru/calls/recordings/CHYSAlcyisFYrEijUDEWswXbJURDcRMk.mp3/"

# Try different auth methods and check output size/content
methods = [
    ("Anonymous", lambda: requests.get(url)),
    ("Basic Auth (baxtiyorjongaziyev@gmail.com, key)", lambda: requests.get(url, auth=("baxtiyorjongaziyev@gmail.com", API_KEY))),
    ("Basic Auth (jonbranding@operator.uz, key)", lambda: requests.get(url, auth=("jonbranding@operator.uz", API_KEY))),
    ("Basic Auth (key as username, email as password)", lambda: requests.get(url, auth=(API_KEY, "baxtiyorjongaziyev@gmail.com"))),
]

for name, fn in methods:
    try:
        r = fn()
        # Get first 32 bytes as hex
        prefix = r.content[:32].hex()
        print(f"{name:50} -> Status: {r.status_code}, Length: {len(r.content)}, Prefix: {prefix}")
    except Exception as e:
        print(f"{name:50} -> Error: {e}")
