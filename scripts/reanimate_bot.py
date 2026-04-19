
import requests
import os
import sys
from dotenv import load_dotenv

def reanimate():
    load_dotenv()
    
    token = os.environ.get("BOT_TOKEN")
    if not token or "placeholder" in token:
        # Try to find it in the current session or settings
        token = "8343217526:AAEOA8Jg8YMEwQREFF2MaK1oZVhFA3b1SQo"
    
    cloud_run_url = "https://oisha-master-bot-982617914297.europe-west3.run.app"
    
    print(f"REANIMATING OISHA...")
    print(f"Target Token: {token[:10]}...")
    print(f"Target URL: {cloud_run_url}")
    
    # 1. Delete Webhook (Enable Polling)
    delete_url = f"https://api.telegram.org/bot{token}/deleteWebhook"
    response = requests.post(delete_url)
    print(f"DELETE WEBHOOK: {response.json()}")
    
    # 2. Get Info
    info_url = f"https://api.telegram.org/bot{token}/getWebhookInfo"
    info = requests.get(info_url).json()
    print(f"WEBHOOK INFO: {info}")
    
    # 3. Health Check
    try:
        health = requests.get(f"{cloud_run_url}/")
        print(f"CLOUD RUN HEALTH: {health.status_code} - {health.text[:50]}")
    except Exception as e:
        print(f"CLOUD RUN HEALTH ERROR: {e}")

if __name__ == "__main__":
    reanimate()
