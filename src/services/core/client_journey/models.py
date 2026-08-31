"""
Data models, stage thresholds, and formatting helpers for client journey playbook.
"""
from __future__ import annotations

import datetime
import logging
import re
from dataclasses import dataclass
from html import escape
from typing import Any, Dict, List, Optional, Tuple

from src.services.core.airtable_sync import AirtableSync
from src.time_utils import get_local_now

logger = logging.getLogger("ClientJourneyPlaybook")

@dataclass
class JourneySignal:
    department: str
    client_name: str
    stage: str
    urgency: str
    owner_hint: str
    risk: str
    owner_action: str
    wow_action: str
    proof_of_done: str
    meta: Dict[str, Any]


AIRTABLE_STAGE_THRESHOLDS = {
    "Advocacy": 2,
    "Kickoff discipline": 2,
    "Preview excellence": 4,
    "Feedback closure": 3,
    "Handoff readiness": 3,
}

STAGE_ORDER = [
    "VIP rescue",
    "Recovery follow-up",
    "Speed-to-lead",
    "Advocacy",
    "Kickoff discipline",
    "Preview excellence",
    "Feedback closure",
    "Handoff readiness",
    "Payment hygiene",
]

STAGE_LABELS = {
    "VIP rescue": "VIP mijozni qayta ushlash",
    "Recovery follow-up": "Qolib ketgan lidni qayta jonlantirish",
    "Speed-to-lead": "Tezkor birinchi javob",
    "Advocacy": "Otziv va tavsiya olish",
    "Kickoff discipline": "Boshlanishni tartibga solish",
    "Preview excellence": "Oraliq ko'rinishni aniq yopish",
    "Feedback closure": "Feedbackni yopish",
    "Handoff readiness": "Topshirishga tayyorgarlik",
    "Payment hygiene": "To'lovni yopish",
}

OWNER_LABELS = {
    "Sales": "Sotuv",
    "Sales/Finance": "Sotuv / Moliya",
    "PM": "PM",
}

COPY_REPLACEMENTS = (
    ("owner/ETA", "mas'ul va muddat"),
    ("owner / ETA", "mas'ul va muddat"),
    ("owner", "mas'ul"),
    ("Owner", "Mas'ul"),
    ("ETA", "muddat"),
    ("next-step", "keyingi qadam"),
    ("next step", "keyingi qadam"),
    ("Next step", "Keyingi qadam"),
    ("feedback question", "feedback savoli"),
    ("Feedback matrix", "Feedback jadvali"),
    ("feedback matrix", "feedback jadvali"),
    ("closure", "yakuniy"),
    ("Closure", "Yakuniy"),
    ("kickoff", "boshlanish"),
    ("Kickoff", "Boshlanish"),
    ("preview", "oraliq ko'rinish"),
    ("Preview", "Oraliq ko'rinish"),
    ("support window", "qo'llab-quvvatlash muddati"),
    ("recap", "qisqa xulosa"),
    ("rationale", "asos"),
)


def _safe_text(value: Any, fallback: str = "Noma'lum") -> str:
    text = str(value).strip() if value is not None else ""
    return text or fallback


def _normalize_copy(value: Any, fallback: str = "Noma'lum") -> str:
    text = _safe_text(value, fallback)
    for source, target in COPY_REPLACEMENTS:
        text = text.replace(source, target)
    return text


def _to_number(value: Any) -> float:
    if value in (None, "", False):
        return 0.0
    try:
        return float(str(value).replace(" ", "").replace(",", "."))
    except (TypeError, ValueError):
        return 0.0


def _lead_idle_hours(lead: Dict[str, Any], now_epoch: Optional[int] = None) -> int:
    now_ts = now_epoch or int(get_local_now().timestamp())
    updated_at = int(lead.get("updated_at") or 0)
    if updated_at <= 0:
        return 0
    return max(0, int((now_ts - updated_at) / 3600))


def _urgency_rank(level: str) -> int:
    return {"critical": 0, "high": 1, "medium": 2, "low": 3}.get(level, 4)


def _looks_like_airtable_id(value: str) -> bool:
    return bool(re.fullmatch(r"rec[a-zA-Z0-9]{10,}", value))


def _humanize_owner_hint(value: Any) -> str:
    if isinstance(value, list):
        labels: List[str] = []
        for item in value:
            label = _humanize_owner_hint(item)
            if label and label not in labels and label != "Mas'ul aniqlansin":
                labels.append(label)
        return ", ".join(labels) if labels else "Mas'ul aniqlansin"

    text = str(value).strip() if value is not None else ""
    if not text or text in ("None", "null", "[]"):
        return "Mas'ul aniqlansin"

    if text in OWNER_LABELS:
        return OWNER_LABELS[text]

    if text.startswith("@"):
        return text

    if _looks_like_airtable_id(text):
        handle = AirtableSync.resolve_pm_handle(text)
        if handle and handle != "Mas'ul belgilanmagan":
            return handle
        name = AirtableSync.resolve_pm_name(text)
        if name and name != "Mas'ul belgilanmagan":
            return name

    record_ids = re.findall(r"rec[a-zA-Z0-9]{10,}", text)
    if record_ids:
        handles: List[str] = []
        for record_id in record_ids:
            handle = AirtableSync.resolve_pm_handle(record_id)
            if handle and handle not in handles and handle != "Mas'ul belgilanmagan":
                handles.append(handle)
        return ", ".join(handles) if handles else "Mas'ul aniqlansin"

    handle = AirtableSync.resolve_pm_handle(text)
    if handle and handle != "Mas'ul belgilanmagan":
        return handle

    return OWNER_LABELS.get(text, text)


def _humanize_stage(stage: Any) -> str:
    text = _safe_text(stage)
    return STAGE_LABELS.get(text, text)


def _render_owner_html(signal: JourneySignal, airtable: Optional[AirtableSync]) -> str:
    raw_owner = signal.meta.get("manager_ref") or signal.owner_hint

    if isinstance(raw_owner, list):
        seen: set[str] = set()
        parts: List[str] = []
        for item in raw_owner:
            label = _humanize_owner_hint(item)
            if not label or label in seen or label == "Mas'ul aniqlansin":
                continue
            seen.add(label)
            url = (
                airtable.get_record_url(item)
                if airtable and _looks_like_airtable_id(str(item))
                else None
            )
            if url:
                parts.append(f"<a href='{escape(url, quote=True)}'>{escape(label)}</a>")
            else:
                parts.append(escape(label))
        return (
            ", ".join(parts)
            if parts
            else escape(_humanize_owner_hint(signal.owner_hint))
        )

    raw_owner_text = str(raw_owner).strip() if raw_owner is not None else ""
    if airtable and _looks_like_airtable_id(raw_owner_text):
        url = airtable.get_record_url(raw_owner_text)
        if url:
            return f"<a href='{escape(url, quote=True)}'>{escape(_humanize_owner_hint(raw_owner_text))}</a>"

    return escape(_humanize_owner_hint(signal.owner_hint))


def _render_airtable_card_line(
    signal: JourneySignal, airtable: Optional[AirtableSync]
) -> Optional[str]:
    if not airtable:
        return None

    record_id = signal.meta.get("project_id")
    if not record_id or not _looks_like_airtable_id(str(record_id)):
        return None

    url = airtable.get_record_url(str(record_id))
    if not url:
        return None

    return f"  Airtable kartasi: <a href='{escape(url, quote=True)}'>yozuvni ochish</a>"


def _project_age_days(project: Dict[str, Any]) -> int:
    fields = project.get("fields", {})
    start_raw = AirtableSync._get_field(fields, "start_date")
    if not start_raw:
        return 0

    try:
        created_dt = datetime.datetime.fromisoformat(
            str(start_raw).replace("Z", "+00:00")
        )
    except ValueError:
        return 0

    now = get_local_now()
    if created_dt.tzinfo is not None:
        now_cmp = now.astimezone(datetime.timezone.utc)
    else:
        now_cmp = now.replace(tzinfo=None)
    return max(0, (now_cmp - created_dt).days)


def _is_overdue(deadline: Any) -> bool:
    if not deadline:
        return False
    try:
        deadline_dt = datetime.datetime.strptime(str(deadline), "%Y-%m-%d")
    except ValueError:
        return False
    return deadline_dt.date() < get_local_now().date()

