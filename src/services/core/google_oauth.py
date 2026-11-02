"""Google OAuth foydalanuvchi tokenini xavfsiz (JSON) saqlash va yuklash.

Pickle oʻrniga `Credentials.to_json()` ishlatiladi: fayl oddiy JSON boʻlgani
uchun uni ochish kod ijrosiga olib kelmaydi. Eski `token.pickle` fayllari
qoʻllab-quvvatlanmaydi — `scripts/google_calendar_auth.py` bilan qayta yarating.
"""
from __future__ import annotations

import logging
import os
import stat
from typing import Iterable, Optional

try:
    from google.auth.transport.requests import Request
    from google.oauth2.credentials import Credentials as UserCredentials
except ImportError:  # google-auth oʻrnatilmagan muhitlar uchun
    Request = None
    UserCredentials = None

logger = logging.getLogger(__name__)

# Bitta token bilan Calendar va Contacts ishlashi uchun umumiy scope toʻplami.
GOOGLE_USER_SCOPES = (
    "https://www.googleapis.com/auth/calendar.events",
    "https://www.googleapis.com/auth/contacts",
    "https://www.googleapis.com/auth/directory.readonly",
)


def _chmod_private(path: str) -> None:
    try:
        os.chmod(path, stat.S_IRUSR | stat.S_IWUSR)
    except OSError:
        pass


def save_user_credentials(token_path: str, credentials) -> bool:
    """Tokenni JSON sifatida yozadi (faqat egasi oʻqiy oladi)."""
    if not token_path or credentials is None:
        return False
    try:
        payload = credentials.to_json()
    except Exception as exc:  # pragma: no cover - himoyaviy
        logger.error(f"[GOOGLE OAUTH] Tokenni JSON ga aylantirishda xato: {exc}")
        return False
    try:
        with open(token_path, "w", encoding="utf-8") as token_file:
            token_file.write(payload)
        _chmod_private(token_path)
        return True
    except OSError as exc:
        logger.error(f"[GOOGLE OAUTH] Tokenni yozishda xato: {exc}")
        return False


def load_user_credentials(
    token_path: str, scopes: Optional[Iterable[str]] = None
) -> Optional[object]:
    """JSON tokenni oʻqiydi, muddati oʻtgan boʻlsa yangilaydi."""
    if not token_path or not os.path.exists(token_path):
        return None
    if UserCredentials is None:
        logger.error("[GOOGLE OAUTH] google-auth oʻrnatilmagan.")
        return None
    if token_path.endswith(".pickle"):
        logger.error(
            "[GOOGLE OAUTH] pickle token qoʻllab-quvvatlanmaydi: "
            f"{token_path}. scripts/google_calendar_auth.py bilan token.json yarating."
        )
        return None
    try:
        credentials = UserCredentials.from_authorized_user_file(
            token_path, list(scopes) if scopes else None
        )
    except (ValueError, OSError) as exc:
        logger.error(f"[GOOGLE OAUTH] Tokenni oʻqishda xato ({token_path}): {exc}")
        return None

    if credentials.expired and credentials.refresh_token:
        try:
            credentials.refresh(Request())
        except Exception as exc:
            logger.error(f"[GOOGLE OAUTH] Tokenni yangilashda xato: {exc}")
            return None
        save_user_credentials(token_path, credentials)
    return credentials
