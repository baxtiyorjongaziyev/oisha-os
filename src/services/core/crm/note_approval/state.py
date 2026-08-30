"""
State tracking and persistence for pending CRM note approvals.
"""
from __future__ import annotations

import asyncio
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

import structlog
from src.services.core.crm.note_approval.models import _approval_key

logger = structlog.get_logger()

_pending: Dict[str, Dict[str, Any]] = {}
_pending_edit: Dict[int, str] = {}


async def _prune_pending(max_age_seconds: int = 86400) -> None:
    cutoff = datetime.now(timezone.utc)
    stale = [
        (k, v) for k, v in list(_pending.items())
        if (cutoff - datetime.fromisoformat(v["created_at"]).replace(tzinfo=timezone.utc)).total_seconds() > max_age_seconds
    ]
    for k, v in stale:
        try:
            await post_notes_to_amocrm(v["amocrm"], v["lead_id"], v["note_texts"])
            logger.info("[CRM_NOTE] 24h timeout: lead %s uchun izoh avtomatik qo'shildi", v["lead_id"])
        except Exception as e:
            logger.error("[CRM_NOTE] 24h timeout auto-post xatolik lead %s: %s", v["lead_id"], e)
        _pending.pop(k, None)
    stale_edits = [uid for uid, akey in _pending_edit.items() if akey not in _pending]
    for uid in stale_edits:
        _pending_edit.pop(uid, None)


async def register_pending(
    lead_id: int,
    call_id: str,
    note_texts: List[str],
    analysis: Dict[str, Any],
    amocrm_client: Any,
) -> None:
    await _prune_pending()
    key = _approval_key(lead_id, call_id)
    _pending[key] = {
        "lead_id": lead_id,
        "call_id": call_id,
        "note_texts": note_texts,
        "analysis": analysis,
        "amocrm": amocrm_client,
        "created_at": datetime.now(timezone.utc).isoformat(),
    }


async def post_note_to_amocrm(amocrm_client: Any, lead_id: int, note_text: str) -> bool:
    try:
        result = await asyncio.to_thread(amocrm_client.add_lead_note, lead_id, note_text)
        if result:
            logger.info("[CRM_NOTE] Lead %s ga izoh qo'shildi", lead_id)
            return True
        return False
    except Exception as e:
        logger.error("[CRM_NOTE] AMO POST xatolik: %s", e)
        return False


async def post_notes_to_amocrm(amocrm_client: Any, lead_id: int, note_texts: List[str]) -> bool:
    ok = True
    for nt in note_texts:
        if nt and nt.strip():
            ok = await post_note_to_amocrm(amocrm_client, lead_id, nt) and ok
    return ok


def pop_pending_edit(user_id: int) -> Optional[str]:
    return _pending_edit.pop(user_id, None)


def push_pending_edit(user_id: int, approve_key: str) -> None:
    _pending_edit[user_id] = approve_key
