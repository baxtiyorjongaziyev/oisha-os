import os
import json
import requests
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("CRM_AUDIT")

def run_audit():
    token_file = "data/amocrm_token.json"
    if not os.path.exists(token_file):
        print(f"Token file not found at {token_file}")
        return

    with open(token_file, "r", encoding="utf-8-sig") as f: # Fixed: Using utf-8-sig to handle BOM
        token_data = json.load(f)
    
    access_token = token_data.get("access_token")
    subdomain = "jonbrandingagency"
    base_url = f"https://{subdomain}.amocrm.ru"
    headers = {
        "Authorization": f"Bearer {access_token}",
        "Content-Type": "application/json"
    }

    audit_results = {}

    # 1. Account Info
    logger.info("Checking Account Info...")
    resp = requests.get(f"{base_url}/api/v4/account", headers=headers)
    if resp.status_code == 200:
        audit_results["account"] = resp.json()
    else:
        logger.error(f"Account error: {resp.status_code}")
        audit_results["account"] = f"Error {resp.status_code}"

    # 2. Pipelines
    logger.info("Checking Pipelines...")
    resp = requests.get(f"{base_url}/api/v4/leads/pipelines", headers=headers)
    audit_results["pipelines"] = resp.json() if resp.status_code == 200 else f"Error {resp.status_code}"

    # 3. Custom Fields
    logger.info("Checking Custom Fields...")
    resp = requests.get(f"{base_url}/api/v4/leads/custom_fields", headers=headers)
    audit_results["custom_fields"] = resp.json() if resp.status_code == 200 else f"Error {resp.status_code}"

    # 4. Recent Leads
    logger.info("Checking Recent Leads...")
    resp = requests.get(f"{base_url}/api/v4/leads?limit=10&with=contacts", headers=headers)
    audit_results["recent_leads"] = resp.json() if resp.status_code == 200 else f"Error {resp.status_code}"

    # Save Results
    with open("data/crm_audit_raw.json", "w", encoding="utf-8") as f:
        json.dump(audit_results, f, ensure_ascii=False, indent=2)
    
    print("Audit data collected successfully.")

if __name__ == "__main__":
    run_audit()
