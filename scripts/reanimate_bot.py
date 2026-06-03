
import requests
import os
import sys
from dotenv import load_dotenv

def reanimate():
    load_dotenv()
    if os.environ.get("OISHA_ALLOW_GCP") != "1":
        print("BLOCKED: Oisha production Oracle VMda ishlaydi. Cloud Run reanimate o'chirilgan.")
        print("Agar juda zarur bo'lsa: OISHA_ALLOW_GCP=1 qo'ying.")
        sys.exit(1)
    
    token = os.environ.get("BOT_TOKEN")
    if not token or "placeholder" in token:
        print("BOT_TOKEN topilmadi; webhookni o'zgartirmayman.")
        sys.exit(1)
    
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
