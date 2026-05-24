import requests
from settings import settings
from amocrm_sync import AmoCRMSync


def research():
    amocrm = AmoCRMSync(
        settings.AMOCRM_SUBDOMAIN,
        settings.AMOCRM_CLIENT_ID,
        settings.AMOCRM_CLIENT_SECRET.get_secret_value(),
        settings.AMOCRM_REDIRECT_URL,
    )
    amocrm._load_token()
    headers = amocrm._get_headers()

    # 1. Pipelines
    p_resp = requests.get(f"{amocrm.base_url}/api/v4/leads/pipelines", headers=headers, timeout=30)
    pipelines = p_resp.json().get("_embedded", {}).get("pipelines", [])
    print("PIPELINES:")
    for pipe in pipelines:
        print(f"{pipe['id']} | {pipe['name']}")
        statuses = pipe.get("_embedded", {}).get("statuses", [])
        for status in statuses:
            print(f"  - {status['id']} | {status['name']}")

    # 2. Users
    u_resp = requests.get(f"{amocrm.base_url}/api/v4/users", headers=headers, timeout=30)
    users = u_resp.json().get("_embedded", {}).get("users", [])
    print("\nAMO_USERS:")
    for user in users:
        print(
            f"{user['id']} | {user['name']} ({user['email'] if 'email' in user else ''})"
        )


if __name__ == "__main__":
    research()
