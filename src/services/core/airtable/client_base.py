"""
Airtable HTTP client, disk caching, rate limiting, and table metadata mixin.
"""
from __future__ import annotations

import json
import logging
import os
import time
from copy import deepcopy
from datetime import datetime
from urllib.parse import quote
import requests

logger = logging.getLogger("AirtableSync")


class ClientBaseMixin:
    """Handles HTTP requests, OAuth bearer reauth, and caching for Airtable."""

    def _current_bearer(self) -> str:
        """OAuth token sozlangan bo'lsa uni, aks holda API key (PAT) qaytaradi."""
        if getattr(self, "oauth", None) and self.oauth.configured and self.oauth.bearer():
            return self.oauth.bearer()
        return self.api_key

    def _reauth_with_oauth(self) -> bool:
        """401 kelganda OAuth tokenni yangilaydi va headerni yangilaydi."""
        if not (getattr(self, "oauth", None) and self.oauth.configured):
            return False
        if self.oauth.refresh():
            self.headers["Authorization"] = f"Bearer {self._current_bearer()}"
            return True
        return False

    def _table_url(self, table_name=None):
        table = quote(str(table_name or self.table_name), safe="")
        return f"https://api.airtable.com/v0/{self.base_id}/{table}"

    def _refresh_endpoint(self):
        self.endpoint = self._table_url()

    def _records_cache_key(self):
        return (self.base_id, self.table_name)

    def _disk_cache_path(self):
        safe_table = "".join(
            char if char.isalnum() or char in "-_" else "_"
            for char in str(self.table_name)
        )
        return os.path.join("data", "cache", f"airtable_{self.base_id}_{safe_table}.json")

    def _get_disk_cached_records(self):
        path = self._disk_cache_path()
        try:
            with open(path, "r", encoding="utf-8") as cache_file:
                payload = json.load(cache_file)
            records = payload.get("records")
            if isinstance(records, list):
                logger.warning(
                    "[AIRTABLE CACHE] Using persistent stale snapshot for %s: %s records",
                    self.table_name,
                    len(records),
                )
                return records
        except (OSError, ValueError, TypeError):
            pass
        return None

    def _get_cached_records(self):
        if self.read_cache_ttl_seconds <= 0:
            return None
        cached = self._records_cache.get(self._records_cache_key())
        if not cached:
            return None
        created_at, records = cached
        if time.time() - created_at > self.read_cache_ttl_seconds:
            self._records_cache.pop(self._records_cache_key(), None)
            return None
        return deepcopy(records)

    def _set_cached_records(self, records):
        if self.read_cache_ttl_seconds <= 0:
            return
        self._records_cache[self._records_cache_key()] = (time.time(), deepcopy(records))
        path = self._disk_cache_path()
        try:
            os.makedirs(os.path.dirname(path), exist_ok=True)
            with open(path, "w", encoding="utf-8") as cache_file:
                json.dump(
                    {"cached_at": datetime.now().isoformat(), "records": records},
                    cache_file,
                    ensure_ascii=False,
                )
        except OSError as exc:
            logger.warning("[AIRTABLE CACHE] Persistent cache write failed: %s", exc)

    def _invalidate_records_cache(self):
        self._records_cache.pop(self._records_cache_key(), None)

    @classmethod
    def _billing_limit_response(cls):
        response = requests.Response()
        response.status_code = 429
        response.headers["X-Oisha-Airtable-Cooldown"] = "active"
        response._content = json.dumps(
            {
                "errors": [
                    {
                        "error": cls._billing_block_reason
                        or "PUBLIC_API_BILLING_LIMIT_EXCEEDED",
                        "message": "Airtable API billing limit cooldown is active.",
                    }
                ]
            }
        ).encode("utf-8")
        return response

    @staticmethod
    def _is_billing_limit_response(response) -> bool:
        if response.status_code != 429:
            return False
        return "PUBLIC_API_BILLING_LIMIT_EXCEEDED" in (response.text or "")

    def _request(self, method: str, url: str, *, retry: bool = True, **kwargs):
        cls = type(self)
        if time.time() < cls._billing_blocked_until:
            return cls._billing_limit_response()

        attempts = self.READ_RETRIES if retry and method.upper() == "GET" else 1
        last_exc = None
        oauth_retried = False

        for attempt in range(1, attempts + 1):
            try:
                request_kwargs = dict(kwargs)
                request_kwargs.setdefault("headers", self.headers)
                request_kwargs.setdefault("timeout", self.REQUEST_TIMEOUT_SECONDS)
                response = requests.request(method, url, **request_kwargs)

                # [OAUTH] Access token muddati tugagan bo'lsa — bir marta refresh + retry
                if (
                    response.status_code == 401
                    and not oauth_retried
                    and self._reauth_with_oauth()
                ):
                    oauth_retried = True
                    request_kwargs["headers"] = self.headers
                    response = requests.request(method, url, **request_kwargs)

                if self._is_billing_limit_response(response):
                    cls._billing_block_reason = "PUBLIC_API_BILLING_LIMIT_EXCEEDED"
                    cls._billing_blocked_until = (
                        time.time() + cls.BILLING_COOLDOWN_SECONDS
                    )
                    logger.error(
                        "[AIRTABLE] Monthly API billing limit exceeded; "
                        "requests paused for the configured cooldown.",
                    )
                    return response

                if (
                    response.status_code in {429, 500, 502, 503, 504}
                    and attempt < attempts
                ):
                    retry_after = response.headers.get("Retry-After")
                    delay = (
                        float(retry_after)
                        if retry_after and retry_after.isdigit()
                        else attempt * 1.5
                    )
                    logger.warning(
                        f"[AIRTABLE] Transient {response.status_code}, retry {attempt}/{attempts} in {delay:.1f}s"
                    )
                    time.sleep(delay)
                    continue

                return response
            except requests.RequestException as exc:
                last_exc = exc
                if attempt >= attempts:
                    raise
                delay = attempt * 1.5
                logger.warning(
                    f"[AIRTABLE] Network error, retry {attempt}/{attempts} in {delay:.1f}s: {exc}"
                )
                time.sleep(delay)

        if last_exc:
            raise last_exc
        raise RuntimeError("Airtable request failed without a response")

    def _get_base_tables(self):
        cache_key = self.base_id
        cached = self._base_tables_cache.get(cache_key)
        if cached is not None:
            return cached

        meta_url = f"https://api.airtable.com/v0/meta/bases/{self.base_id}/tables"
        try:
            response = self._request("GET", meta_url)
            if response.status_code != 200:
                logger.warning(
                    f"[AIRTABLE] Jadval metadata olib bo'lmadi: {response.status_code}"
                )
                self._base_tables_cache[cache_key] = []
                return []

            tables = []
            for table in response.json().get("tables", []):
                views = table.get("views") or []
                view_id = None
                for view in views:
                    if view.get("type") == "grid":
                        view_id = view.get("id")
                        break
                if not view_id and views:
                    view_id = views[0].get("id")

                tables.append(
                    {
                        "id": table.get("id"),
                        "name": table.get("name"),
                        "view_id": view_id,
                    }
                )

            self._base_tables_cache[cache_key] = tables
            return tables
        except Exception as exc:
            logger.warning(f"[AIRTABLE] Jadval metadata xatosi: {exc}")
            self._base_tables_cache[cache_key] = []
            return []

    def get_record_url(self, record_id: str):
        record_id = str(record_id or "").strip()
        if not record_id.startswith("rec"):
            return None

        cache_key = (self.base_id, record_id)
        cached = self._record_url_cache.get(cache_key)
        if cached is not None:
            return cached

        tables = self._get_base_tables()
        if not tables:
            self._record_url_cache[cache_key] = None
            return None

        ordered_tables = sorted(
            tables,
            key=lambda table: (
                table.get("name") != self.table_name
                and table.get("id") != self.table_name
            ),
        )

        for table in ordered_tables:
            table_id = table.get("id")
            if not table_id:
                continue

            probe_url = (
                f"https://api.airtable.com/v0/{self.base_id}/{table_id}/{record_id}"
            )
            try:
                response = self._request("GET", probe_url)
            except Exception:
                logger.error("Exception handled in %s", __name__, exc_info=True)
                continue

            if response.status_code == 200:
                view_id = table.get("view_id")
                if view_id:
                    record_url = f"https://airtable.com/{self.base_id}/{table_id}/{view_id}/{record_id}"
                else:
                    record_url = (
                        f"https://airtable.com/{self.base_id}/{table_id}/{record_id}"
                    )
                self._record_url_cache[cache_key] = record_url
                return record_url

            if response.status_code in {404, 422}:
                continue

            if response.status_code == 403:
                logger.warning("[AIRTABLE] Record URL probe uchun ruxsat yetarli emas.")
                break

        self._record_url_cache[cache_key] = None
        return None

    def _normalize_fields_for_table(self, fields: dict) -> dict:
        """Translate legacy field names to the actual Airtable schema and drop unknown keys."""
        normalized = dict(fields or {})
        if self.table_name != "Loyihalar":
            return normalized

        translated = {}
        dropped_originals = []
        for key, value in normalized.items():
            actual_key = self.PROJECT_WRITE_ALIASES.get(key, key)
            if actual_key in {
                "Client Phone",
                "AmoCRM_ID",
                "Manager",
                "PM",
                "Mijoz nomi",
                "Loyiha ID",
            }:
                dropped_originals.append(key)
                continue
            if actual_key in self.PROJECT_ALLOWED_FIELDS:
                translated[actual_key] = value
            else:
                dropped_originals.append(key)

        if dropped_originals:
            dropped = ", ".join(sorted(set(dropped_originals)))
            logger.warning(
                f"[AIRTABLE] Skipping unsupported Loyihalar fields: {dropped}"
            )
        return translated
