import asyncio
import os
import time
import json
import requests  # type: ignore
import tempfile
from typing import Any
from functools import wraps

import structlog

from src.services.core.crm.amocrm.token_loader import AmoCRMTokenLoaderMixin

logger = structlog.get_logger()


def retry_with_backoff(
    max_retries=3,
    initial_delay=1,
    backoff_factor=2,
    exceptions=(requests.RequestException,),
):
    """Decorator to retry API calls with exponential backoff."""

    def decorator(func):
        @wraps(func)
        def wrapper(*args, **kwargs):
            delay = initial_delay
            last_exception = None

            for attempt in range(max_retries):
                try:
                    return func(*args, **kwargs)
                except exceptions as e:
                    last_exception = e
                    logger.warning(
                        f"[AMOCRM RETRY] {func.__name__} attempt {attempt + 1}/{max_retries} failed: {e}"
                    )
                    if attempt < max_retries - 1:
                        time.sleep(delay)
                        delay *= backoff_factor

            logger.error(
                f"[AMOCRM RETRY] {func.__name__} failed after {max_retries} attempts: {last_exception}"
            )
            raise last_exception

        return wrapper

    return decorator


def _plain_secret(value: Any) -> Any:
    """Pydantic SecretStr'ni oddiy matnga aylantiradi.

    OAuth so'rovlari client_secret'ni JSON yoki form body'da yuboradi.
    SecretStr obyekti JSON-serializable emas, form-encoding'da esa
    '**********' ko'rinishida maskalanadi — ikkala holatda ham auth jim
    yiqiladi. Chaqiruvchilarning bir qismi settings'dan xom SecretStr uzatadi,
    shuning uchun normallashtirishni shu yerda, bitta joyda qilamiz.
    """
    getter = getattr(value, "get_secret_value", None)
    return getter() if callable(getter) else value



class AmoCRMAuthMixin(AmoCRMTokenLoaderMixin):
    """OAuth token saqlash + refresh. Yuklash mantiqи ``AmoCRMTokenLoaderMixin``da."""

    def _save_token(self, token_data):
        """Atomically save OAuth tokens with owner-only file permissions.

        Yozish tartibi SIGKILL-proof: avval xotira holati + Turso DB
        (bardavom, restart'ga chidamli manba), keyin lokal fayl. Oracle VM'da
        servis shutdown timeout'da ``SIGKILL`` (status=9) bilan o'ladi —
        agar u fayl yozish o'rtasida kelsa, DB'da allaqachon yangi rotatsiya
        qilingan token bor va keyingi start uzilmaydi.
        """
        # 1. Xotira holati — darrov, hech qanday I/O kutmasdan.
        self.token_data = token_data
        self.access_token = token_data.get("access_token")
        self.auth_blocked_until = 0.0
        self.auth_block_reason = None

        # 2. Turso DB — fayldan OLDIN. Rotatsiya qilingan refresh_token
        #    shu yerda bo'lsa, SIGKILL fayl yozuvini uzsa ham zanjir tirik.
        self._persist_token_to_db()

        # 3. Lokal fayl (atomik replace) — bonus, tez local o'qish uchun.
        token_path = os.path.abspath(self.token_file)
        token_dir = os.path.dirname(token_path)
        temp_path = None
        try:
            os.makedirs(token_dir, mode=0o700, exist_ok=True)
            fd, temp_path = tempfile.mkstemp(prefix=".amocrm-token-", dir=token_dir)
            try:
                os.chmod(temp_path, 0o600)
                with os.fdopen(fd, "w", encoding="utf-8") as f:
                    json.dump(token_data, f, separators=(",", ":"))
                    f.flush()
                    os.fsync(f.fileno())
                os.replace(temp_path, token_path)
                temp_path = None
                os.chmod(token_path, 0o600)
            except Exception:
                try:
                    os.close(fd)
                except OSError:
                    pass
                raise
        except Exception as e:
            # DB'ga allaqachon yozilgan — fayl xatosi integratsiyani
            # o'ldirmaydi, faqat lokal keshni yangilay olmadik.
            self.last_error = "token_file_save_failed"
            logger.error("[AMOCRM] Token faylga saqlashda xato (DB baribir yangilandi): %s", type(e).__name__)
        finally:
            if temp_path:
                try:
                    os.unlink(temp_path)
                except OSError:
                    pass

    def _mark_auth_blocked(self, reason: str, seconds: int = 3600) -> None:
        self.auth_block_reason = reason
        self.auth_blocked_until = time.time() + seconds
        self.last_error = reason

    def is_auth_blocked(self) -> bool:
        if self.auth_blocked_until <= 0:
            return False
        if time.time() >= self.auth_blocked_until:
            self.auth_blocked_until = 0.0
            self.auth_block_reason = None
            return False
        self.last_error = self.auth_block_reason or "auth_blocked"
        return True

    def refresh_token(self):
        """Refresh token yordamida yangi access token olish.

        Sinmaydigan oqim ``refresh_guard`` orqali: cross-process lock ostida
        ishlaydi, HTTP 4xx da darrov bloklamasdan bardavom joydan yangiroq
        token izlaydi (parallel rotatsiya holati). Faqat hamma manba
        yaroqsiz bo'lсagina blok + owner alert.
        """
        if self.is_auth_blocked():
            return False

        if not self.token_data.get("refresh_token"):
            self._mark_auth_blocked("refresh_token_missing", seconds=900)
            logger.error("[AMOCRM] Refresh token topilmadi.")
            return False

        from src.services.core.crm.amocrm.refresh_guard import refresh_with_guard

        self._last_refresh_http_status = None
        ok = refresh_with_guard(
            do_refresh=self._do_http_refresh,
            reload_freshest=self._reload_freshest_token,
            apply_token=self._set_token_data,
        )
        if not ok:
            # Guard hamma manbani (HTTP + bardavom joy) yaroqsiz deb topdi —
            # endi haqiqatan owner qayta avtorizatsiya qilishi kerak.
            status = getattr(self, "_last_refresh_http_status", None) or "unknown"
            self._mark_auth_blocked(
                f"oauth_reauthorization_required_http_{status}", seconds=3600
            )
            logger.critical("[AMOCRM AUTH EXPIRED] Yangi authorization code kerak.")
        return ok

    def _do_http_refresh(self):
        """Haqiqiy ``grant_type=refresh_token`` HTTP so'rovi. Guard ичидан chaqiriladi."""
        url = f"{self.base_url}/oauth2/access_token"
        data = {
            "client_id": self.client_id,
            "client_secret": self.client_secret,
            "grant_type": "refresh_token",
            "refresh_token": self.token_data.get("refresh_token", ""),
            "redirect_uri": self.redirect_url,
        }

        try:
            response = requests.post(url, json=data, timeout=30)
            if response.status_code == 400:
                response = requests.post(url, data=data, timeout=30)

            if response.status_code == 200:
                resp_data = response.json()
                if "expires_in" in resp_data:
                    resp_data["expires_at"] = int(time.time()) + resp_data["expires_in"]
                self._save_token(resp_data)
                self.last_error = None
                logger.info("[AMOCRM OK] Access token refreshed successfully.")
                return True

            resp_json = {}
            try:
                resp_json = response.json()
            except Exception:
                logger.debug("[AMOCRM] Failed to parse JSON error response body", exc_info=True)

            error_msg = (
                resp_json.get("detail") or resp_json.get("title") or response.text
            )
            self.last_error = f"refresh_failed_http_{response.status_code}"
            logger.error(f"[AMOCRM ERROR] Token yangilashda xato: {error_msg}")
            # DIQQAT: 400/401 da BU YERDA bloklamaymiz. AmoCRM refresh_token'lari
            # rotatsiya qilinadi — 400 ko'pincha "boshqa instance allaqachon
            # yangiladi" degani. Blok qarorini refresh_guard beradi: u avval
            # bardavom joydan (Turso DB) yangiroq token izlaydi, faqat u ham
            # yaroqsiz bo'lсagina _mark_reauth_required() chaqiriladi.
            self._last_refresh_http_status = response.status_code
            return False
        except Exception as e:
            self.last_error = "refresh_request_failed"
            logger.error(f"[AMOCRM ERROR] Request yuborishda xato: {e}")
            return False

    def authorize_initial(self, auth_code):
        """Birinchi marta kod yordamida token olish."""
        url = f"{self.base_url}/oauth2/access_token"
        data = {
            "client_id": self.client_id,
            "client_secret": self.client_secret,
            "grant_type": "authorization_code",
            "code": auth_code,
            "redirect_uri": self.redirect_url,
        }

        try:
            response = requests.post(url, data=data, timeout=30)
            if response.status_code == 200:
                resp_data = response.json()
                if "expires_in" in resp_data:
                    resp_data["expires_at"] = int(time.time()) + resp_data["expires_in"]
                self._save_token(resp_data)
                logger.info("[AMOCRM OK] Dastlabki avtorizatsiya muvaffaqiyatli.")
                return True
            self.last_error = f"authorize_initial_http_{response.status_code}"
            logger.error("[AMOCRM ERROR] Initial authorization HTTP %s", response.status_code)
            return False
        except Exception as e:
            if not self.last_error:
                self.last_error = "authorize_initial_request_failed"
            logger.error("[AMOCRM ERROR] Initial authorization failed: %s", type(e).__name__)
            return False

    async def get_account_status(self):
        """Akkaunt limitlarini tekshirish."""
        url = f"{self.base_url}/api/v4/account"
        resp = requests.get(url, headers=self._get_headers(), timeout=30)
        if resp.status_code == 200:
            return resp.json()
        return None

    async def check_connection(self) -> bool:
        """AmoCRM OAuth tokenini real account endpoint orqali tekshiradi."""
        return await asyncio.to_thread(self._check_connection_sync)

    def _check_connection_sync(self) -> bool:
        """Blocking AmoCRM account probe; keep it off the asyncio event loop."""
        if self.is_auth_blocked():
            return False

        if not self.access_token:
            self._load_token()

        if not self.access_token:
            self.last_error = "access_token_missing"
            return False

        url = f"{self.base_url}/api/v4/account"
        try:
            response = requests.get(url, headers=self._get_headers(), timeout=15)
            if response.status_code == 200:
                self.last_error = None
                return True

            if response.status_code == 401 and self.refresh_token():
                response = requests.get(url, headers=self._get_headers(), timeout=15)
                if response.status_code == 200:
                    self.last_error = None
                    return True

            self.last_error = f"check_connection_http_{response.status_code}"
            return False
        except Exception as e:
            self.last_error = "check_connection_exception"
            logger.error(f"[AMOCRM CHECK ERROR] {type(e).__name__}")
            return False

    def _get_headers(self):
        """API so'rovlari uchun headerlarni tayyorlash va token muddatini tekshirish."""
        if self.is_auth_blocked():
            return {"Authorization": "Bearer ", "Content-Type": "application/json"}

        # 1. Token muddatini tekshirish
        expires_at = self.token_data.get("expires_at")
        now = int(time.time())
        
        # Agar token yo'q yoki muddati tugayotgan bo'lsa (60 soniya qolganida)
        needs_refresh = False
        if not self.access_token:
            needs_refresh = True
        elif expires_at and now > int(expires_at) - 60:
            needs_refresh = True
            
        if needs_refresh and self.token_data.get("refresh_token"):
            logger.info("[AMOCRM] Token expired or missing, refreshing...")
            self.refresh_token()

        token = str(self.access_token or "")
        if not token:
            logger.warning("[AMOCRM] Access token is missing, requests will likely fail.")
            
        return {"Authorization": f"Bearer {token}", "Content-Type": "application/json"}

    async def _request_with_auth(self, request_fn, url: str, **kwargs):
        """Run blocking requests calls outside the shared Telegram/API event loop."""
        def _send():
            return request_fn(url, headers=self._get_headers(), **kwargs)

        return await asyncio.to_thread(_send)
