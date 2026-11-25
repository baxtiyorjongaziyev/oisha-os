"""Conversation-driven automation discovery for OishaSelfDiagnosis.

Inspects recent Telegram/CRM conversation records (read-only) and proposes
concrete, evidence-backed CRM/workflow automations when repeated manual gaps
appear — e.g. clients sharing resumes (hh.uz), emails, or phone numbers in
chat while their CRM cards remain incomplete.
"""
from __future__ import annotations

import logging
import re
from collections import Counter
from typing import Any, List, Tuple

from src.services.core.diagnosis.models import (
    CATEGORY_FEATURE,
    SEVERITY_LOW,
    SEVERITY_MEDIUM,
    ImprovementProposal,
)

logger = logging.getLogger("OishaSelfDiagnosis")

_PATTERNS: Tuple[Tuple[str, re.Pattern[str], str, str, str], ...] = (
    (
        "resume_link",
        re.compile(r"https?://(?:www\.)?hh\.uz/resume/[A-Za-z0-9]+", re.IGNORECASE),
        "Suhbatlarda yuborilgan hh.uz rezyumelarni amoCRM kartochkasiga avtomatik biriktirish",
        "Mijozlar yoki nomzodlar Telegram suhbatida hh.uz rezyume havolasini yubormoqda, lekin u CRM kartochkasiga avtomatik tushmayapti.",
        "tg_amo_bridge/inbound.py ga rezyume havolasini ajratib, amoCRM kontakt/bitim izohiga yoki maxsus maydoniga yozuvchi handler qoʻshing.",
    ),
    (
        "email_address",
        re.compile(r"\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}\b"),
        "Suhbat kontekstidan email manzilini amoCRM kontakt kartochkasiga avtomatik qoʻshish",
        "Mijozlar suhbat davomida email manzilini yozmoqda, lekin u amoCRM kontaktining EMAIL maydoniga avtomatik saqlanmayapti.",
        "phone_enrichment.py namunasida email ajratuvchi va amoCRM kontaktiga EMAIL qoʻshuvchi avtomatizatsiya qoʻshing.",
    ),
    (
        "social_or_site_link",
        re.compile(r"https?://(?:www\.)?(?:instagram\.com|t\.me|linkedin\.com)/[^\s]+", re.IGNORECASE),
        "Suhbatdagi Instagram/LinkedIn havolalarini CRM kartochkasiga avtomatik saqlash",
        "Mijozlar suhbatda ijtimoiy tarmoq havolalarini ulashmoqda, lekin ular CRM kartochkasiga avtomatik tushmayapti.",
        "Suhbat matnidan ijtimoiy tarmoq havolalarini ajratib, amoCRM kontakt izohiga yoki custom field ga yozuvchi modul qoʻshing.",
    ),
)

_MIN_PATTERN_HITS = 2
_MIN_MISSING_PHONE_LINKS = 3
_MIN_REPETITIVE_HITS = 3


def _normalize_phrase(text: str) -> str:
    cleaned = re.sub(r"\s+", " ", str(text or "").strip().lower())
    cleaned = re.sub(r"https?://\S+|\+?\d[\d\s\-()]{6,}", "<val>", cleaned)
    return cleaned[:80].strip()


class ConversationInsightsMixin:
    """Mixin for OishaSelfDiagnosis: discovers automation proposals from real chats."""

    db: Any

    async def _query_rows(self, sql: str, params: list | None = None) -> List[Any]:
        if not self.db or not hasattr(self.db, "execute"):
            return []
        try:
            rows = await self.db.execute(sql, params or [])
            return list(rows or [])
        except Exception as exc:
            logger.debug("[SELF-DIAG] conversation insights query skipped: %s", type(exc).__name__)
            return []

    async def diagnose_conversation_insights(self) -> List[ImprovementProposal]:
        """Scan recent conversations and chat links for recurring CRM automation gaps."""
        proposals: List[ImprovementProposal] = []
        if not self.db:
            return proposals

        # 1. Contacts linked in Telegram without a phone number yet
        missing_rows = await self._query_rows(
            "SELECT COUNT(*) FROM tg_amo_chat_links "
            "WHERE (phone IS NULL OR TRIM(phone) = '') AND linked_contact_id IS NOT NULL"
        )
        missing_count = int(missing_rows[0][0]) if missing_rows and missing_rows[0] else 0
        if missing_count >= _MIN_MISSING_PHONE_LINKS:
            proposals.append(
                ImprovementProposal(
                    id="conv_missing_phone_links",
                    category=CATEGORY_FEATURE,
                    severity=SEVERITY_MEDIUM,
                    title="Telefonsiz Telegram kontaktlaridan raqamni avtomatik soʻrash/boyitish",
                    problem=(
                        f"Hozir {missing_count} ta amoCRM kontaktida Telegram chat ulangan, "
                        "lekin telefon raqami hali kiritilmagan."
                    ),
                    proposed_solution=(
                        "Suhbat kontekstidan telefon raqamini avtomatik aniqlashni (phone_enrichment) "
                        "faol tuting va uzoq vaqt telefonsiz qolgan lidlar uchun menejerga eslatma yuboring."
                    ),
                    affected_files=["src/services/core/crm/tg_amo_bridge/phone_enrichment.py"],
                    suggested_agent="Integration",
                    evidence={
                        "source": "tg_amo_chat_links",
                        "missing_phone_contacts": missing_count,
                    },
                )
            )

        # 2. Recent incoming client messages with structured data not yet automated
        msg_rows = await self._query_rows(
            "SELECT text FROM messages WHERE is_ai = 0 ORDER BY id DESC LIMIT 200"
        )
        texts = [str(r[0] or "") for r in msg_rows if r and r[0]]
        if not texts:
            return proposals

        for key, regex, title, desc, fix in _PATTERNS:
            hits = sum(1 for t in texts if regex.search(t))
            if hits >= _MIN_PATTERN_HITS:
                proposals.append(
                    ImprovementProposal(
                        id=f"conv_pattern_{key}",
                        category=CATEGORY_FEATURE,
                        severity=SEVERITY_MEDIUM if hits >= 5 else SEVERITY_LOW,
                        title=title,
                        problem=f"{desc} (soʻnggi 200 ta xabarda {hits} marta uchradi).",
                        proposed_solution=fix,
                        affected_files=["src/services/core/crm/tg_amo_bridge/inbound.py"],
                        suggested_agent="Integration",
                        evidence={"source": "messages", "pattern": key, "hits": hits},
                    )
                )

        # 3. Repetitive manual tasks & repeated outgoing replies
        proposals.extend(await self._detect_repetitive_work())
        return proposals

    async def _detect_repetitive_work(self) -> List[ImprovementProposal]:
        """Detect repeated manual tasks or repeated replies that can be automated."""
        proposals: List[ImprovementProposal] = []

        # 3a. Repeated tasks in `tasks` table
        task_rows = await self._query_rows(
            "SELECT title FROM tasks ORDER BY id DESC LIMIT 200"
        )
        task_counts = Counter(
            _normalize_phrase(r[0])
            for r in task_rows
            if r and r[0] and len(_normalize_phrase(r[0])) >= 12
        )
        for phrase, count in task_counts.most_common(3):
            if count < _MIN_REPETITIVE_HITS:
                continue
            slug = re.sub(r"[^a-z0-9]+", "_", phrase)[:24].strip("_") or "task"
            proposals.append(
                ImprovementProposal(
                    id=f"rep_task_{slug}",
                    category=CATEGORY_FEATURE,
                    severity=SEVERITY_MEDIUM if count >= 5 else SEVERITY_LOW,
                    title=f"Takroriy vazifani avtomatlashtirish: {phrase[:48]}",
                    problem=(
                        f"\"{phrase[:60]}\" mazmunidagi vazifa soʻnggi 200 ta yozuvda "
                        f"{count} marta takrorlangan."
                    ),
                    proposed_solution=(
                        "Bu takrorlanuvchi ish uchun scheduler yoki trigger asosida "
                        "avtomatik bajaruvchi handler qoʻshishni taklif qilaman."
                    ),
                    affected_files=["src/schedulers/"],
                    suggested_agent="Coordinator",
                    evidence={"source": "tasks", "phrase": phrase, "count": count},
                )
            )

        # 3b. Repeated outgoing replies / questions in `messages`
        out_rows = await self._query_rows(
            "SELECT text FROM messages WHERE is_ai = 0 ORDER BY id DESC LIMIT 200"
        )
        reply_counts = Counter(
            _normalize_phrase(r[0])
            for r in out_rows
            if r and r[0] and len(_normalize_phrase(r[0])) >= 20
        )
        for phrase, count in reply_counts.most_common(2):
            if count < _MIN_REPETITIVE_HITS:
                continue
            slug = re.sub(r"[^a-z0-9]+", "_", phrase)[:24].strip("_") or "msg"
            proposals.append(
                ImprovementProposal(
                    id=f"rep_msg_{slug}",
                    category=CATEGORY_FEATURE,
                    severity=SEVERITY_LOW,
                    title=f"Takroriy soʻrov/savolni avtomatlashtirish: {phrase[:45]}",
                    problem=(
                        f"Suhbatlarda \"{phrase[:60]}\" mazmunidagi murojaat "
                        f"{count} marta takrorlandi."
                    ),
                    proposed_solution=(
                        "Bu takroriy soʻrov uchun avtomatik javob shabloni yoki "
                        "CRM/Telegram workflow qoʻshishni taklif qilaman."
                    ),
                    affected_files=["src/services/core/crm/tg_amo_bridge/inbound.py"],
                    suggested_agent="Integration",
                    evidence={"source": "messages", "phrase": phrase, "count": count},
                )
            )

        return proposals
