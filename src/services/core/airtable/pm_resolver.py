"""
Project Manager (PM) and team member name/handle resolver mixin.
"""
from __future__ import annotations

import ast
import logging
import re
from typing import Any, Dict, List, Optional
from src.services.core.airtable.constants import FIELD_MAP

logger = logging.getLogger("AirtableSync")

_PM_NAME_DATA: Dict[str, Dict[str, str]] = {
    "recoKLD3kbbVnDW2s": {"name": "Inomjon Ibrohimjonov", "role": "PM", "handle": "@Inomjon_JonBranding"},
    "recPi9SROzJNK8SX7": {"name": "Hasanboy Gaziyev", "role": "PM", "handle": "@jonbranding_pm"},
    "recl47X6x0IQpPyuf": {"name": "Dilorom", "role": "PM", "handle": "@jonbranding_pm"},
    "reccXjZIGIcRezKgB": {"name": "Baxtiyorjon Gaziyev", "role": "Owner", "handle": "@Baxtiyorjon_Gaziyev"},
    "recQr0v0WoemFL2j4": {"name": "Feruzbek Norchayev", "role": "Dizayner", "handle": "@feruzbek207"},
}

_NAME_TO_HANDLE: Dict[str, str] = {
    "inomjon": "@Inomjon_JonBranding",
    "inomjon ibrohimjonov": "@Inomjon_JonBranding",
    "inomjon aka": "@Inomjon_JonBranding",
    "hasanboy": "@jonbranding_pm",
    "hasanboy gaziyev": "@jonbranding_pm",
    "dilorom": "@jonbranding_pm",
    "dilorom opa": "@jonbranding_pm",
    "baxtiyorjon": "@Baxtiyorjon_Gaziyev",
    "baxtiyorjon gaziyev": "@Baxtiyorjon_Gaziyev",
    "feruzbek": "@feruzbek207",
    "feruzbek norchayev": "@feruzbek207",
}


def _extract_items(val: Any) -> List[str]:
    if not val:
        return []
    if isinstance(val, list):
        items = []
        for item in val:
            items.extend(_extract_items(item))
        return [str(i).strip() for i in items if i]
    text = str(val).strip()
    if text.startswith("[") and text.endswith("]"):
        try:
            parsed = ast.literal_eval(text)
            return _extract_items(parsed)
        except Exception:
            pass
    parts = re.split(r"[,;]\s*", text)
    return [p.strip() for p in parts if p.strip()]


class PMResolverMixin:
    """Handles parsing and normalizing PM names and handles from Airtable fields."""

    @staticmethod
    def _get_field(fields: dict, key: str, default=None):
        """Get field value by trying multiple possible field names."""
        for name in FIELD_MAP.get(key, [key]):
            val = fields.get(name)
            if val is not None:
                return val
        return default

    @classmethod
    def resolve_pm_name(cls, pm_value: Any, include_role: bool = False) -> str:
        """
        Maps Airtable PM field values (names or Record IDs) to display names.
        """
        if not pm_value:
            return "Mas'ul belgilanmagan"

        items = _extract_items(pm_value)
        if not items:
            return "Mas'ul belgilanmagan"

        results = []
        for item in items:
            clean = str(item).strip().strip("'\"")
            if clean in _PM_NAME_DATA:
                info = _PM_NAME_DATA[clean]
                if include_role and info.get("role"):
                    results.append(f"{info['name']} ({info['role']})")
                else:
                    results.append(info["name"])
            else:
                results.append(clean)

        return ", ".join(results) if results else "Mas'ul belgilanmagan"

    @classmethod
    def resolve_pm_handle(cls, pm_value: Any) -> str:
        """
        Maps Airtable PM field values (names or Record IDs) to Telegram handles.
        """
        if not pm_value:
            return "@Inomjon_JonBranding"

        items = _extract_items(pm_value)
        if not items:
            return "@Inomjon_JonBranding"

        results = []
        for item in items:
            clean = str(item).strip().strip("'\"")
            if clean in _PM_NAME_DATA:
                results.append(_PM_NAME_DATA[clean]["handle"])
            elif clean.lower() in _NAME_TO_HANDLE:
                results.append(_NAME_TO_HANDLE[clean.lower()])
            elif clean.startswith("@"):
                results.append(clean)
            else:
                results.append(f"@{clean}")

        return ", ".join(results) if results else "@Inomjon_JonBranding"
