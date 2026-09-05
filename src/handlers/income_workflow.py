"""Income workflow handlers — Airtable integration, state management, approvals."""
from __future__ import annotations

import json
import re
import asyncio
import structlog
from typing import Any, Dict, Optional

from src.settings import settings
from src import config

logger = structlog.get_logger()


def income_state_key(message_id: int) -> str:
    return f"income_workflow:{message_id}"


def income_gate_key(message_id: int) -> str:
    return f"income_workflow_gate:{message_id}"


def normalize_income_lookup(text: str) -> str:
    normalized = re.sub(r"[^\w]+", " ", (text or "").lower(), flags=re.UNICODE)
    return " ".join(normalized.split())


def detect_payment_type(text: str, is_first_payment: bool) -> str:
    lowered = (text or "").lower()
    if "to'liq" in lowered or "toliq" in lowered or "full" in lowered:
        return "Oldindan to'liq" if is_first_payment else "Yakuniy"
    if "yakuniy" in lowered or "final" in lowered or "qoldiq" in lowered:
        return "Yakuniy"
    return "Avans" if is_first_payment else "Orada to'lov"


def detect_payment_source(text: str) -> Optional[str]:
    lowered = (text or "").lower()
    if "naqd" in lowered or "cash" in lowered:
        return "Naqd"
    if "bank" in lowered or "hisob" in lowered:
        return "Bank hisobi"
    if "p2p" in lowered or "card" in lowered or "karta" in lowered:
        return "P2P card"
    return None


def format_person_mention(person: Optional[Dict[str, Any]], fallback: str) -> str:
    if not person:
        return fallback
    username = (person.get("username") or "").strip()
    if username:
        return username if username.startswith("@") else f"@{username}"
    user_id = person.get("user_id")
    name = person.get("name") or fallback
    if user_id:
        return f"<a href='tg://user?id={user_id}'>{name}</a>"
    return name


def is_group_open_confirmation(text: str) -> bool:
    lowered = (text or "").lower()
    keywords = (
        "guruh ochildi",
        "group opened",
        "group open",
        "gruppa ochildi",
        "mijoz bilan guruh",
        "client group",
    )
    return any(keyword in lowered for keyword in keywords) or "t.me/" in lowered


def is_finance_approval(text: str) -> bool:
    lowered = (text or "").lower()
    keywords = (
        "tasdiq",
        "tasdiqlandi",
        "confirmed",
        "confirm",
        "ok",
        "okey",
        "tushdi",
        "tushgan",
    )
    return any(keyword in lowered for keyword in keywords)


def is_finance_rejection(text: str) -> bool:
    lowered = (text or "").lower()
    keywords = (
        "rad",
        "reject",
        "rejected",
        "tasdiqlamadi",
        "tasdiqlanmadi",
        "xato",
        "xatolik",
        "tushmadi",
        "bekor",
    )
    return any(keyword in lowered for keyword in keywords)


async def resolve_finance_approver(db) -> Optional[Dict[str, Any]]:
    for role_name in ("finance", "moliya", "accountant", "buxgalter"):
        person = await db.get_user_by_role(role_name)
        if person:
            return person

    owner_id = getattr(settings, "OWNER_ID", None) or getattr(config, "OWNER_ID", None)
    if owner_id:
        return {"user_id": owner_id, "name": "Owner", "username": None}
    return None


async def find_project_for_income(message_text: str) -> Optional[Dict[str, Any]]:
    from src.services.core.airtable_sync import AirtableSync

    sync = AirtableSync()
    projects = await asyncio.to_thread(sync.get_projects)
    if not projects:
        return None

    normalized_text = normalize_income_lookup(message_text)
    best_match = None
    best_score = 0.0

    for project in projects:
        fields = project.get("fields", {})
        project_name = AirtableSync._get_field(fields, "project_name", "") or ""
        normalized_name = normalize_income_lookup(project_name)
        if len(normalized_name) < 4:
            continue

        if normalized_name in normalized_text:
            score = 2.0 + (len(normalized_name) / 1000)
        else:
            tokens = [token for token in normalized_name.split() if len(token) >= 4]
            if not tokens:
                continue
            hits = sum(1 for token in tokens if token in normalized_text)
            score = hits / len(tokens)

        if score > best_score:
            best_score = score
            best_match = {
                "record_id": project.get("id"),
                "project_name": project_name,
                "client_ids": fields.get("Mijoz nomi") or [],
                "seller_ids": fields.get("Seller") or [],
                "project_fields": fields,
            }

    return best_match if best_score >= 0.6 else None


async def count_income_records_for_project(project_record_id: str) -> int:
    from src.services.core.airtable_sync import AirtableSync

    sync = AirtableSync()
    records = await asyncio.to_thread(sync.get_finance_records)
    count = 0
    for record in records:
        if record.get("_record_type") != "income":
            continue
        if project_record_id in (record.get("fields", {}).get("Loyiha nomi") or []):
            count += 1
    return count


async def create_income_airtable_record(
    workflow: Dict[str, Any],
) -> Optional[Dict[str, Any]]:
    from src.services.core.airtable_sync import AirtableSync
    from src.time_utils import get_local_now

    project_id = workflow.get("project_id")
    if not project_id:
        return None

    project_fields = workflow.get("project_fields") or {}
    amount_value = workflow.get("amount_value")
    if amount_value is None:
        return None

    currency = workflow.get("currency") or "UZS"
    kurs = project_fields.get("Kurs") or 12000
    fields: Dict[str, Any] = {
        "Loyiha nomi": [project_id],
        "Valyuta": currency,
        "To'lov sanasi": get_local_now().strftime("%Y-%m-%d"),
        "To'lov miqdori": amount_value,
        "Kurs": kurs,
        "To'lov turi": detect_payment_type(
            workflow.get("source_text", ""), workflow.get("is_first_payment", False)
        ),
    }

    payment_source = detect_payment_source(workflow.get("source_text", ""))
    if payment_source:
        fields["To'lov manbasi"] = payment_source
    if workflow.get("client_ids"):
        fields["Mijoz"] = workflow["client_ids"]
    if workflow.get("seller_ids"):
        fields["Seller"] = workflow["seller_ids"]

    sync = AirtableSync(table_name="Kirim")
    return await asyncio.to_thread(sync.create_record, fields)


async def save_income_workflow_state(db, payload: Dict[str, Any]) -> None:
    await db.set_state(
        income_state_key(int(payload["original_message_id"])),
        json.dumps(payload, ensure_ascii=False),
    )
    gate_message_id = payload.get("gate_message_id")
    if gate_message_id:
        await db.set_state(
            income_gate_key(int(gate_message_id)), int(payload["original_message_id"])
        )


async def load_income_workflow_state(
    db, reply_message_id: Optional[int]
) -> Optional[Dict[str, Any]]:
    if not reply_message_id:
        return None

    raw = await db.get_state(income_state_key(int(reply_message_id)))
    if raw:
        try:
            return json.loads(raw)
        except json.JSONDecodeError:
            return None

    original_id = await db.get_state(income_gate_key(int(reply_message_id)))
    if not original_id:
        return None

    raw = await db.get_state(income_state_key(int(original_id)))
    if not raw:
        return None
    try:
        return json.loads(raw)
    except json.JSONDecodeError:
        return None
