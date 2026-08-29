"""
Airtable OAuth2 token manager and refresh lifecycle.
"""
from __future__ import annotations

import base64
import json
import logging
import os
import time
from typing import Any, Dict, Optional
import requests

logger = logging.getLogger("AirtableOAuth")

_AIRTABLE_TOKEN_URL = "https://airtable.com/oauth2/v1/token"
_AIRTABLE_OAUTH_TOKEN_FILE = os.path.join("data", "airtable_oauth_token.json")


class AirtableOAuth:
    """Airtable OAuth 2.0 token boshqaruvchisi.

    API key (PAT) o'rniga to'g'ridan-to'g'ri OAuth access token bilan ishlaydi.
    Access token muddati tugasa (401), refresh token orqali yangilaydi va
    yangi tokenlarni diskka saqlaydi. Airtable refresh tokenlari rotatsiya
    qilinadi — har refreshdan keyin yangi refresh_token qaytadi.
    """

    def __init__(self, client_id, client_secret, access_token, refresh_token,
                 token_file=_AIRTABLE_OAUTH_TOKEN_FILE):
        self.client_id = client_id
        self.client_secret = client_secret
        self.token_file = token_file
        self.access_token = access_token
        self.refresh_token = refresh_token
        # Diskda saqlangan (yangilangan) tokenlar env'dan ustun turadi
        self._load_from_disk()

    @property
    def configured(self) -> bool:
        return bool(self.client_id and self.refresh_token)

    def _load_from_disk(self):
        try:
            with open(self.token_file, "r", encoding="utf-8") as fh:
                data = json.load(fh)
            if data.get("access_token"):
                self.access_token = data["access_token"]
            if data.get("refresh_token"):
                self.refresh_token = data["refresh_token"]
        except FileNotFoundError:
            pass
        except Exception as exc:
            logger.warning("[AIRTABLE OAUTH] Token faylini o'qishda xato: %s", exc)

    def _save_to_disk(self):
        try:
            token_dir = os.path.dirname(self.token_file)
            if token_dir:
                os.makedirs(token_dir, exist_ok=True)
            # Atomik yozish: chala yozilgan fayl token'ni buzmasligi uchun
            temp_file = f"{self.token_file}.tmp"
            with open(temp_file, "w", encoding="utf-8") as fh:
                json.dump(
                    {"access_token": self.access_token, "refresh_token": self.refresh_token},
                    fh,
                )
            os.replace(temp_file, self.token_file)
        except Exception as exc:
            logger.warning("[AIRTABLE OAUTH] Token faylini saqlashda xato: %s", exc)

    def bearer(self) -> str:
        return self.access_token or ""

    def refresh(self) -> bool:
        """Refresh token orqali yangi access token oladi. Muvaffaqiyatda True."""
        if not (self.client_id and self.refresh_token):
            return False
        try:
            auth = None
            data = {
                "grant_type": "refresh_token",
                "refresh_token": self.refresh_token,
                "client_id": self.client_id,
            }
            # Confidential client bo'lsa — Basic auth; public client bo'lsa client_id body'da
            if self.client_secret:
                auth = (self.client_id, self.client_secret)
            resp = requests.post(_AIRTABLE_TOKEN_URL, data=data, auth=auth, timeout=30)
            if resp.status_code == 200:
                payload = resp.json()
                self.access_token = payload.get("access_token", self.access_token)
                # Airtable refresh tokenni rotatsiya qiladi
                if payload.get("refresh_token"):
                    self.refresh_token = payload["refresh_token"]
                self._save_to_disk()
                logger.info("[AIRTABLE OAUTH] Access token yangilandi.")
                return True
            logger.error(
                "[AIRTABLE OAUTH] Refresh xato %s: %s", resp.status_code, resp.text[:200]
            )
            return False
        except Exception as exc:
            logger.error("[AIRTABLE OAUTH] Refresh exception: %s", exc)
            return False
