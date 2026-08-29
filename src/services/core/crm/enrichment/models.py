"""
Data models and helper functions for AmoCRM lead enrichment.
"""
from __future__ import annotations

import inspect
import json
import logging
import re
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from typing import Any, Dict, List, Mapping, Optional, Sequence

logger = logging.getLogger("AmoCRMLeadEnrichment")

def normalize_phone(phone: Optional[str]) -> str:
    """Normalize UZ/common phone strings to +<digits> for matching."""
    digits = re.sub(r"\D", "", phone or "")
    if not digits:
        return ""
    if digits.startswith("00"):
        digits = digits[2:]
    if len(digits) == 9:
        digits = "998" + digits
    return f"+{digits}"


async def maybe_await(value: Any) -> Any:
    if inspect.isawaitable(value):
        return await value
    return value


def _secret_to_text(value: Any) -> str:
    if value is None:
        return ""
    getter = getattr(value, "get_secret_value", None)
    if callable(getter):
        value = getter()
    return str(value or "").strip()


def _clip(text: str, limit: int) -> str:
    text = (text or "").strip()
    if len(text) <= limit:
        return text
    return text[: max(0, limit - 3)].rstrip() + "..."


def _extract_text_from_history_item(item: Dict[str, Any]) -> str:
    if "parts" in item:
        parts = item.get("parts") or []
        if parts and isinstance(parts[0], dict):
            return str(parts[0].get("text") or "").strip()
    return str(
        item.get("message_text")
        or item.get("text")
        or item.get("message")
        or ""
    ).strip()


def _extract_role_from_history_item(item: Dict[str, Any]) -> str:
    role = str(item.get("role") or "").lower()
    if role == "model":
        return "Oisha"
    if role == "assistant":
        return "Oisha"
    if item.get("is_ai") or item.get("is_ai_reply"):
        return "Oisha"
    return "Mijoz"


@dataclass
class LeadEnrichmentResult:
    status: str
    lead_id: int
    phone: str = ""
    telegram_user_id: Optional[int] = None
    note_added: bool = False
    reason: Optional[str] = None
    tags_added: List[str] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "status": self.status,
            "lead_id": self.lead_id,
            "phone": self.phone,
            "telegram_user_id": self.telegram_user_id,
            "note_added": self.note_added,
            "reason": self.reason,
            "tags_added": list(self.tags_added),
        }
