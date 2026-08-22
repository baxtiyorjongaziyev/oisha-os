"""Exchange AmoCRM Authorization Code for Access & Refresh Tokens.

Usage:
    python scripts/exchange_amocrm_code.py <AUTH_CODE>
"""
from __future__ import annotations

import sys
import json
import os
from pathlib import Path
from dotenv import load_dotenv

# Add project root to sys.path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

if sys.platform == "win32":
    sys.stdout.reconfigure(encoding="utf-8")

load_dotenv()

from src.services.core.crm.amocrm_sync import AmoCRMSync
from src.settings import settings


def main():
    if len(sys.argv) < 2:
        print("Usage: python scripts/exchange_amocrm_code.py <AUTH_CODE>")
        sys.exit(1)

    auth_code = sys.argv[1].strip()
    print(f"[*] AmoCRM Authorization code qabul qilindi: {auth_code[:10]}...")

    sync = AmoCRMSync(
        subdomain=settings.AMOCRM_SUBDOMAIN,
        client_id=settings.AMOCRM_CLIENT_ID,
        client_secret=(
            settings.AMOCRM_CLIENT_SECRET.get_secret_value()
            if settings.AMOCRM_CLIENT_SECRET
            else None
        ),
        redirect_url=settings.AMOCRM_REDIRECT_URL,
    )

    success = sync.authorize_initial(auth_code)
    if success:
        print("[✅] AmoCRM tokenlari muvaffaqiyatli yangilandi va saqlandi!")
        print(f"    - Subdomain: {sync.subdomain}")
        print(f"    - Access token: {sync.access_token[:20]}...")
    else:
        print(f"[❌] Token olishda xatolik: {sync.last_error}")


if __name__ == "__main__":
    main()
