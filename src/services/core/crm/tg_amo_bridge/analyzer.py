"""Pure phone/Telegram deal analysis and merge-decision logic (no I/O)."""
from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Sequence, Tuple

from src.services.core.crm.amocrm_pipeline_config import (
    FARMER_PIPELINE_ID,
    SALES_NEW_STATUS_ID,
    STATUS_LOST,
    STATUS_WON,
    UTC_NEW_STATUS_ID,
)

CLOSED_STATUS_IDS = frozenset({STATUS_WON, STATUS_LOST})
INITIAL_STAGE_IDS = frozenset({SALES_NEW_STATUS_ID, UTC_NEW_STATUS_ID, 80178230})

_UZ_PREFIXES = frozenset(
    {
        "20", "33", "50", "55", "61", "62", "65", "66", "67", "69",
        "70", "71", "72", "73", "74", "75", "76", "77", "78", "79",
        "88", "90", "91", "93", "94", "95", "97", "98", "99",
    }
)
_EXPLICIT_UZ_PHONE_RE = re.compile(
    r"(?<!\d)(?:\+?998[\s\-()]*)(?:20|33|50|55|6[125679]|7[0-9]|88|9[01345789])"
    r"[\s\-()]*\d{3}[\s\-()]*\d{2}[\s\-()]*\d{2}(?!\d)"
)
_LOCAL_UZ_PHONE_RE = re.compile(
    r"(?<!\d)(?:20|33|50|55|71|77|88|9[01345789])"
    r"[\s\-()]*\d{3}[\s\-()]*\d{2}[\s\-()]*\d{2}(?!\d)"
)
_TG_MARKERS = (
    "telegram",
    "oisha-tg",
    "tg chat",
    "tg:",
    "неразобранное",
    "входящее сообщение",
)


@dataclass(frozen=True)
class LeadProfile:
    lead_id: int
    contact_id: int
    name: str
    status_id: int
    pipeline_id: int
    price: int = 0
    created_at: int = 0
    updated_at: int = 0
    call_count: int = 0
    has_chat: bool = False
    notes_count: int = 0
    tags: Tuple[str, ...] = ()
    phones: Tuple[str, ...] = ()


@dataclass(frozen=True)
class PairDecision:
    action: str  # "merge" | "link_only" | "conflict" | "skip"
    target_lead_id: int
    source_lead_id: int
    target_contact_id: int
    source_contact_id: int
    confidence: str  # "high" | "medium" | "low"
    reason: str
    evidence: List[str] = field(default_factory=list)


def normalize_uz_phone(value: Any) -> str:
    """Normalize Uzbekistan or international phone numbers to digits only."""
    digits = re.sub(r"\D+", "", str(value or ""))
    if len(digits) < 9 or len(digits) > 15:
        return ""
    if len(digits) == 9:
        if digits[:2] in _UZ_PREFIXES:
            return "998" + digits
        return ""
    if len(digits) == 12 and digits.startswith("998"):
        return digits if digits[3:5] in _UZ_PREFIXES else ""
    if len(digits) == 13 and digits.startswith("0998"):
        tail = digits[1:]
        return tail if tail[3:5] in _UZ_PREFIXES else ""
    if 10 <= len(digits) <= 15 and not digits.startswith("0"):
        return digits
    return ""


def extract_phone_from_text(text: str) -> str:
    """Extract the first valid Uzbekistan phone number from chat or note text."""
    body = str(text or "")
    if not body:
        return ""
    for pattern in (_EXPLICIT_UZ_PHONE_RE, _LOCAL_UZ_PHONE_RE):
        for match in pattern.finditer(body):
            normalized = normalize_uz_phone(match.group(0))
            if normalized:
                return normalized
    return ""


def is_internal_team_phone(phone: str) -> bool:
    """Reject agency staff numbers so manager phones never merge client deals."""
    norm = normalize_uz_phone(phone)
    if not norm:
        return False
    tail = norm[-9:]
    try:
        from src.services.core.crm.team_roster import TEAM_MEMBERS

        for member in TEAM_MEMBERS:
            for candidate in (getattr(member, "phone", None), *(getattr(member, "phones", ()) or ())):
                c_norm = normalize_uz_phone(candidate)
                if c_norm and c_norm[-9:] == tail:
                    return True
    except Exception:
        return False
    return False


def contact_phones(contact: Dict[str, Any]) -> Tuple[str, ...]:
    """Return sorted unique normalized phones from an amoCRM contact payload."""
    found: set[str] = set()
    for field_item in contact.get("custom_fields_values") or []:
        if str(field_item.get("field_code") or "").upper() != "PHONE":
            continue
        for val in field_item.get("values") or []:
            norm = normalize_uz_phone(val.get("value"))
            if norm:
                found.add(norm)
    return tuple(sorted(found))


def lead_tags(lead: Dict[str, Any]) -> Tuple[str, ...]:
    raw_tags = (lead.get("_embedded") or {}).get("tags") or lead.get("tags") or []
    names: List[str] = []
    for tag in raw_tags:
        name = tag.get("name") if isinstance(tag, dict) else str(tag)
        if name:
            names.append(str(name).strip())
    return tuple(names)


def is_telegram_only_lead(profile: LeadProfile) -> bool:
    """Return True when a deal looks like a standalone Telegram chat deal."""
    if profile.status_id in CLOSED_STATUS_IDS:
        return False
    if profile.call_count > 0 or profile.price > 0:
        return False
    if profile.pipeline_id == FARMER_PIPELINE_ID:
        return False
    if profile.has_chat:
        return True
    haystack = " ".join([profile.name, *profile.tags]).lower()
    return any(marker in haystack for marker in _TG_MARKERS)


def score_primary_lead(profile: LeadProfile) -> Tuple[int, List[str]]:
    """Score a lead for primary (target) selection — phone/older deals win."""
    score = 0
    reasons: List[str] = []
    if profile.status_id not in CLOSED_STATUS_IDS:
        score += 100
        reasons.append("faol bitim")
    if profile.call_count > 0:
        score += 60
        reasons.append(f"telefon qoʻngʻiroqlari: {profile.call_count} ta")
    if profile.phones:
        score += 20
        reasons.append("telefon raqami mavjud")
    if profile.price > 0:
        score += 35
        reasons.append(f"summa: {profile.price}")
    if profile.pipeline_id == FARMER_PIPELINE_ID:
        score += 45
        reasons.append("loyiha voronkasida")
    if profile.status_id not in CLOSED_STATUS_IDS and profile.status_id not in INITIAL_STAGE_IDS:
        score += 25
        reasons.append("voronkada oldinga siljigan")
    if profile.notes_count > 0:
        score += 10
        reasons.append(f"izohlar: {profile.notes_count} ta")
    if is_telegram_only_lead(profile):
        score -= 30
    return score, reasons


def analyze_lead_pair(target: LeadProfile, source: LeadProfile) -> PairDecision:
    """Decide whether source (Telegram deal) should merge into target (phone deal)."""
    if target.lead_id == source.lead_id:
        return PairDecision("skip", target.lead_id, source.lead_id, target.contact_id, source.contact_id, "low", "same_lead")
    if source.status_id in CLOSED_STATUS_IDS:
        return PairDecision("skip", target.lead_id, source.lead_id, target.contact_id, source.contact_id, "low", "source_already_closed")
    if source.pipeline_id == FARMER_PIPELINE_ID:
        return PairDecision("conflict", target.lead_id, source.lead_id, target.contact_id, source.contact_id, "low", "source_in_farmer_pipeline")
    if target.price > 0 and source.price > 0:
        return PairDecision("conflict", target.lead_id, source.lead_id, target.contact_id, source.contact_id, "low", "both_leads_have_price")
    if target.call_count > 0 and source.call_count > 0:
        return PairDecision("conflict", target.lead_id, source.lead_id, target.contact_id, source.contact_id, "low", "both_leads_have_calls")
    if target.status_id in CLOSED_STATUS_IDS:
        return PairDecision(
            "link_only",
            target.lead_id,
            source.lead_id,
            target.contact_id,
            source.contact_id,
            "medium",
            "target_closed_preserve_active_tg_lead",
            ["avvalgi telefon sdelkasi yopilgan — yangi faol Telegram sdelkasi saqlandi"],
        )
    if not is_telegram_only_lead(source):
        return PairDecision("conflict", target.lead_id, source.lead_id, target.contact_id, source.contact_id, "low", "source_not_telegram_only")

    target_score, target_reasons = score_primary_lead(target)
    source_score, _ = score_primary_lead(source)
    has_phone_history = target.call_count > 0 or bool(target.phones)
    if not has_phone_history:
        return PairDecision("conflict", target.lead_id, source.lead_id, target.contact_id, source.contact_id, "low", "target_missing_phone_history")
    if target_score <= source_score and target.created_at > source.created_at > 0:
        return PairDecision("conflict", target.lead_id, source.lead_id, target.contact_id, source.contact_id, "low", "ambiguous_primary_lead")

    confidence = "high" if target.call_count > 0 or target_score > source_score else "medium"
    evidence = [
        f"asosiy sdelka #{target.lead_id}: " + ", ".join(target_reasons),
        f"Telegram dublikat #{source.lead_id}: faqat chat (qoʻngʻiroq=0, summa=0)",
    ]
    return PairDecision(
        action="merge",
        target_lead_id=target.lead_id,
        source_lead_id=source.lead_id,
        target_contact_id=target.contact_id,
        source_contact_id=source.contact_id,
        confidence=confidence,
        reason="telegram_duplicate_of_phone_deal",
        evidence=evidence,
    )


def pick_best_pair(profiles: Sequence[LeadProfile]) -> Optional[PairDecision]:
    """Select the highest-priority primary lead and a Telegram-only duplicate from a group."""
    if len(profiles) < 2:
        return None
    ranked = sorted(
        profiles,
        key=lambda p: (score_primary_lead(p)[0], -(p.created_at or 0)),
        reverse=True,
    )
    target = ranked[0]
    for candidate in ranked[1:]:
        decision = analyze_lead_pair(target, candidate)
        if decision.action in {"merge", "link_only", "conflict"}:
            return decision
    return None


def format_link_note(
    *,
    phone: str,
    phone_source: str,
    tg_user_id: int,
    username: Optional[str],
    client_name: str,
) -> str:
    handle = f"@{username}" if username else f"ID:{tg_user_id}"
    return (
        "🔗 [TG-AMO AUTO-LINK] Telegram chat mavjud telefon kontaktiga ulandi.\n"
        f"• Mijoz: {client_name} ({handle}, TG ID: {tg_user_id})\n"
        f"• Raqam: +{phone} (manba: {phone_source})\n"
        "• Holat: alohida Telegram sdelkasi ochilmadi, yozishmalar shu sdelkada davom etadi."
    )


def format_merge_note(
    *,
    decision: PairDecision,
    phone: str,
    tg_user_id: Optional[int],
    username: Optional[str],
    source_notes: Sequence[str],
    migrated_tasks: int,
) -> str:
    handle = f"@{username}" if username else (f"ID:{tg_user_id}" if tg_user_id else "nomaʼlum")
    lines = [
        "🔗 [TG-AMO AUTO-MERGE] Alohida Telegram sdelkasi asosiy sdelkaga birlashtirildi.",
        f"• Birlashtirilgan sdelka: #{decision.source_lead_id} -> #{decision.target_lead_id}",
        f"• Telefon: +{phone} | Telegram: {handle}",
        f"• Ishonchlilik: {decision.confidence}",
    ]
    for item in decision.evidence:
        lines.append(f"• Tahlil: {item}")
    if migrated_tasks:
        lines.append(f"• Koʻchirilgan ochiq vazifalar: {migrated_tasks} ta")
    if source_notes:
        lines.append("• Telegram sdelkasidan koʻchirilgan izohlar:")
        for snippet in source_notes[:5]:
            lines.append(f"  - {snippet[:300]}")
    return "\n".join(lines)
