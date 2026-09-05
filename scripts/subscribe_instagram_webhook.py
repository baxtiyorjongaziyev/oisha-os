"""
Subscribes or inspects Facebook Page / Instagram App Webhook fields.
Supports --check to inspect currently subscribed fields.
"""
import os
import sys
import httpx
from dotenv import load_dotenv

load_dotenv(override=True)

if sys.platform == "win32":
    sys.stdout.reconfigure(encoding="utf-8")


def check_subscription(page_id: str, token: str):
    url = f"https://graph.facebook.com/v19.0/{page_id}/subscribed_apps"
    try:
        res = httpx.get(url, params={"access_token": token}, timeout=20.0)
        print(f"GET {url} -> Status: {res.status_code}")
        print(f"Subscribed Apps & Fields:\n{res.text}")
    except Exception as e:
        print(f"[EXCEPTION] Failed to check subscription: {e}")


def subscribe(page_id: str, token: str, fields: str = "feed,conversations,messages,comments,mentions"):
    url = f"https://graph.facebook.com/v19.0/{page_id}/subscribed_apps"
    params = {
        "subscribed_fields": fields,
        "access_token": token,
    }
    print(f"Subscribing Page ID: {page_id} to webhook fields: {fields}...")
    try:
        res = httpx.post(url, params=params, timeout=20.0)
        print(f"POST Status Code: {res.status_code}")
        print(f"POST Response: {res.text}")
        if res.status_code == 200 and res.json().get("success") is True:
            print("\n[SUCCESS] Webhook subscribed successfully!")
        else:
            # Fallback if any field was rejected
            print("\n[INFO] Attempting fallback with canonical fields: feed,conversations,messages...")
            res2 = httpx.post(url, params={"subscribed_fields": "feed,conversations,messages", "access_token": token}, timeout=20.0)
            print(f"Fallback Status: {res2.status_code} -> {res2.text}")
    except Exception as e:
        print(f"[EXCEPTION] Failed to subscribe: {e}")


def main():
    token = os.getenv("META_PAGE_ACCESS_TOKEN", "").strip()
    page_id = os.getenv("META_PAGE_ID", "103894334533931").strip()

    if not token:
        print("[ERROR] META_PAGE_ACCESS_TOKEN is missing in .env")
        sys.exit(1)

    if "--check" in sys.argv:
        check_subscription(page_id, token)
    else:
        fields = "feed,conversations,messages,comments,mentions"
        for i, arg in enumerate(sys.argv):
            if arg == "--fields" and i + 1 < len(sys.argv):
                fields = sys.argv[i + 1]
        subscribe(page_id, token, fields)
        print("\n--- Current Subscriptions ---")
        check_subscription(page_id, token)


if __name__ == "__main__":
    main()
