import requests
import json
import os

def refresh_amocrm_token():
    token_file = "data/amocrm_token.json"
    with open(token_file, "r", encoding="utf-8-sig") as f:
        token_data = json.load(f)
    
    subdomain = "jonbrandingagency"
    client_id = "5a755b58-f5d1-477d-965d-a50ddaa3d55e"
    client_secret = "***REDACTED***"
    redirect_url = "https://us-central1-jonbranding-85662071-ea38e.cloudfunctions.net/amocrmOAuthCallback"
    
    url = f"https://{subdomain}.amocrm.ru/oauth2/access_token"
    data = {
        "client_id": client_id,
        "client_secret": client_secret,
        "grant_type": "refresh_token",
        "refresh_token": token_data.get("refresh_token"),
        "redirect_uri": redirect_url,
    }
    
    print(f"Refreshing token for {subdomain}...")
    response = requests.post(url, json=data)
    
    if response.status_code == 200:
        new_token_data = response.json()
        with open(token_file, "w", encoding="utf-8") as f:
            json.dump(new_token_data, f, indent=2)
        print("Token refreshed successfully!")
        return True
    else:
        print(f"Failed to refresh token: {response.status_code}")
        print(response.text)
        return False

if __name__ == "__main__":
    refresh_amocrm_token()
