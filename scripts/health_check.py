import requests
import sys

SERVICES = {
    "Oisha-OS (Production)": "https://oisha-master-bot-jonbranding-85662071-ea38e.europe-west3.run.app/health",
    "JonBranding-Web": "https://jonbranding.uz/api/health",
    "SalesCoach-AI API": "https://salescoach-api-jonbranding-85662071-ea38e.europe-west3.run.app/health",
    "SalesCoach-AI Worker": "https://salescoach-worker-jonbranding-85662071-ea38e.europe-west3.run.app/",
}

def check_services():
    all_ok = True
    print("Checking Oisha-OS Ecosystem Health...")
    print("-" * 40)
    
    for name, url in SERVICES.items():
        try:
            response = requests.get(url, timeout=10)
            if response.status_code == 200:
                print(f"✅ {name}: UP (200 OK)")
            else:
                print(f"❌ {name}: DOWN ({response.status_code})")
                all_ok = False
        except Exception as e:
            print(f"❌ {name}: ERROR ({str(e)})")
            all_ok = False
            
    print("-" * 40)
    if all_ok:
        print("ALL SERVICES OPERATIONAL")
    else:
        print("SOME SERVICES ARE UNSTABLE")
        sys.exit(1)

if __name__ == "__main__":
    check_services()
