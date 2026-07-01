"""AmoCRM deal hygiene agent.

This module separates suspicious/noise deals from real client work and finds
high-probability duplicates using AmoCRM contacts plus Telegram memory.
It is deliberately conservative: it tags and explains, but never deletes or
merges records automatically.
"""

from __future__ import annotations

import logging
import re
import time
from collections import defaultdict
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from typing import Any, Dict, Iterable, List, Optional, Set, Tuple

from src.services.core.amocrm_sync import AmoCRMSync

logger = logging.getLogger(__name__)


PHONE_RE = re.compile(r"(?:\+?998[\s\-()]*)?\d{2}[\s\-()]*\d{3}[\s\-()]*\d{2}[\s\-()]*\d{2}")
USERNAME_RE = re.compile(r"(?<![A-Za-z0-9_])@([A-Za-z0-9_]{5,32})")

HARD_NOISE_KEYWORDS = {
    "spam": "Spam yoki bot xabar",
    "reklama": "Begona reklama",
    "noto'g'ri raqam": "Noto'g'ri raqam",
    "notogri raqam": "Noto'g'ri raqam",
    "wrong number": "Noto'g'ri raqam",
    "qiziqmagan": "Mijoz qiziqmagan",
    "qiziqmaydi": "Mijoz qiziqmagan",
    "mijoz emas": "Mijoz emas",
    "not client": "Mijoz emas",
    "shaxsiy": "Shaxsiy yozishma",
    "oila": "Shaxsiy/oila aloqasi",
    "qarindosh": "Shaxsiy/oila aloqasi",
}

METASELL_LOST_OUTCOMES = {
    "lost",
    "no_interest",
    "not_interested",
    "wrong_number",
    "spam",
    "invalid",
}

SYSTEM_TAGS = {
    "personal": "OISHA_PERSONAL_NOT_CLIENT",
    "spam": "OISHA_SPAM_OR_WRONG",
    "low_quality_lost": "OISHA_LOW_QUALITY_LOST",
    "needs_review": "OISHA_NEEDS_REVIEW",
    "duplicate": "OISHA_DUPLICATE_SUSPECT",
}


@dataclass
class DealSignal:
    source: str
    message: str
    weight: float = 0.1


@dataclass
class DealHygieneFinding:
    lead_id: int
    lead_name: str
    category: str
    confidence: float
    reason: str
    evidence: List[str] = field(default_factory=list)
    recommended_action: str = "review"
    amo_url: Optional[str] = None
    tag: str = SYSTEM_TAGS["needs_review"]


@dataclass
class DuplicateDealFinding:
    probability: float
    reason: str
    lead_ids: List[int]
    lead_names: List[str]
    phones: List[str] = field(default_factory=list)
    telegram_usernames: List[str] = field(default_factory=list)
    telegram_user_ids: List[int] = field(default_factory=list)
    contact_ids: List[int] = field(default_factory=list)
    evidence: List[str] = field(default_factory=list)
    recommended_action: str = "Birlashtirishdan oldin mas'ul bilan tekshiring"
    tag: str = SYSTEM_TAGS["duplicate"]


@dataclass
class LeadIdentity:
    lead_id: int
    lead_name: str
    status_id: Optional[int]
    pipeline_id: Optional[int]
    responsible_user_id: Optional[int]
    updated_at: Optional[int]
    phones: Set[str] = field(default_factory=set)
    telegram_usernames: Set[str] = field(default_factory=set)
    telegram_user_ids: Set[int] = field(default_factory=set)
    contact_ids: Set[int] = field(default_factory=set)
    note_text: str = ""


def normalize_phone(value: Any) -> str:
    """Return a stable Uzbek-friendly phone key."""
    digits = re.sub(r"\D+", "", str(value or ""))
    if not digits:
        return ""
    if len(digits) >= 9:
        return digits[-9:]
    return digits


def extract_phones(text: str) -> Set[str]:
    phones: Set[str] = set()
    for match in PHONE_RE.findall(text or ""):
        normalized = normalize_phone(match)
        if len(normalized) >= 9:
            phones.add(normalized)
    return phones


def extract_usernames(text: str) -> Set[str]:
    return {m.group(1).lower() for m in USERNAME_RE.finditer(text or "")}


def _safe_ts(value: Any) -> Optional[int]:
    try:
        return int(value) if value is not None else None
    except (TypeError, ValueError):
        return None


class AmoCRMDealHygieneAgent:
    """Find noisy AmoCRM deals and duplicate deal probabilities."""

    def __init__(self, amocrm: AmoCRMSync, db: Any = None):
        self.amocrm = amocrm
        self.db = db

    async def audit(self, limit: int = 100) -> Dict[str, Any]:
        leads = await self.amocrm.get_leads_detailed(limit=min(max(limit, 1), 250))
        active_leads = [lead for lead in leads if lead.get("status_id") not in (142, 143)]
        telegram_profiles = await self._load_telegram_profiles()

        identities: List[LeadIdentity] = []
        unnecessary: List[DealHygieneFinding] = []

        for lead in active_leads:
            identity = await self._build_identity(lead, telegram_profiles)
            identities.append(identity)

            finding = await self._classify_unnecessary(lead, identity)
            if finding:
                unnecessary.append(finding)

        duplicates = self._find_duplicates(identities)

        return {
            "generated_at": datetime.now(timezone.utc).isoformat(),
            "checked_leads": len(active_leads),
            "unnecessary_count": len(unnecessary),
            "duplicate_group_count": len(duplicates),
            "unnecessary_deals": [asdict(item) for item in unnecessary],
            "duplicate_suspects": [asdict(item) for item in duplicates],
            "safety": {
                "auto_delete": False,
                "auto_merge": False,
                "apply_mode": "tags_notes_tasks_only",
            },
        }

    async def apply_report(
        self,
        report: Dict[str, Any],
        create_tasks: bool = True,
    ) -> Dict[str, Any]:
        """Apply safe AmoCRM annotations only: tags, notes, optional tasks."""
        actions: List[Dict[str, Any]] = []

        for item in report.get("unnecessary_deals", []):
            lead_id = int(item["lead_id"])
            tag = item.get("tag") or SYSTEM_TAGS["needs_review"]
            note = self._format_unnecessary_note(item)
            actions.append(await self._tag_and_note(lead_id, tag, note))
            if create_tasks:
                task_text = (
                    "Oisha: sdelka sifati shubhali. Dalillarni tekshirib, "
                    "keraksiz bo'lsa Lost/keraksiz segmentga ajrating."
                )
                actions.append(await self._create_review_task(lead_id, task_text))

        for group in report.get("duplicate_suspects", []):
            note = self._format_duplicate_note(group)
            for lead_id in group.get("lead_ids", []):
                actions.append(
                    await self._tag_and_note(int(lead_id), SYSTEM_TAGS["duplicate"], note)
                )
            if create_tasks and group.get("lead_ids"):
                lead_id = int(group["lead_ids"][0])
                actions.append(
                    await self._create_review_task(
                        lead_id,
                        "Oisha: duplikat sdelka ehtimoli yuqori. "
                        "Telefon/Telegram mosligini tekshirib, bitta asosiy sdelkani qoldiring.",
                    )
                )

        return {
            "attempted": len(actions),
            "success": sum(1 for action in actions if action.get("success")),
            "failed": sum(1 for action in actions if not action.get("success")),
            "actions": actions,
        }

    async def _build_identity(
        self,
        lead: Dict[str, Any],
        telegram_profiles: Dict[str, List[Dict[str, Any]]],
    ) -> LeadIdentity:
        lead_id = int(lead["id"])
        notes = await self.amocrm.get_lead_notes(lead_id)
        note_text = self._notes_to_text(notes)
        identity = LeadIdentity(
            lead_id=lead_id,
            lead_name=lead.get("name") or f"Lead #{lead_id}",
            status_id=lead.get("status_id"),
            pipeline_id=lead.get("pipeline_id"),
            responsible_user_id=lead.get("responsible_user_id"),
            updated_at=_safe_ts(lead.get("updated_at")),
            note_text=note_text,
        )

        identity.phones.update(extract_phones(identity.lead_name))
        identity.phones.update(extract_phones(note_text))
        identity.telegram_usernames.update(extract_usernames(identity.lead_name))
        identity.telegram_usernames.update(extract_usernames(note_text))

        for contact_ref in lead.get("_embedded", {}).get("contacts", []) or []:
            contact_id = contact_ref.get("id")
            if not contact_id:
                continue
            identity.contact_ids.add(int(contact_id))
            contact = self.amocrm.get_contact_details(int(contact_id)) or {}
            contact_text = self._contact_to_text(contact)
            identity.phones.update(extract_phones(contact_text))
            identity.telegram_usernames.update(extract_usernames(contact_text))
            for phone in self._extract_contact_phones(contact):
                identity.phones.add(phone)

        for phone in list(identity.phones):
            for profile in telegram_profiles.get(f"phone:{phone}", []):
                self._merge_profile(identity, profile)

        for username in list(identity.telegram_usernames):
            for profile in telegram_profiles.get(f"username:{username}", []):
                self._merge_profile(identity, profile)

        return identity

    async def _classify_unnecessary(
        self,
        lead: Dict[str, Any],
        identity: LeadIdentity,
    ) -> Optional[DealHygieneFinding]:
        signals: List[DealSignal] = []
        combined_text = f"{identity.lead_name}\n{identity.note_text}".lower()

        for keyword, reason in HARD_NOISE_KEYWORDS.items():
            if keyword in combined_text:
                signals.append(DealSignal("crm_notes", reason, 0.45))

        analysis = await self._get_metasell_analysis(identity.lead_id)
        if analysis:
            outcome = str(analysis.get("outcome") or "").lower()
            interest = self._to_float(analysis.get("client_interest_level"))
            summary_text = " ".join(
                str(analysis.get(key) or "")
                for key in ("summary", "weaknesses", "objections", "next_steps")
            ).lower()

            if outcome in METASELL_LOST_OUTCOMES:
                signals.append(DealSignal("metasell_outcome", f"MetaSell natija: {outcome}", 0.35))
            if interest is not None and interest <= 25:
                signals.append(
                    DealSignal("metasell_interest", f"MetaSell qiziqish darajasi past: {interest:g}", 0.25)
                )
            for keyword, reason in HARD_NOISE_KEYWORDS.items():
                if keyword in summary_text:
                    signals.append(DealSignal("metasell_summary", reason, 0.35))

        if not signals:
            return None

        score = min(0.98, 0.35 + sum(signal.weight for signal in signals))
        category = self._category_from_signals(signals)
        tag = SYSTEM_TAGS.get(category, SYSTEM_TAGS["needs_review"])

        if category == "low_quality_lost" and score < 0.7:
            return None

        reason = signals[0].message
        if len(signals) > 1:
            reason = f"{reason}; qo'shimcha {len(signals) - 1} ta signal bor"

        return DealHygieneFinding(
            lead_id=identity.lead_id,
            lead_name=identity.lead_name,
            category=category,
            confidence=round(score, 2),
            reason=reason,
            evidence=[f"{s.source}: {s.message}" for s in signals[:6]],
            recommended_action=(
                "Mas'ul bilan tekshirib, keraksiz bo'lsa Lost/keraksiz segmentga ajrating"
            ),
            amo_url=self._lead_url(identity.lead_id),
            tag=tag,
        )

    def _find_duplicates(self, identities: List[LeadIdentity]) -> List[DuplicateDealFinding]:
        groups: Dict[Tuple[str, str], List[LeadIdentity]] = defaultdict(list)
        for identity in identities:
            for phone in identity.phones:
                groups[("phone", phone)].append(identity)
            for username in identity.telegram_usernames:
                groups[("username", username)].append(identity)
            for user_id in identity.telegram_user_ids:
                groups[("telegram_user_id", str(user_id))].append(identity)
            for contact_id in identity.contact_ids:
                groups[("contact_id", str(contact_id))].append(identity)

        findings: Dict[Tuple[int, ...], DuplicateDealFinding] = {}
        for (kind, value), items in groups.items():
            unique = self._unique_by_lead(items)
            if len(unique) < 2:
                continue

            lead_key = tuple(sorted(item.lead_id for item in unique))
            current = findings.get(lead_key)
            probability = self._duplicate_probability(kind, unique)
            evidence = [f"{kind} mos tushdi: {value}"]
            if current:
                current.probability = min(0.99, current.probability + 0.04)
                current.evidence.extend(evidence)
                current.reason = "Bir nechta moslik topildi: " + ", ".join(current.evidence[:3])
                continue

            findings[lead_key] = DuplicateDealFinding(
                probability=probability,
                reason=f"{kind} bo'yicha bir xil identifikator topildi",
                lead_ids=[item.lead_id for item in unique],
                lead_names=[item.lead_name for item in unique],
                phones=sorted({phone for item in unique for phone in item.phones}),
                telegram_usernames=sorted(
                    {username for item in unique for username in item.telegram_usernames}
                ),
                telegram_user_ids=sorted(
                    {user_id for item in unique for user_id in item.telegram_user_ids}
                ),
                contact_ids=sorted({cid for item in unique for cid in item.contact_ids}),
                evidence=evidence,
            )

        return sorted(findings.values(), key=lambda item: item.probability, reverse=True)

    async def _load_telegram_profiles(self) -> Dict[str, List[Dict[str, Any]]]:
        profiles: Dict[str, List[Dict[str, Any]]] = defaultdict(list)
        if not self.db:
            return profiles

        try:
            conn = await self.db.get_connection()
            async with conn.execute(
                """
                SELECT user_id, first_name, last_name, username, phone, intent, role, detailed_role
                FROM users
                WHERE (phone IS NOT NULL AND phone != '')
                   OR (username IS NOT NULL AND username != '')
                """
            ) as cursor:
                rows = await cursor.fetchall()
                columns = [desc[0] for desc in cursor.description]
        except Exception as exc:
            logger.warning(f"[DEAL HYGIENE] Telegram profile load failed: {exc}")
            return profiles

        for row in rows:
            profile = dict(zip(columns, row))
            phone = normalize_phone(profile.get("phone"))
            username = str(profile.get("username") or "").lstrip("@").lower()
            if phone:
                profiles[f"phone:{phone}"].append(profile)
            if username:
                profiles[f"username:{username}"].append(profile)
        return profiles

    async def _get_metasell_analysis(self, lead_id: int) -> Optional[Dict[str, Any]]:
        if not self.db or not hasattr(self.db, "get_latest_call_analysis"):
            return None
        try:
            return await self.db.get_latest_call_analysis(lead_id)
        except Exception as exc:
            logger.warning(f"[DEAL HYGIENE] MetaSell analysis fetch failed for {lead_id}: {exc}")
            return None

    def _notes_to_text(self, notes: Iterable[Dict[str, Any]]) -> str:
        parts: List[str] = []
        for note in notes or []:
            params = note.get("params") or {}
            text = params.get("text") or params.get("message") or ""
            if not text and params:
                text = " ".join(str(v) for v in params.values() if isinstance(v, (str, int, float)))
            if text:
                parts.append(str(text)[:1000])
        return "\n".join(parts[-30:])

    def _contact_to_text(self, contact: Dict[str, Any]) -> str:
        parts = [str(contact.get("name") or "")]
        for field in contact.get("custom_fields_values") or []:
            parts.append(str(field.get("field_name") or field.get("field_code") or ""))
            for value in field.get("values") or []:
                parts.append(str(value.get("value") or ""))
        return "\n".join(parts)

    def _extract_contact_phones(self, contact: Dict[str, Any]) -> Set[str]:
        phones: Set[str] = set()
        for field in contact.get("custom_fields_values") or []:
            if field.get("field_code") != "PHONE":
                continue
            for value in field.get("values") or []:
                normalized = normalize_phone(value.get("value"))
                if normalized:
                    phones.add(normalized)
        return phones

    def _merge_profile(self, identity: LeadIdentity, profile: Dict[str, Any]) -> None:
        try:
            identity.telegram_user_ids.add(int(profile["user_id"]))
        except (KeyError, TypeError, ValueError):
            pass
        username = str(profile.get("username") or "").lstrip("@").lower()
        if username:
            identity.telegram_usernames.add(username)
        phone = normalize_phone(profile.get("phone"))
        if phone:
            identity.phones.add(phone)

    def _category_from_signals(self, signals: List[DealSignal]) -> str:
        text = " ".join(signal.message.lower() for signal in signals)
        if "shaxsiy" in text or "oila" in text:
            return "personal"
        if "spam" in text or "noto'g'ri raqam" in text:
            return "spam"
        if any(signal.source.startswith("metasell") for signal in signals):
            return "low_quality_lost"
        return "needs_review"

    def _duplicate_probability(self, kind: str, items: List[LeadIdentity]) -> float:
        base = {
            "phone": 0.92,
            "telegram_user_id": 0.96,
            "username": 0.86,
            "contact_id": 0.76,
        }.get(kind, 0.7)
        if any(item.phones for item in items) and any(item.telegram_usernames for item in items):
            base += 0.05
        return min(0.99, round(base, 2))

    def _unique_by_lead(self, items: List[LeadIdentity]) -> List[LeadIdentity]:
        seen: Set[int] = set()
        unique: List[LeadIdentity] = []
        for item in sorted(items, key=lambda x: x.updated_at or 0, reverse=True):
            if item.lead_id in seen:
                continue
            seen.add(item.lead_id)
            unique.append(item)
        return unique

    def _lead_url(self, lead_id: int) -> Optional[str]:
        subdomain = getattr(self.amocrm, "subdomain", "")
        if not subdomain:
            return None
        return f"https://{subdomain}.amocrm.ru/leads/detail/{lead_id}"

    async def _tag_and_note(self, lead_id: int, tag: str, note: str) -> Dict[str, Any]:
        tag_ok = await self.amocrm.add_lead_tag(lead_id, tag)
        note_result = self.amocrm.add_lead_note(lead_id, note)
        return {
            "lead_id": lead_id,
            "action": "tag_and_note",
            "tag": tag,
            "success": bool(tag_ok and note_result),
            "tag_ok": bool(tag_ok),
            "note_ok": bool(note_result),
        }

    async def _create_review_task(self, lead_id: int, text: str) -> Dict[str, Any]:
        result = await self.amocrm.create_task(
            element_id=lead_id,
            text=text,
            complete_till=int(time.time()) + 24 * 60 * 60,
        )
        return {
            "lead_id": lead_id,
            "action": "create_review_task",
            "success": bool(result),
            "metadata": result if isinstance(result, dict) else {},
        }

    def _format_unnecessary_note(self, item: Dict[str, Any]) -> str:
        evidence = "\n".join(f"- {line}" for line in item.get("evidence", [])[:6])
        return (
            "Oisha hygiene audit: sdelka sifati shubhali.\n"
            f"Kategoriya: {item.get('category')}\n"
            f"Ishonch: {item.get('confidence')}\n"
            f"Sabab: {item.get('reason')}\n"
            f"Dalillar:\n{evidence}\n"
            "Avtomatik o'chirish yoki merge qilinmadi. Mas'ul tekshirishi kerak."
        )

    def _format_duplicate_note(self, group: Dict[str, Any]) -> str:
        lead_ids = ", ".join(str(x) for x in group.get("lead_ids", []))
        phones = ", ".join(group.get("phones", []) or ["yo'q"])
        usernames = ", ".join("@" + u for u in group.get("telegram_usernames", []) or [])
        telegram_label = usernames or "yo'q"
        evidence = "\n".join(f"- {line}" for line in group.get("evidence", [])[:6])
        return (
            "Oisha hygiene audit: duplikat sdelka ehtimoli.\n"
            f"Ehtimollik: {group.get('probability')}\n"
            f"Leadlar: {lead_ids}\n"
            f"Telefonlar: {phones}\n"
            f"Telegram: {telegram_label}\n"
            f"Dalillar:\n{evidence}\n"
            "Avtomatik merge qilinmadi. Asosiy sdelkani mas'ul tanlashi kerak."
        )

    def _to_float(self, value: Any) -> Optional[float]:
        try:
            return float(value)
        except (TypeError, ValueError):
            return None
