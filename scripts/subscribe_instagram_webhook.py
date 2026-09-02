"""
Subscribes the Facebook Page / Instagram App to Webhook fields (feed, comments, messages).
"""
import os
import sys
import httpx
from dotenv import load_dotenv

load_dotenv(override=True)

if sys.platform == "win32":
    sys.stdout.reconfigure(encoding="utf-8")

def main():
    token = os.getenv("META_PAGE_ACCESS_TOKEN", "").strip()
    page_id = os.getenv("META_PAGE_ID", "103894334533931").strip()
    
    if not token:
        print("[ERROR] META_PAGE_ACCESS_TOKEN is missing in .env")
        sys.exit(1)
        
    url = f"https://graph.facebook.com/v19.0/{page_id}/subscribed_apps"
    params = {
        "subscribed_fields": "feed,conversations,messages",
        "access_token": token,
    }
    
    print(f"Subscribing Page ID: {page_id} to webhook fields: {params['subscribed_fields']}...")
    try:
        res = httpx.post(url, params=params, timeout=20.0)
        print(f"Status Code: {res.status_code}")
        print(f"Response: {res.text}")
        if res.status_code == 200 and res.json().get("success") is True:
            print("\n[SUCCESS] Webhook subscribed successfully!")
        else:
            print("\n[WARNING] Subscription returned non-success response.")
    except Exception as e:
        print(f"[EXCEPTION] Failed to subscribe: {e}")
        sys.exit(1)

if __name__ == "__main__":
    main()
