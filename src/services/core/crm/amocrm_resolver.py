"""
AmoCRM Dynamic Pipeline & Custom Field Resolver.
Auto-discovers pipelines, stages, and custom fields from amoCRM API,
caching them with TTL and falling back safely to static config.
"""

from __future__ import annotations

import asyncio
import logging
import time
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Union

import requests

from src.services.core.crm.amocrm_pipeline_config import (
    FARMER_PIPELINE_ID,
    REACTIVATION_PIPELINE_ID,
    SALES_PIPELINE_ID,
    STATUS_LOST,
    STATUS_WON,
)

logger = logging.getLogger("AmoPipelineResolver")


def _norm(text: str) -> str:
    """Normalize text for case- and whitespace-insensitive matching."""
    return "".join(c for c in text.lower().strip() if c.isalnum() or c in " _-")


@dataclass(frozen=True)
class StatusMeta:
    id: int
    name: str
    sort: int
    pipeline_id: int


@dataclass
class PipelineMeta:
    id: int
    name: str
    is_main: bool
    is_archive: bool
    statuses: Dict[int, StatusMeta] = field(default_factory=dict)
    status_by_name: Dict[str, StatusMeta] = field(default_factory=dict)


@dataclass(frozen=True)
class CustomFieldMeta:
    id: int
    name: str
    field_type: str
    enums: Dict[str, int] = field(default_factory=dict)


class AmoPipelineResolver:
    """Dynamic auto-discovery registry for amoCRM pipelines and custom fields."""

    _instance: Optional["AmoPipelineResolver"] = None

    def __init__(self, amocrm: Any = None, ttl_seconds: int = 3600) -> None:
        self.amocrm = amocrm
        self.ttl_seconds = ttl_seconds
        self._last_loaded_at: float = 0.0
        self._pipelines: Dict[int, PipelineMeta] = {}
        self._pipeline_by_name: Dict[str, PipelineMeta] = {}
        self._custom_fields: Dict[int, CustomFieldMeta] = {}
        self._custom_field_by_name: Dict[str, CustomFieldMeta] = {}

    @classmethod
    def get_instance(cls, amocrm: Any = None) -> "AmoPipelineResolver":
        if cls._instance is None:
            cls._instance = cls(amocrm=amocrm)
        elif amocrm is not None and cls._instance.amocrm is None:
            cls._instance.amocrm = amocrm
        return cls._instance

    def is_cache_valid(self) -> bool:
        if not self._pipelines:
            return False
        return (time.time() - self._last_loaded_at) < self.ttl_seconds

    def load_sync(self, force: bool = False) -> bool:
        """Synchronously load pipelines and custom fields from amoCRM API."""
        if not force and self.is_cache_valid():
            return True

        amo = self._ensure_amocrm()
        if not amo:
            logger.warning("[AmoResolver] amoCRM instance not available; using static fallback")
            self._apply_static_fallbacks()
            return False

        try:
            amo._load_token()
            headers = amo._get_headers()
            p_ok = self._load_pipelines(amo.base_url, headers)
            f_ok = self._load_custom_fields(amo.base_url, headers)
            if p_ok or f_ok:
                self._last_loaded_at = time.time()
                logger.info(
                    "[AmoResolver] Discovered %d pipelines and %d custom fields",
                    len(self._pipelines),
                    len(self._custom_fields),
                )
                return True
        except Exception as exc:
            logger.error("[AmoResolver] Failed to discover from amoCRM API: %s", exc)

        self._apply_static_fallbacks()
        return False

    async def load_async(self, force: bool = False) -> bool:
        """Asynchronously load pipelines and custom fields."""
        return await asyncio.to_thread(self.load_sync, force)

    def _ensure_amocrm(self) -> Any:
        if self.amocrm is not None:
            return self.amocrm
        try:
            from src.services.core.crm.amocrm_sync import AmoCRMSync

            self.amocrm = AmoCRMSync()
            return self.amocrm
        except Exception:
            return None

    def _load_pipelines(self, base_url: str, headers: Dict[str, str]) -> bool:
        url = f"{base_url}/api/v4/leads/pipelines"
        resp = requests.get(url, headers=headers, timeout=20)
        if resp.status_code != 200:
            logger.warning("[AmoResolver] GET pipelines returned HTTP %s", resp.status_code)
            return False

        payload = resp.json().get("_embedded", {}).get("pipelines", []) or []
        self._pipelines.clear()
        self._pipeline_by_name.clear()

        for p in payload:
            p_id = int(p.get("id"))
            p_name = str(p.get("name", "")).strip()
            is_main = bool(p.get("is_main", False))
            is_archive = bool(p.get("is_archive", False))
            meta = PipelineMeta(id=p_id, name=p_name, is_main=is_main, is_archive=is_archive)

            raw_statuses = p.get("_embedded", {}).get("statuses", []) or []
            for s in raw_statuses:
                s_id = int(s.get("id"))
                s_name = str(s.get("name", "")).strip()
                s_sort = int(s.get("sort", 0))
                smeta = StatusMeta(id=s_id, name=s_name, sort=s_sort, pipeline_id=p_id)
                meta.statuses[s_id] = smeta
                meta.status_by_name[_norm(s_name)] = smeta

            self._pipelines[p_id] = meta
            self._pipeline_by_name[_norm(p_name)] = meta
            if is_main:
                self._pipeline_by_name["main"] = meta
                self._pipeline_by_name["default"] = meta
                self._pipeline_by_name["sotuv"] = meta

        return len(self._pipelines) > 0

    def _load_custom_fields(self, base_url: str, headers: Dict[str, str]) -> bool:
        url = f"{base_url}/api/v4/leads/custom_fields"
        resp = requests.get(url, headers=headers, timeout=20)
        if resp.status_code != 200:
            return False

        payload = resp.json().get("_embedded", {}).get("custom_fields", []) or []
        self._custom_fields.clear()
        self._custom_field_by_name.clear()

        for f in payload:
            f_id = int(f.get("id"))
            f_name = str(f.get("name", "")).strip()
            f_type = str(f.get("type", "text"))
            enums = {}
            for e in f.get("enums", []) or []:
                val = str(e.get("value", "")).strip()
                enums[_norm(val)] = int(e.get("id"))

            cf_meta = CustomFieldMeta(id=f_id, name=f_name, field_type=f_type, enums=enums)
            self._custom_fields[f_id] = cf_meta
            self._custom_field_by_name[_norm(f_name)] = cf_meta

        return len(self._custom_fields) > 0

    def _apply_static_fallbacks(self) -> None:
        """Seed known static IDs when remote is unavailable."""
        if not self._pipelines:
            sotuv = PipelineMeta(id=SALES_PIPELINE_ID, name="Sotuv Boʻlimi", is_main=True, is_archive=False)
            self._pipelines[SALES_PIPELINE_ID] = sotuv
            self._pipeline_by_name["sotuv"] = sotuv
            self._pipeline_by_name["main"] = sotuv
            self._pipeline_by_name["default"] = sotuv
            farmer = PipelineMeta(id=FARMER_PIPELINE_ID, name="Farmer", is_main=False, is_archive=False)
            self._pipelines[FARMER_PIPELINE_ID] = farmer
            self._pipeline_by_name["farmer"] = farmer
            react = PipelineMeta(id=REACTIVATION_PIPELINE_ID, name="Reactivation", is_main=False, is_archive=False)
            self._pipelines[REACTIVATION_PIPELINE_ID] = react
            self._pipeline_by_name["reactivation"] = react

    def get_pipeline(self, identifier: Union[int, str]) -> Optional[PipelineMeta]:
        if isinstance(identifier, int):
            return self._pipelines.get(identifier)
        return self._pipeline_by_name.get(_norm(identifier))

    def get_pipeline_id(self, name_or_alias: str) -> Optional[int]:
        pipe = self.get_pipeline(name_or_alias)
        return pipe.id if pipe else None

    def get_status_id(self, pipeline: Union[int, str], status_name: str) -> Optional[int]:
        """Resolve a status ID within a pipeline by name or alias."""
        norm_s = _norm(status_name)
        if norm_s in {"won", "yutildi", "sotuvboldi", "uspeshno"}:
            return STATUS_WON
        if norm_s in {"lost", "yopildi", "bekorqilindi", "otkaz"}:
            return STATUS_LOST

        pipe = self.get_pipeline(pipeline)
        if not pipe:
            return None

        if norm_s in pipe.status_by_name:
            return pipe.status_by_name[norm_s].id

        for s_key, s_meta in pipe.status_by_name.items():
            if norm_s in s_key or s_key in norm_s:
                return s_meta.id

        return None

    def get_custom_field_id(self, field_name: str) -> Optional[int]:
        """Resolve custom field ID by name."""
        norm_f = _norm(field_name)
        if norm_f in self._custom_field_by_name:
            return self._custom_field_by_name[norm_f].id
        for f_key, f_meta in self._custom_field_by_name.items():
            if norm_f in f_key or f_key in norm_f:
                return f_meta.id
        return None

    def get_custom_field_enum_id(self, field_name: str, enum_value: str) -> Optional[int]:
        """Resolve enum ID for select/multiselect fields."""
        f_id = self.get_custom_field_id(field_name)
        if not f_id or f_id not in self._custom_fields:
            return None
        cf = self._custom_fields[f_id]
        norm_e = _norm(enum_value)
        if norm_e in cf.enums:
            return cf.enums[norm_e]
        for e_key, e_id in cf.enums.items():
            if norm_e in e_key or e_key in norm_e:
                return e_id
        return None

    def summary(self) -> Dict[str, Any]:
        """Return safe diagnostic summary of cached pipelines and custom fields."""
        return {
            "is_cached": self.is_cache_valid(),
            "total_pipelines": len(self._pipelines),
            "pipelines": [
                {
                    "id": p.id,
                    "name": p.name,
                    "is_main": p.is_main,
                    "statuses_count": len(p.statuses),
                }
                for p in self._pipelines.values()
            ],
            "total_custom_fields": len(self._custom_fields),
            "custom_fields": [
                {"id": f.id, "name": f.name, "type": f.field_type}
                for f in self._custom_fields.values()
            ],
        }
