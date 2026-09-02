"""
Constants, helpers, and keys for CRM note approval.
"""
from typing import Any

MOOD_EMOJI = {
    "Ijobiy": "😊",
    "Neytral": "😐",
    "Salbiy": "😟",
    "Noaniq": "🤔",
}

CATEGORY_EMOJI = {
    "Mijoz": "🤝",
    "Jamoa": "👥",
    "Shaxsiy": "👤",
    "Oila": "🏠",
    "Boshqa": "📌",
}


def _safe_call_id(call_id: str, lead_id: int) -> str:
    longest_prefix = "crm_approve"
    max_id_len = 64 - len(longest_prefix) - len(str(lead_id)) - 2
    return call_id[:max_id_len]


def _approval_key(lead_id: int, call_id: str) -> str:
    return f"crm_approve:{lead_id}:{_safe_call_id(call_id, lead_id)}"


def _edit_key(lead_id: int, call_id: str) -> str:
    return f"crm_edit:{lead_id}:{_safe_call_id(call_id, lead_id)}"


def _h(text: Any) -> str:
    return str(text).replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
