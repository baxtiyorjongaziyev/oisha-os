"""
AirtableSync main client class composed of modular mixins.
"""
from __future__ import annotations

import json
import logging
import os
import time
from typing import Any, Dict, List, Optional

from src.settings import settings
from src.services.core.airtable.constants import (
    BILLING_COOLDOWN_SECONDS,
    DONE_STAGES,
    FIELD_MAP,
    PROJECT_ALLOWED_FIELDS,
    PROJECT_WRITE_ALIASES,
    READ_RETRIES,
    REQUEST_TIMEOUT_SECONDS,
)
from src.services.core.airtable.oauth import AirtableOAuth
from src.services.core.airtable.pm_resolver import PMResolverMixin
from src.services.core.airtable.client_base import ClientBaseMixin
from src.services.core.airtable.projects import ProjectsMixin

logger = logging.getLogger("AirtableSync")


class AirtableSync(PMResolverMixin, ClientBaseMixin, ProjectsMixin):
    """
    Airtable sinxronizatsiya xizmati (OAuth va PAT qo'llab-quvvatlaydi).
    """

    BILLING_LIMIT_STATUS_CODE = 402
    BILLING_LIMIT_ERROR_TYPE = "PAYMENT_REQUIRED"

    READ_RETRIES = READ_RETRIES
    REQUEST_TIMEOUT_SECONDS = REQUEST_TIMEOUT_SECONDS
    BILLING_COOLDOWN_SECONDS = BILLING_COOLDOWN_SECONDS
    FIELD_MAP = FIELD_MAP
    PROJECT_WRITE_ALIASES = PROJECT_WRITE_ALIASES
    PROJECT_ALLOWED_FIELDS = PROJECT_ALLOWED_FIELDS
    DONE_STAGES = DONE_STAGES

    _base_tables_cache = {}
    _record_url_cache = {}
    _records_cache = {}
    _billing_blocked_until = 0.0
    _billing_block_reason = None

    def __init__(self, api_key=None, base_id=None, table_name="Loyihalar"):
        configured_key = getattr(settings, "AIRTABLE_API_KEY", None)
        self.api_key = api_key or (
            configured_key.get_secret_value() if hasattr(configured_key, "get_secret_value") else str(configured_key or "")
        )
        self.base_id = base_id or getattr(settings, "AIRTABLE_BASE_ID", None)
        self.table_name = table_name
        self.transactions_table = (
            getattr(settings, "AIRTABLE_TRANSACTIONS_TABLE", "Transactions")
            or os.getenv("AIRTABLE_TRANSACTIONS_TABLE", "Transactions")
        )
        self.endpoint = self._table_url()
        self.read_cache_ttl_seconds = int(
            os.getenv("AIRTABLE_READ_CACHE_TTL_SECONDS", "600")
        )

        def _secret(v):
            return v.get_secret_value() if hasattr(v, "get_secret_value") else str(v or "")

        self.oauth = AirtableOAuth(
            client_id=getattr(settings, "AIRTABLE_OAUTH_CLIENT_ID", "") or "",
            client_secret=_secret(getattr(settings, "AIRTABLE_OAUTH_CLIENT_SECRET", None)),
            access_token=_secret(getattr(settings, "AIRTABLE_ACCESS_TOKEN", None)),
            refresh_token=_secret(getattr(settings, "AIRTABLE_REFRESH_TOKEN", None)),
        )
        self.headers = {
            "Authorization": f"Bearer {self._current_bearer()}",
            "Content-Type": "application/json",
        }
        self.base_url = "https://api.airtable.com/v0"
        self._rate_limit_lock = False
        self._last_request_time = 0.0
        self._min_interval = 0.22
        self._records_cache: Dict[str, Any] = {}
        self._cache_ttl = 60.0
        self._base_schema_cache: Dict[str, Any] = {}
        self._base_schema_cache_ttl = 300.0
        self._disk_cache_dir = os.path.join("data", "airtable_cache")
        os.makedirs(self._disk_cache_dir, exist_ok=True)
