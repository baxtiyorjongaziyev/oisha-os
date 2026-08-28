"""Oracle VM dagi amoCRM tokenini tiklash.

1. GitHub secret'dagi AMOCRM_TOKEN_JSON ni data/amocrm_token.json ga yozadi
2. refresh_crm_token.py orqali yangi access_token oladi
"""
import json
import os
import sys
from pathlib import Path

def main():
    token_json_env = os.environ.get("AMOCRM_TOKEN_JSON", "").strip()
    refresh_token_env = os.environ.get("AMOCRM_REFRESH_TOKEN", "").strip()
    token_path = Path("data/amocrm_token.json")

    # Mavjud token faylini tekshirish
    existing = {}
    if token_path.exists():
        try:
            existing = json.loads(token_path.read_text(encoding="utf-8-sig"))
        except Exception:
            pass

    has_refresh = bool(existing.get("refresh_token"))
    print(f"Mavjud fayl: {'bor' if token_path.exists() else 'yo_q'}")
    print(f"Mavjud refresh_token: {'bor' if has_refresh else 'yo_q'}")

    # Agar faylda refresh_token yo'q — env'dan tiklash
    if not has_refresh:
        if token_json_env:
            print("AMOCRM_TOKEN_JSON env'dan tiklanmoqda...")
            try:
                token_data = json.loads(token_json_env)
                if token_data.get("refresh_token"):
                    token_path.parent.mkdir(exist_ok=True)
                    token_path.write_text(json.dumps(token_data, indent=2), encoding="utf-8")
                    os.chmod(str(token_path), 0o600)
                    print(f"OK: token fayl yozildi, refresh_token bor")
                    return 0
                else:
                    print("AMOCRM_TOKEN_JSON da ham refresh_token yo'q")
            except json.JSONDecodeError as e:
                print(f"AMOCRM_TOKEN_JSON JSON parse xatosi: {e}")

        if refresh_token_env:
            print("AMOCRM_REFRESH_TOKEN env'dan tiklanmoqda...")
            # Mavjud faylga refresh_token qo'shish
            existing["refresh_token"] = refresh_token_env
            token_path.parent.mkdir(exist_ok=True)
            token_path.write_text(json.dumps(existing, indent=2), encoding="utf-8")
            os.chmod(str(token_path), 0o600)
            print("OK: refresh_token faylga qo'shildi")
            return 0

        print("XATO: refresh_token topilmadi (na faylda, na env'da)")
        return 1
    else:
        print("refresh_token allaqachon faylda bor — tiklash shart emas")
        return 0


if __name__ == "__main__":
    sys.exit(main())
