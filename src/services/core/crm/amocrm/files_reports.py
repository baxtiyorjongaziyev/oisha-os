import asyncio
import os
import time
import json
import logging
import requests  # type: ignore
from typing import Optional, Dict, Any, List
from functools import wraps

import structlog

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



class AmoCRMFilesReportsMixin:
    def download_file(self, file_uuid: str) -> Optional[bytes]:
        """AmoCRM dan faylni yuklab olish."""
        self._load_token()
        # AmoCRM Files API orqali faylni olish
        url = f"{self.base_url}/api/v4/files/{file_uuid}"
        headers = self._get_headers()

        try:
            # 1. Metadatasini olish (download link uchun)
            resp = requests.get(url, headers=headers, timeout=30)
            if resp.status_code == 200:
                file_data = resp.json()
                download_url = file_data.get("download_url")

                if download_url:
                    # 2. Haqiqiy faylni yuklab olish
                    file_resp = requests.get(download_url, headers=headers, timeout=30)
                    if file_resp.status_code == 200:
                        return file_resp.content

            logger.error(f"[AMOCRM DOWNLOAD ERROR] {resp.status_code}: {resp.text}")
            return None
        except Exception as e:
            logger.error(f"[AMOCRM DOWNLOAD EXCEPTION] {e}")
            return None

    def download_file_from_url(self, url: str) -> Optional[bytes]:
        """URL orqali faylni yuklab olish (audio, hujjat va h.k.)."""
        self._load_token()
        try:
            resp = requests.get(url, headers=self._get_headers(), timeout=60)
            if resp.status_code == 200:
                return resp.content
            resp_no_auth = requests.get(url, timeout=60)
            if resp_no_auth.status_code == 200:
                return resp_no_auth.content
            logger.error(f"[AMOCRM DOWNLOAD URL] {resp.status_code}: {url}")
            return None
        except Exception as e:
            logger.error(f"[AMOCRM DOWNLOAD URL EXCEPTION] {e}")
            return None

    def get_sales_report(self) -> Dict[str, Any]:
        """Oylik sotuv hisobotini (Plan-Fakt) shakllantirish."""
        self._load_token()
        # Won (Muvaffaqiyatli) statusidagi bitimlarni olish
        # Odatda 142 status - bu Success (Won)
        from datetime import datetime, date

        first_day = datetime.combine(date.today().replace(day=1), datetime.min.time())
        timestamp_from = int(first_day.timestamp())

        url = f"{self.base_url}/api/v4/leads"
        params = {
            "filter[status][0]": 142,  # 142 - muvaffaqiyatli bitim
            "filter[closed_at][from]": timestamp_from,
        }

        try:
            response = requests.get(url, headers=self._get_headers(), params=params, timeout=30)
            total_sum = 0
            count = 0
            if response.status_code == 200:
                leads = response.json().get("_embedded", {}).get("leads", [])
                for lead in leads:
                    total_sum += lead.get("price", 0)
                    count += 1

            target = 80000000  # 80 mln so'm target
            return {
                "fact": total_sum,
                "target": target,
                "count": count,
                "percent": (total_sum / target * 100) if target > 0 else 0,
            }
        except Exception as e:
            logger.error(f"[AMOCRM REPORT ERROR] {e}")
            return {"fact": 0, "target": 80000000, "count": 0, "percent": 0}

    def _dummy_placeholder(self):
        # Removing old redundant implementation of get_contact_by_phone as it's now enhanced above
        pass
