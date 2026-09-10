"""AmoCRM OAuth token'ini ko'p manbadan yuklash mantiqи (SRP bo'yicha ajratilgan).

``AmoCRMAuthMixin`` juda kengayib ketgani (>400 qator) uchun tokenni
**o'qish** qismи shu yerga ko'chirildi. ``AmoCRMAuthMixin`` bu mixin'ni
inherit qiladi, shuning uchun mavjud importlar va testlar buzilmaydi.

Manba tartibi (birinchi topilgani g'olib):

1. ``AMOCRM_TOKEN_JSON`` env — to'liq payload (deploy secret).
2. Lokal fayl (``data/amocrm_token.json``) — oxirgi rotatsiya.
3. ``AMOCRM_REFRESH_TOKEN`` env — faqat raw refresh, long-lived access'ni
   saqlab qolgan holda.
4. Turso DB — restart'ga chidamli fallback (``data/`` yo'qolganда).

Har topilgan sog'lom payload darrov DB'ga ko'chiriladi — keyingi
restart'da 4-manba tirik bo'lishi uchun.
"""

from __future__ import annotations

import json
import os
import time

import structlog

logger = structlog.get_logger()


class AmoCRMTokenLoaderMixin:
    def _load_token(self):
        """Tokenni env > fayl > raw refresh > Turso DB tartibida o'qadi."""
        if self._load_token_from_env_json():
            return
        self._load_token_from_file()
        self._apply_raw_refresh_fallback()
        if self._load_token_from_db_fallback():
            return
        # Env/fayldan yuklangan sog'lom payload'ni DB'ga ko'chirish
        if self.token_data.get("refresh_token") or self.token_data.get("access_token"):
            self._persist_token_to_db()

    def _set_token_data(self, data: dict) -> None:
        """token_data + access_token'ni bir joyda o'rnatadi."""
        self.token_data = data
        self.access_token = (
            str(data.get("access_token", "")) if data.get("access_token") else None
        )

    def _load_token_from_env_json(self) -> bool:
        """AMOCRM_TOKEN_JSON env'dan to'liq payload. True -> yuklandi."""
        env_token_json = os.environ.get("AMOCRM_TOKEN_JSON")
        if not env_token_json:
            return False
        try:
            data = json.loads(env_token_json)
            if isinstance(data, dict):
                self._set_token_data(data)
                self._persist_token_to_db()
                return True
        except Exception as e:
            self.last_error = "token_env_parse_failed"
            logger.error(f"[AMOCRM] Env token parse xatosi: {type(e).__name__}")
        return False

    def _load_token_from_file(self) -> None:
        """Diskdagi token JSON'ini o'qiydi (raw refresh'dan afzal — rotatsiya)."""
        if self.token_data or not os.path.exists(self.token_file):
            return
        for encoding in ("utf-8-sig", "utf-16"):
            try:
                with open(self.token_file, "r", encoding=encoding) as f:
                    data = json.load(f)
                if isinstance(data, dict):
                    self._set_token_data(data)
                    return
            except UnicodeError:
                continue
            except Exception as e:
                self.last_error = "token_file_load_failed"
                logger.error(f"[AMOCRM] Token yuklashda xato: {type(e).__name__}")
                return

    def _apply_raw_refresh_fallback(self) -> None:
        """AMOCRM_REFRESH_TOKEN — payload bo'sh yoki refresh_token yo'q bo'lsa."""
        raw_refresh = os.environ.get("AMOCRM_REFRESH_TOKEN")
        if not raw_refresh:
            return
        expires_at = self.token_data.get("expires_at") if isinstance(self.token_data, dict) else None
        is_long_lived = bool(
            expires_at
            and isinstance(expires_at, (int, float))
            and expires_at > (time.time() + 86400)
            and self.access_token
        )
        if not self.token_data:
            logger.info("[AMOCRM] Found raw AMOCRM_REFRESH_TOKEN fallback.")
            self.token_data = {"refresh_token": raw_refresh}
            self.access_token = None
        elif not self.token_data.get("refresh_token"):
            if is_long_lived:
                logger.debug("[AMOCRM] Retaining valid long-lived access token and attaching refresh fallback.")
                self.token_data["refresh_token"] = raw_refresh
            else:
                logger.info("[AMOCRM] Found raw AMOCRM_REFRESH_TOKEN fallback.")
                self.token_data = {"refresh_token": raw_refresh}
                self.access_token = None

    def _load_token_from_db_fallback(self) -> bool:
        """Turso DB fallback — env/fayl butunlay bo'sh bo'lganda. True -> yuklandi."""
        if self.token_data and (self.token_data.get("refresh_token") or self.token_data.get("access_token")):
            return False
        try:
            from src.services.core.crm.amocrm.token_store import load_token_from_db

            db_token = load_token_from_db()
            if isinstance(db_token, dict) and (db_token.get("refresh_token") or db_token.get("access_token")):
                self._set_token_data(db_token)
                logger.info("[AMOCRM] Token Turso DB fallback'dan yuklandi (restart-proof)")
                return True
        except Exception as e:
            logger.warning("[AMOCRM] DB token yuklashda xato: %s", type(e).__name__)
        return False

    def _persist_token_to_db(self):
        """Joriy token_data'ni Turso DB'ga yozadi (best-effort, xato yutiladi)."""
        try:
            from src.services.core.crm.amocrm.token_store import save_token_to_db

            if isinstance(self.token_data, dict) and (self.token_data.get("refresh_token") or self.token_data.get("access_token")):
                save_token_to_db(self.token_data)
        except Exception as e:
            logger.debug("[AMOCRM] DB token persist skip: %s", type(e).__name__)

    def _reload_freshest_token(self):
        """Env/fayl/DB'dan eng yangi AmoCRM token payload'ini qaytaradi.

        Refresh guard bunga tayanadi: parallel instance yoki oldingi process
        (SIGKILL'dan oldin) bardavom joyga yangiroq token yozgan bo'lishi
        mumkin. ``pick_freshest`` ``expires_at`` bo'yicha eng yangisini oladi.
        """
        try:
            from src.services.core.crm.amocrm.token_store import (
                load_token_from_db,
                pick_freshest,
            )

            db_token = load_token_from_db()
            current = self.token_data if isinstance(self.token_data, dict) else None
            return pick_freshest(current, db_token)
        except Exception as e:
            logger.debug("[AMOCRM] freshest reload skip: %s", type(e).__name__)
            return self.token_data if isinstance(self.token_data, dict) else None
