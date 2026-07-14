import requests
import re

from bs4 import BeautifulSoup

email = "jonbranding@agency.uz"
password = "a123456"

session = requests.Session()
login_url = "https://jonbrandingagency.moizvonki.ru/accounts/login/"
r = session.get(login_url)
print("GET Login Status:", r.status_code)
csrf_token = session.cookies.get("csrftoken")

# Extract csrfmiddlewaretoken from HTML
csrf_mid = re.search(r'name=["\']csrfmiddlewaretoken["\']\s+value=["\']([^"\']+)["\']', r.text)
csrf_val = csrf_mid.group(1) if csrf_mid else csrf_token

login_data = {
    "csrfmiddlewaretoken": csrf_val,
    "username": email,
    "password": password,
    "foreign_pc": "on"
}

# POST login
# Referer header is often required for CSRF validation
headers = {
    "Referer": login_url,
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)"
}
r_post = session.post(login_url, data=login_data, headers=headers)
print("POST Login Status:", r_post.status_code)
print("POST Cookies:", session.cookies.get_dict())

# Let's query recent calls from the last 7 days
import time
payload = {
    "user_name": "jonbranding@agency.uz",
    "api_key": "4bj3tqn0mbq54crzfr2zqnjnfrb3n3rd",
    "action": "calls.list",
    "from_date": int(time.time()) - 7 * 24 * 3600,
    "max_results": 20
}
url = "https://jonbrandingagency.moizvonki.ru/api/v1"
r_calls = requests.post(url, json=payload)
data = r_calls.json()
calls = data.get("results", [])
print("Total recent calls:", len(calls))
for c in calls:
    if c.get("db_call_id") == 5000:
        rec_url = c.get("recording")
        print("Recording URL for 5000:", rec_url)
        # Download and transcribe
        r_audio = session.get(rec_url)
        print("Audio Status:", r_audio.status_code)
        print("Audio Length:", len(r_audio.content))
        if len(r_audio.content) > 100000:
            with open("test_5000.mp3", "wb") as f:
                f.write(r_audio.content)
            print("Saved test_5000.mp3")
            import os, dotenv
            dotenv.load_dotenv("/home/ubuntu/oisha-os/.env")
            key = os.environ.get("GROQ_API_KEY")
            if key:
                with open("test_5000.mp3", "rb") as f:
                    r_trans = requests.post(
                        "https://api.groq.com/openai/v1/audio/transcriptions",
                        headers={"Authorization": f"Bearer {key}"},
                        files={"file": ("test_5000.mp3", f, "audio/mpeg")},
                        data={"model": "whisper-large-v3-turbo", "response_format": "json"}
                    )
                    print("Groq Response:", r_trans.json().get("text", "No text").encode("utf-8"))
            else:
                print("No GROQ_API_KEY")








