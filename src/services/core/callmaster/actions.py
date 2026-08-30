"""
Action builders for Callmaster events.
"""
from __future__ import annotations

from typing import Any, Dict, Optional
from src.services.core.callmaster.models import _safe_int


def build_oisha_action(
    payload: Dict[str, Any],
    *,
    contact: Optional[Dict[str, Any]],
    attempt: Optional[Dict[str, Any]],
) -> Dict[str, Any]:
    digit = str(payload.get("digit") or payload.get("dtmf") or "").strip()
    lead_id = _safe_int(payload.get("lead_id") or (contact or {}).get("lead_id"))
    phone = str(payload.get("phone") or (contact or {}).get("phone") or "").strip()
    if digit != "1":
        return {"type": "none", "reason": "no_operator_request"}

    text = (
        "Avto-qo'ng'iroqda mijoz 1 ni bosdi. Operator bog'lanishi kerak. "
        f"Telefon: {phone or 'noma-lum'}."
    )
    task_text = "Oisha Callmaster: 1 ni bosgan mijoz bilan tezda bog'lanish"
    action: Dict[str, Any] = {
        "type": "operator_handoff",
        "priority": "high",
        "message": text,
        "phone": phone,
        "lead_id": lead_id,
        "attempt_id": (attempt or {}).get("id"),
    }
    if lead_id:
        action["amocrm"] = {
            "lead_id": lead_id,
            "note": text,
            "task": task_text,
        }
    else:
        action["amocrm"] = {
            "lead_lookup": {"phone": phone},
            "note": text,
            "task": task_text,
        }
    return action
