"""
Deal classification, duplicate scoring, and CRM cleanup task formatting mixin.
"""
from __future__ import annotations

from collections import defaultdict
import logging
import re
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Set, Tuple

from src.services.core.hygiene.models import (
    HARD_NOISE_KEYWORDS,
    METASELL_LOST_OUTCOMES,
    SYSTEM_TAGS,
    DealHygieneFinding,
    DealSignal,
    DuplicateDealFinding,
    LeadIdentity,
    _safe_ts,
    _to_float,
)

logger = logging.getLogger("AmoCRMDealHygiene")


class ClassifierMixin:
    """Classifies invalid/stale deals and detects duplicate CRM leads."""

    _to_float = staticmethod(_to_float)

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
        from src.utils.task_scheduler import task_deadline

        result = await self.amocrm.create_task(
            element_id=lead_id,
            text=text,
            complete_till=task_deadline(due_in_hours=24),
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

