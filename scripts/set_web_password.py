"""Owner uchun: Oisha web-panel hisobini yaratish yoki parolini almashtirish.

Repo ildizidan ishga tushiring (data/web_auth_sessions.db shu yerda).

    python scripts/set_web_password.py owner@example.com --role owner --generate
    python scripts/set_web_password.py user@example.com --role targetolog   # parol soʼraydi

Parol hech qayerga yozilmaydi; --generate boʼlsa faqat bir marta ekranga chiqadi.
"""
from __future__ import annotations

import argparse
import getpass
import os
import secrets
import sys

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))

from src.api.web_auth_store import MIN_PASSWORD_LENGTH, set_user_password  # noqa: E402


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("email")
    parser.add_argument("--role", default="targetolog")
    parser.add_argument("--name", default=None)
    parser.add_argument("--generate", action="store_true", help="kuchli tasodifiy parol yaratish")
    args = parser.parse_args()

    if args.generate:
        password = secrets.token_urlsafe(15)
    else:
        password = getpass.getpass(f"Yangi parol (kamida {MIN_PASSWORD_LENGTH} belgi): ")

    try:
        result = set_user_password(args.email, password, role=args.role, name=args.name)
    except ValueError as exc:
        print(f"Xato: {exc}", file=sys.stderr)
        return 1

    print(f"{'Yaratildi' if result['created'] else 'Yangilandi'}: {result['email']} (rol: {result['role']})")
    if args.generate:
        print(f"Parol (faqat hozir koʼrsatiladi): {password}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
