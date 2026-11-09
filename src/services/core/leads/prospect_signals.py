"""Evidence-only Telegram prospect classification; no inferred qualification."""
from __future__ import annotations

import hashlib
import re
from datetime import datetime, timezone

from pydantic import BaseModel, Field
from src.services.core.leads.lead_filter_guard import is_excluded_contact


SERVICES = {
    "branding": r"\b(?:brending|branding|rebrending|rebranding|logotip|logo|brendbuk|brandbook)\b",
    "packaging": r"\b(?:qadoq\w*|upakovka|упаков\w*)\b",
    "website": r"\b(?:sayt|website|veb.sayt|сайт)\b",
    "design": r"\b(?:dizayn\w*|designer|дизайн\w*)\b",
}
DEMAND = re.compile(
    r"\b(?:kerak|izlay\w*|qidir\w*|tavsiya|нуж\w*|ищ\w*)\b", re.I
)
OFFER = re.compile(
    r"\b(?:xizmatlarimiz|xizmatimiz|yasaymiz|qilamiz|tayyorlaymiz|услуги|предлагаем)\b", re.I
)
PHONE = re.compile(r"(?<!\d)\+?998(?:[\s()-]*\d){9}(?!\d)")


class Prospect(BaseModel):
    key: str
    chat_id: int
    message_id: int = Field(gt=0)
    source_url: str
    observed_at: datetime
    published_at: datetime
    service: str
    evidence: str
    phone: str | None = None
    sender_id: int | None = None
    qualification: str = "needs_review"
    budget: None = None
    purchase_timing: None = None
    crm_status: str = "unchecked"


def classify_message(message, chat_id: int, now: datetime) -> list[Prospect]:
    """Match explicit demand in one sentence, rejecting seller/job advertisements."""
    text = getattr(message, "message", None) or ""
    published = getattr(message, "date", None)
    if not text or not isinstance(published, datetime) or published.tzinfo is None:
        return []
    if published > now:
        return []
    if OFFER.search(text) or re.search(r"\b(?:vakansiya|вакансия|oylik|зарплата)\b", text, re.I):
        return []
    sender = getattr(message, "sender", None)
    s_name = f"{getattr(sender, 'first_name', '') or ''} {getattr(sender, 'last_name', '') or ''}".strip()
    s_user = getattr(sender, "username", "") or ""
    if s_name or s_user:
        excluded, _ = is_excluded_contact(name=s_name, username=s_user)
        if excluded:
            return []
    message_id = getattr(message, "id", None)
    if not isinstance(message_id, int) or message_id <= 0 or chat_id >= 0:
        return []
    result = []
    for sentence in re.split(r"[.!?\n]+", text):
        if not DEMAND.search(sentence):
            continue
        if re.search(r"kerak\s+emas|не\s+нуж|qidir\w*\s+emas", sentence, re.I):
            continue
        for service, pattern in SERVICES.items():
            if not re.search(pattern, sentence, re.I):
                continue
            if service == "design" and any(
                re.search(specific, sentence, re.I)
                for name, specific in SERVICES.items() if name != "design"
            ):
                continue
            normalized = " ".join(text.casefold().split())
            key = hashlib.sha256(f"{service}:{normalized}".encode()).hexdigest()
            phone_match = PHONE.search(text)
            result.append(Prospect(
                key=key, chat_id=chat_id, message_id=message_id,
                source_url=f"https://t.me/c/{str(abs(chat_id)).removeprefix('100')}/{message_id}",
                observed_at=now.astimezone(timezone.utc), published_at=published,
                service=service, evidence=sentence.strip()[:600],
                phone=("+" + re.sub(r"\D", "", phone_match.group())) if phone_match else None,
                sender_id=getattr(message, "sender_id", None),
            ))
    return result
