import argparse
import json
import sys
from pathlib import Path

import requests

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from src.settings import settings


TOKEN_FILE = Path("data/amocrm_token.json")


def refresh_amocrm_token(write_secret_file: str | None = None) -> bool:
    if not TOKEN_FILE.exists():
        print("status=failed reason=token_file_missing")
        return False

    token_data = json.loads(TOKEN_FILE.read_text(encoding="utf-8-sig"))
    refresh_token = token_data.get("refresh_token")
    if not refresh_token:
        print("status=failed reason=refresh_token_missing")
        return False

    url = f"https://{settings.AMOCRM_SUBDOMAIN}.amocrm.ru/oauth2/access_token"
    data = {
        "client_id": settings.AMOCRM_CLIENT_ID,
        "client_secret": settings.AMOCRM_CLIENT_SECRET.get_secret_value() if settings.AMOCRM_CLIENT_SECRET else "",
        "grant_type": "refresh_token",
        "refresh_token": refresh_token,
        "redirect_uri": settings.AMOCRM_REDIRECT_URL,
    }

    print(f"refreshing_subdomain={settings.AMOCRM_SUBDOMAIN}")
    response = requests.post(url, json=data, timeout=30)
    if response.status_code == 400:
        response = requests.post(url, data=data, timeout=30)

    if response.status_code != 200:
        print(f"status=failed http={response.status_code}")
        return False

    new_token_data = response.json()
    TOKEN_FILE.parent.mkdir(exist_ok=True)
    TOKEN_FILE.write_text(json.dumps(new_token_data, ensure_ascii=True, indent=2), encoding="utf-8")

    if write_secret_file:
        Path(write_secret_file).write_text(json.dumps(new_token_data, ensure_ascii=True), encoding="utf-8")

    print("status=ok token_refreshed=True")
    return True


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Refresh AmoCRM OAuth token without printing secrets.")
    parser.add_argument(
        "--write-secret-file",
        help="Optional path for a compact JSON copy that can be uploaded to Secret Manager.",
    )
    args = parser.parse_args()
    raise SystemExit(0 if refresh_amocrm_token(args.write_secret_file) else 1)
