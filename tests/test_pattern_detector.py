"""Unit tests for PatternDetector and Systematizer engine."""
import pytest
from src.services.core.systematizer import (
    AutomationStrategy,
    DetectedPattern,
    PatternDetector,
    PatternType,
    ProposalStatus,
    SystematizationReport,
)


@pytest.fixture
def detector() -> PatternDetector:
    return PatternDetector(min_frequency_threshold=2)


def test_normalize_text(detector: PatternDetector):
    raw = "  Assalomu alaykum! Narxi qancha bo'ladi???  "
    normalized = detector.normalize_text(raw)
    assert normalized == "assalomu alaykum narxi qancha bo'ladi"
    assert detector.normalize_text("") == ""
    assert detector.normalize_text(None) == ""


def test_detect_message_patterns_faq(detector: PatternDetector):
    messages = [
        {"user_id": 101, "text": "Salom, logotip narxi qancha bo'ladi?", "created_at": "2026-10-18T10:00:00"},
        {"user_id": 102, "text": "Brending narxlari qanaqa?", "created_at": "2026-10-18T10:15:00"},
        {"user_id": 103, "text": "Iltimos portfolio va oldingi ishlaringizni tashlang", "created_at": "2026-10-18T10:20:00"},
        {"user_id": 104, "text": "Portfolio bormi ko'rsatsangiz", "created_at": "2026-10-18T10:30:00"},
        {"user_id": 105, "text": "Rahmat yaxshi", "created_at": "2026-10-18T10:35:00"},
    ]

    patterns = detector.detect_message_patterns(messages)
    assert len(patterns) >= 2

    pricing_pat = next(p for p in patterns if "narx" in p.title.lower())
    assert pricing_pat.frequency == 2
    assert pricing_pat.pattern_type == PatternType.FAQ_QUESTION
    assert pricing_pat.suggested_strategy == AutomationStrategy.AI_AUTO_REPLY
    assert len(pricing_pat.interlocutors) == 2

    portfolio_pat = next(p for p in patterns if "portfolio" in p.title.lower())
    assert portfolio_pat.frequency == 2


def test_detect_task_patterns(detector: PatternDetector):
    tasks = [
        {"title": "Mijozga KP tayyorlash va yuborish", "assigned_to": 1},
        {"title": "Yangi brending bo'yicha KP tayyorlash", "assigned_to": 2},
        {"title": "Kompaniya uchun tijorat taklifi yozish", "assigned_to": 1},
        {"title": "Shartnoma va hisob-faktura rasmiylashtirish", "assigned_to": 3},
        {"title": "Shartnoma tayyorlash", "assigned_to": 3},
    ]

    patterns = detector.detect_task_patterns(tasks)
    assert len(patterns) >= 2

    kp_pat = next(p for p in patterns if "kp" in p.title.lower() or "taklif" in p.title.lower())
    assert kp_pat.frequency == 3
    assert kp_pat.pattern_type == PatternType.ROUTINE_TASK
    assert kp_pat.suggested_strategy == AutomationStrategy.TASK_TEMPLATE


def test_detect_finance_patterns(detector: PatternDetector):
    transactions = [
        {"merchant": "YANDEX GO", "raw_text": "Yandex Go taxi xizmati 25000 UZS"},
        {"merchant": "YANDEX GO", "raw_text": "Yandex Go taxi xizmati 32000 UZS"},
        {"merchant": "FIGMA.COM", "raw_text": "Figma monthly subscription $15"},
        {"merchant": "FIGMA.COM", "raw_text": "Figma monthly subscription $15"},
        {"merchant": "KORZINKA", "raw_text": "Bir martalik xarid"},
    ]

    patterns = detector.detect_finance_patterns(transactions)
    assert len(patterns) == 2

    merchants = [p.title.lower() for p in patterns]
    assert any("yandex" in m for m in merchants)
    assert any("figma" in m for m in merchants)
    assert all(p.suggested_strategy == AutomationStrategy.FINANCE_RULE for p in patterns)


def test_detect_crm_patterns(detector: PatternDetector):
    leads = [
        {"id": 501, "loss_reason": "Mijoz xizmat qimmat deb aytdi, byudjeti yetmaydi"},
        {"id": 502, "loss_reason": "Juda qimmat deyishdi"},
        {"id": 503, "loss_reason": "O'ylab ko'ramiz deyishdi, qaror qilinmadi"},
        {"id": 504, "loss_reason": "Hali o'ylab ko'rishmoqchi"},
    ]

    patterns = detector.detect_crm_patterns(leads)
    assert len(patterns) == 2

    objection_pat = next(p for p in patterns if "qimmat" in p.title.lower())
    assert objection_pat.frequency == 2
    assert objection_pat.pattern_type == PatternType.CRM_OBJECTION
    assert objection_pat.suggested_strategy == AutomationStrategy.CRM_TRIGGER


def test_generate_proposals(detector: PatternDetector):
    pattern = DetectedPattern(
        pattern_id="pat_msg_pricing_123456",
        pattern_type=PatternType.FAQ_QUESTION,
        title="Xizmat narxlarini so'rash",
        frequency=5,
        sample_texts=["Narxi qancha?", "Necha pul?"],
        impact_score=3.75,
        suggested_strategy=AutomationStrategy.AI_AUTO_REPLY,
    )

    proposals = detector.generate_proposals([pattern])
    assert len(proposals) == 1
    prop = proposals[0]

    assert prop.proposal_id == "prop_msg_pricing_123456"
    assert prop.strategy == AutomationStrategy.AI_AUTO_REPLY
    assert prop.status == ProposalStatus.PENDING
    assert prop.time_saved_weekly_minutes > 0
    assert "Gemini 1.5 Flash" in prop.solution_blueprint


def test_run_audit_end_to_end(detector: PatternDetector):
    messages = [
        {"text": "Narxi qancha?"},
        {"text": "Narxi qancha bo'ladi?"},
    ]
    tasks = [
        {"title": "Mijozga KP tayyorlash"},
        {"title": "KP tayyorlash"},
    ]
    transactions = [
        {"merchant": "Yandex Go"},
        {"merchant": "Yandex Go"},
    ]
    leads = [
        {"loss_reason": "Mijoz juda qimmat dedi"},
        {"loss_reason": "Qimmat deb rad etildi"},
    ]

    report = detector.run_audit(
        messages=messages,
        tasks=tasks,
        transactions=transactions,
        leads=leads,
    )

    assert isinstance(report, SystematizationReport)
    assert report.total_scanned_items == 8
    assert len(report.patterns) == 4
    assert len(report.proposals) == 4
    assert report.estimated_time_saved_hours_weekly > 0

    d = report.to_dict()
    assert d["total_scanned_items"] == 8
    assert "scanned_breakdown" in d


def test_export_skill_markdown(detector: PatternDetector):
    pattern = DetectedPattern(
        pattern_id="pat_task_kp_abcdef",
        pattern_type=PatternType.ROUTINE_TASK,
        title="Tijorat taklifi tayyorlash",
        frequency=4,
        suggested_strategy=AutomationStrategy.TASK_TEMPLATE,
    )
    proposals = detector.generate_proposals([pattern])
    skill_md = detector.export_skill_markdown(proposals[0])

    assert "---" in skill_md
    assert "name: avtomatlashtirish-tijorat-taklifi-tayyorlash" in skill_md
    assert "Tijorat taklifi tayyorlash" in skill_md
    assert "Muammo va takroriylik tahlili" in skill_md
    assert "Tejash samaradorligi" in skill_md
