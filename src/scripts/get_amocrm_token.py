"""
AmoCRM OAuth token olish uchun yordamchi script.

Ishlatish:
    python -m src.scripts.get_amocrm_token

AmoCRM OAuth2 flow:
    1. Brauzerada oching: https://{subdomain}.amocrm.ru/oauth2/authorize?client_id={client_id}&redirect_uri={redirect_uri}
    2. Ruxsat bering
    3. Redirect URL dan authorization code ni oling
    4. Bu script orqali code ni token ga almashtiring
"""
from __future__ import annotations

import json
import os
import sys
import httpx


def exchange_code(code: str, redirect_uri: str | None = None) -> dict:
    """Authorization code ni token ga almashtirish."""
    subdomain = os.getenv("AMOCRM_SUBDOMAIN", "")
    client_id = os.getenv("AMOCRM_CLIENT_ID", "")
    client_secret = os.getenv("AMOCRM_CLIENT_SECRET", "")
    redirect_url = redirect_uri or os.getenv("AMOCRM_REDIRECT_URL", "https://localhost")

    if not all([subdomain, client_id, client_secret]):
        print("XATO: AMOCRM_SUBDOMAIN, AMOCRM_CLIENT_ID, AMOCRM_CLIENT_SECRET kerak")
        sys.exit(1)

    url = f"https://{subdomain}.amocrm.ru/oauth2/access_token"
    payload = {
        "client_id": client_id,
        "client_secret": client_secret,
        "grant_type": "authorization_code",
        "code": code,
        "redirect_uri": redirect_url,
    }

    resp = httpx.post(url, json=payload, timeout=30)
    resp.raise_for_status()
    return resp.json()


def main():
    if len(sys.argv) < 2:
        print("Ishlatish: python -m src.scripts.get_amocrm_token <authorization_code> [--redirect-uri URL]")
        print()
        print("1. AmoCRM Integratsiya sozlamalarida Redirect URI ni 'http://localhost' ga o'zgartiring")
        print("2. Brauzerada oching:")
        subdomain = os.getenv("AMOCRM_SUBDOMAIN", "YOUR_SUBDOMAIN")
        client_id = os.getenv("AMOCRM_CLIENT_ID", "YOUR_CLIENT_ID")
        print(f"   https://{subdomain}.amocrm.ru/oauth2/authorize?client_id={client_id}&redirect_uri=http://localhost")
        print()
        print("3. Ruxsat bering")
        print("4. Brauzer URL bar dan code ni oling (?code=...)")
        print("5. python -m src.scripts.get_amocrm_token <code>")
        sys.exit(0)

    code = sys.argv[1]
    redirect_uri = None
    if "--redirect-uri" in sys.argv:
        idx = sys.argv.index("--redirect-uri")
        redirect_uri = sys.argv[idx + 1] if idx + 1 < len(sys.argv) else None

    print(f"Code: {code[:10]}...")
    print("Token olinmoqda...")

    try:
        data = exchange_code(code, redirect_uri)
        print()
        print("MUVAFFAQIYATLI!")
        print()
        print("Refresh token (env ga qo'shing):")
        print(f"AMOCRM_REFRESH_TOKEN={data.get('refresh_token', '')}")
        print()
        print("To'liq javob:")
        print(json.dumps(data, indent=2))

        # Token faylga saqlash
        token_file = "amocrm_token.json"
        with open(token_file, "w") as f:
            json.dump(data, f, indent=2)
        print(f"\nToken faylga saqlandi: {token_file}")

    except httpx.HTTPStatusError as e:
        print(f"XATO: {e.response.status_code}")
        print(e.response.text)
    except Exception as e:
        print(f"XATO: {e}")


if __name__ == "__main__":
    main()
