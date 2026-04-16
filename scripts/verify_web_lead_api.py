import requests
import os
import json
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

API_URL = "http://localhost:8080/api/leads"
SECRET_KEY = os.getenv("OISHA_API_SECRET", "oisha_safe_123")

def test_create_lead():
    payload = {
        "name": "Test Web Lead (Antigravity)",
        "phone": "+998901234567",
        "note": "This is a test lead from the verification script.\nBudget: 5,000,000 UZS\nGoal: Lead Integration",
        "secret_key": SECRET_KEY
    }
    
    print(f"[TEST] Sending test lead to {API_URL}...")
    try:
        response = requests.post(API_URL, json=payload)
        print(f"Status Code: {response.status_code}")
        
        result = response.json()
        if response.status_code == 200 and "lead_id" in result:
            print(f"DONE: Success! Lead created in AmoCRM. Lead ID: {result['lead_id']}")
        else:
            print(f"FAIL: Error: {result.get('error', 'Unknown error')}")
            
    except Exception as e:
        print(f"FAIL: Failed to connect to API: {e}")
        print("Note: Make sure the Oisha-OS API server is running (src/api_server.py)")

if __name__ == "__main__":
    test_create_lead()
