"""Google Calendar uchun OAuth token yaratadi (owner brauzerida bir marta).

Ishlatish (lokal kompyuterda):

    python scripts/google_calendar_auth.py \
        --client-secrets credentials.json \
        --token token.pickle

Soʻng `token.pickle` ni prod serverdagi `/home/ubuntu/oisha-os/` ga qoʻying,
`chmod 600 token.pickle` qiling va `oisha-os.service` ni restart qiling.
"""
from __future__ import annotations

import argparse
import os
import pickle
import stat
import sys

SCOPES = ["https://www.googleapis.com/auth/calendar.events"]


def _parse_args(argv=None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--client-secrets",
        default=os.getenv("GOOGLE_OAUTH_CLIENT_SECRETS", "credentials.json"),
        help="Google Clouddan yuklangan OAuth Desktop client JSON fayli.",
    )
    parser.add_argument(
        "--token",
        default=os.getenv("GOOGLE_CALENDAR_TOKEN_PATH", "token.pickle"),
        help="Yaratiladigan token fayli (default: token.pickle).",
    )
    parser.add_argument(
        "--force",
        action="store_true",
        help="Mavjud tokenni qayta yaratish.",
    )
    return parser.parse_args(argv)


def main(argv=None) -> int:
    args = _parse_args(argv)

    if os.path.exists(args.token) and not args.force:
        print(f"Token mavjud: {args.token}. Qayta yaratish uchun --force ishlating.")
        return 0
    if not os.path.exists(args.client_secrets):
        print(
            f"OAuth client secrets topilmadi: {args.client_secrets}",
            file=sys.stderr,
        )
        return 1

    try:
        from google_auth_oauthlib.flow import InstalledAppFlow
    except ImportError:
        print(
            "google-auth-oauthlib oʻrnatilmagan: pip install google-auth-oauthlib",
            file=sys.stderr,
        )
        return 1

    flow = InstalledAppFlow.from_client_secrets_file(args.client_secrets, SCOPES)
    credentials = flow.run_local_server(port=0, prompt="consent")
    with open(args.token, "wb") as token_file:
        pickle.dump(credentials, token_file)
    try:
        os.chmod(args.token, stat.S_IRUSR | stat.S_IWUSR)
    except OSError:
        pass

    print(f"Token yozildi: {args.token}")
    print(
        "Keyingi qadam: faylni prod serverga qoʻying, chmod 600 qiling va "
        "oisha-os.service ni restart qiling."
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
