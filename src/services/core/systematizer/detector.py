"""PatternDetector: Autonomous repetitive action identification and systematization engine."""
from __future__ import annotations

import datetime
import hashlib
import re
from collections import Counter, defaultdict
from typing import Any, Dict, List, Optional, Tuple

import structlog

from src.services.core.systematizer.models import (
    AutomationStrategy,
    DetectedPattern,
    PatternType,
    ProposalStatus,
    SystematizationProposal,
    SystematizationReport,
)

logger = structlog.get_logger()

# Predefined high-value canonical intent signals in Jon Branding operations
CANONICAL_FAQ_MAP: Dict[str, Tuple[str, List[str]]] = {
    "pricing_inquiry": (
        "Xizmat narxlarini so'rash",
        ["narxi", "qancha", "nechpul", "narxlar", "narxlari", "skolko", "price", "stoimost"],
    ),
    "portfolio_request": (
        "Portfolio va oldingi ishlarni ko'rish",
        ["portfolio", "namuna", "ishlar", "keys", "primer", "keyslar", "misol"],
    ),
    "service_catalog": (
        "Brending va dizayn xizmatlari ro'yxati",
        ["xizmatlar", "logotip", "brending", "rebrending", "aydentika", "brandbook"],
    ),
    "timeline_inquiry": (
        "Loyiha tayyor bo'lish muddatini bilish",
        ["qachon", "muddat", "necha kunda", "srok", "vaqt", "qancha vaqt"],
    ),
}

CANONICAL_TASK_MAP: Dict[str, Tuple[str, List[str]]] = {
    "commercial_proposal": (
        "Tijorat taklifi (KP) tayyorlash",
        ["kp", "tijorat taklifi", "kompred", "taklif tayyorlash", "proposal"],
    ),
    "contract_and_invoice": (
        "Shartnoma va hisob-faktura rasmiylashtirish",
        ["shartnoma", "dogovor", "hisob-faktura", "invoys", "akt"],
    ),
    "briefing_intake": (
        "Mijozdan brief olish va anketani to'ldirish",
        ["brief", "brif", "so'rovnoma", "anketa", "savolnoma"],
    ),
    "design_revisions": (
        "Dizayn variantlariga o'zgartirish va tuzatishlar",
        ["pravka", "tuzatish", "variant", "eskiz", "redaktsiya"],
    ),
}

CANONICAL_OBJECTION_MAP: Dict[str, Tuple[str, List[str]]] = {
    "price_objection": (
        "Qimmatlik yoki byudjet cheklovi e'tirozi",
        ["qimmat", "byudjet yetmaydi", "dorogo", "arzonroq", "chegirma"],
    ),
    "stagnant_thinking": (
        "O'ylab ko'rish va qaror qabul qilishni cho'zish",
        ["o'ylab", "keyinroq", "rahbar bilan", "podumayem", "vaqt kerak"],
    ),
    "no_contact": (
        "Mijoz bilan aloqa yo'qolishi",
        ["ko'tarmadi", "javob bermadi", "ne otvechaet", "aloqaga chiqmadi"],
    ),
}


class PatternDetector:
    """Detects repeating team behaviors and drafts automated systems."""

    def __init__(self, min_frequency_threshold: int = 2) -> None:
        self.min_freq = min_frequency_threshold

    @staticmethod
    def normalize_text(text: str) -> str:
        """Strip punctuation, special chars, and normalize casing while preserving apostrophes."""
        if not text:
            return ""
        cleaned = re.sub(r"['`’‘]", "'", str(text).lower())
        cleaned = re.sub(r"[^\w\s\d']", " ", cleaned)
        return re.sub(r"\s+", " ", cleaned).strip()

    def _match_signals(
        self, text: str, signal_map: Dict[str, Tuple[str, List[str]]]
    ) -> Optional[Tuple[str, str]]:
        """Match text against a signal keyword map."""
        normalized = self.normalize_text(text)
        if not normalized:
            return None
        words = set(normalized.split())
        for key, (title, keywords) in signal_map.items():
            for kw in keywords:
                norm_kw = self.normalize_text(kw)
                if norm_kw and (norm_kw in words if " " not in norm_kw
                                else f" {norm_kw} " in f" {normalized} "):
                    return key, title
        return None

    def detect_message_patterns(
        self, messages: List[Dict[str, Any]]
    ) -> List[DetectedPattern]:
        """Group and detect high-frequency message patterns."""
        grouped: Dict[str, Dict[str, Any]] = defaultdict(
            lambda: {"title": "", "texts": [], "senders": set(), "timestamps": []}
        )

        for m in messages:
            text = m.get("text") or m.get("message_text") or ""
            sender = str(m.get("user_id") or m.get("sender") or "unknown")
            ts_val = m.get("created_at")
            match = self._match_signals(text, CANONICAL_FAQ_MAP)

            if match:
                key, title = match
                grouped[key]["title"] = title
                grouped[key]["texts"].append(text)
                grouped[key]["senders"].add(sender)
                if ts_val:
                    grouped[key]["timestamps"].append(ts_val)

        patterns = []
        for key, data in grouped.items():
            count = len(data["texts"])
            if count >= self.min_freq:
                p_id = f"pat_msg_{key}_{hashlib.sha256(key.encode()).hexdigest()[:8]}"
                pattern = DetectedPattern(
                    pattern_id=p_id,
                    pattern_type=PatternType.FAQ_QUESTION,
                    title=data["title"],
                    frequency=count,
                    sample_texts=data["texts"][:5],
                    interlocutors=list(data["senders"]),
                    impact_score=round(count * 0.75, 2),
                    confidence=0.92,
                    suggested_strategy=AutomationStrategy.AI_AUTO_REPLY,
                )
                patterns.append(pattern)

        return sorted(patterns, key=lambda x: x.frequency, reverse=True)

    def detect_task_patterns(
        self, tasks: List[Dict[str, Any]]
    ) -> List[DetectedPattern]:
        """Detect repetitive task definitions that can be templated."""
        grouped: Dict[str, Dict[str, Any]] = defaultdict(
            lambda: {"title": "", "texts": [], "assignees": set()}
        )

        for t in tasks:
            title_text = t.get("title") or t.get("description") or ""
            assignee = str(t.get("assigned_to") or "unassigned")
            match = self._match_signals(title_text, CANONICAL_TASK_MAP)

            if match:
                key, canonical_title = match
                grouped[key]["title"] = canonical_title
                grouped[key]["texts"].append(title_text)
                grouped[key]["assignees"].add(assignee)

        patterns = []
        for key, data in grouped.items():
            count = len(data["texts"])
            if count >= self.min_freq:
                p_id = f"pat_task_{key}_{hashlib.sha256(key.encode()).hexdigest()[:8]}"
                pattern = DetectedPattern(
                    pattern_id=p_id,
                    pattern_type=PatternType.ROUTINE_TASK,
                    title=data["title"],
                    frequency=count,
                    sample_texts=data["texts"][:5],
                    interlocutors=list(data["assignees"]),
                    impact_score=round(count * 1.5, 2),
                    confidence=0.88,
                    suggested_strategy=AutomationStrategy.TASK_TEMPLATE,
                )
                patterns.append(pattern)

        return sorted(patterns, key=lambda x: x.frequency, reverse=True)

    def detect_finance_patterns(
        self, transactions: List[Dict[str, Any]]
    ) -> List[DetectedPattern]:
        """Detect recurring merchants, subscriptions, or uncategorized expenses."""
        merchant_counter: Counter[str] = Counter()
        merchant_samples: Dict[str, List[str]] = defaultdict(list)

        for tx in transactions:
            merchant = str(tx.get("merchant") or "").strip()
            raw_text = str(tx.get("raw_text") or merchant)
            if merchant:
                norm_m = self.normalize_text(merchant)
                merchant_counter[norm_m] += 1
                merchant_samples[norm_m].append(raw_text)

        patterns = []
        for m_name, count in merchant_counter.most_common():
            if count >= self.min_freq:
                p_id = f"pat_fin_{hashlib.sha256(m_name.encode()).hexdigest()[:8]}"
                pattern = DetectedPattern(
                    pattern_id=p_id,
                    pattern_type=PatternType.FINANCE_EXPENSE,
                    title=f"Takroriy to'lov: {m_name.title()}",
                    frequency=count,
                    sample_texts=merchant_samples[m_name][:5],
                    impact_score=round(count * 0.5, 2),
                    confidence=0.95,
                    suggested_strategy=AutomationStrategy.FINANCE_RULE,
                )
                patterns.append(pattern)

        return patterns

    def detect_crm_patterns(
        self, leads: List[Dict[str, Any]]
    ) -> List[DetectedPattern]:
        """Detect repetitive deal objections or lost reasons."""
        grouped: Dict[str, Dict[str, Any]] = defaultdict(
            lambda: {"title": "", "texts": [], "leads": []}
        )

        for lead in leads:
            notes = str(lead.get("loss_reason") or lead.get("notes") or "")
            lead_id = str(lead.get("id") or "")
            match = self._match_signals(notes, CANONICAL_OBJECTION_MAP)

            if match:
                key, title = match
                grouped[key]["title"] = title
                grouped[key]["texts"].append(notes)
                grouped[key]["leads"].append(lead_id)

        patterns = []
        for key, data in grouped.items():
            count = len(data["texts"])
            if count >= self.min_freq:
                p_id = f"pat_crm_{key}_{hashlib.sha256(key.encode()).hexdigest()[:8]}"
                pattern = DetectedPattern(
                    pattern_id=p_id,
                    pattern_type=PatternType.CRM_OBJECTION,
                    title=data["title"],
                    frequency=count,
                    sample_texts=data["texts"][:5],
                    interlocutors=data["leads"],
                    impact_score=round(count * 2.0, 2),
                    confidence=0.85,
                    suggested_strategy=AutomationStrategy.CRM_TRIGGER,
                )
                patterns.append(pattern)

        return patterns

    def generate_proposals(
        self, patterns: List[DetectedPattern]
    ) -> List[SystematizationProposal]:
        """Turn detected patterns into actionable systematization blueprints."""
        proposals = []
        now = datetime.datetime.now(datetime.timezone.utc)

        for pat in patterns:
            prop_id = f"prop_{pat.pattern_id[4:]}"
            strategy = pat.suggested_strategy

            if strategy == AutomationStrategy.AI_AUTO_REPLY:
                blueprint = (
                    f"Oisha Telegram botida '{pat.title}' bo'yicha Gemini 1.5 Flash "
                    f"orqali avtomatik 3 bosqichli javob va portfolio yuborish oqimini yoqish."
                )
                target = "src/services/core/telegram/streaming.py"
            elif strategy == AutomationStrategy.TASK_TEMPLATE:
                blueprint = (
                    f"'{pat.title}' amalini standartlashtirish: 1 klik bilan 3 ta aniq "
                    f"sub-vazifa va SLA biriktiriluvchi shablon tizimini yoqish."
                )
                target = "src/services/core/smart_tasks/"
            elif strategy == AutomationStrategy.FINANCE_RULE:
                blueprint = (
                    f"Hisobchi AI xotirasiga avtomatik qoida o'rgatish: bu merchant to'lovi "
                    f"kelganda tasdiq so'ramasdan tegishli toifaga avto-joylash."
                )
                target = "src/services/core/finance/engine/rules.py"
            else:
                blueprint = (
                    f"AmoCRM pipeline'ida '{pat.title}' yuz berganda avtomatik "
                    f"reaktivatsiya va muzokarachi skriptini ishga tushirish."
                )
                target = "src/services/core/pipeline/"

            proposal = SystematizationProposal(
                proposal_id=prop_id,
                pattern_id=pat.pattern_id,
                title=f"Avtomatlashtirish: {pat.title}",
                strategy=strategy,
                problem_statement=f"Jamoa ushbu operatsiyani {pat.frequency} marta qo'lda takrorlagan.",
                solution_blueprint=blueprint,
                time_saved_weekly_minutes=None,
                target_skill_or_handler=target,
                status=ProposalStatus.PENDING,
                created_at=now,
            )
            proposals.append(proposal)

        return proposals

    def run_audit(
        self,
        messages: Optional[List[Dict[str, Any]]] = None,
        tasks: Optional[List[Dict[str, Any]]] = None,
        transactions: Optional[List[Dict[str, Any]]] = None,
        leads: Optional[List[Dict[str, Any]]] = None,
    ) -> SystematizationReport:
        """Run complete multi-source pattern detection audit."""
        msgs = messages or []
        tsks = tasks or []
        txs = transactions or []
        lds = leads or []

        all_patterns: List[DetectedPattern] = []
        all_patterns.extend(self.detect_message_patterns(msgs))
        all_patterns.extend(self.detect_task_patterns(tsks))
        all_patterns.extend(self.detect_finance_patterns(txs))
        all_patterns.extend(self.detect_crm_patterns(lds))

        proposals = self.generate_proposals(all_patterns)

        return SystematizationReport(
            audit_timestamp=datetime.datetime.now(datetime.timezone.utc),
            scanned_messages_count=len(msgs),
            scanned_tasks_count=len(tsks),
            scanned_finance_count=len(txs),
            scanned_crm_count=len(lds),
            patterns=all_patterns,
            proposals=proposals,
        )

    def export_skill_markdown(self, proposal: SystematizationProposal) -> str:
        """Format an automation proposal into standard SKILL.md specification."""
        clean_name = re.sub(r"[^\w\-]", "-", proposal.title.lower())
        clean_name = re.sub(r"-+", "-", clean_name).strip("-")
        return (
            f"---\n"
            f"name: {clean_name}\n"
            f"description: Auto-generated SOP from PatternDetector for '{proposal.title}'.\n"
            f"---\n\n"
            f"# {proposal.title}\n\n"
            f"## Muammo va takroriylik tahlili\n"
            f"{proposal.problem_statement}\n\n"
            f"## Tavsiya etilgan arxitektura\n"
            f"{proposal.solution_blueprint}\n\n"
            f"## Tejash samaradorligi\n"
            f"{self._savings_text(proposal)}\n\n"
            f"## Texnik integratsiya nuqtasi\n"
            f"`{proposal.target_skill_or_handler}`\n"
        )

    @staticmethod
    def _savings_text(proposal: SystematizationProposal) -> str:
        if proposal.time_saved_weekly_minutes is None:
            return "Noma'lum: kuzatuv davri va har bir amal davomiyligi tasdiqlanmagan."
        return f"Haftasiga taxminan {proposal.time_saved_weekly_minutes} daqiqa."
