"""Gapirish nisbati rolsiz transkripsiyada menejerni jazolamasligi kerak."""

from src.services.ai.quality_analyzer import QualityAnalyzer, QualityMetric
from src.services.utils.transcript import speaker_split, talk_ratio_verdict

# Diarizatsiya rolsiz yorliq bergan haqiqiy format.
GENERIC = (
    "A: Allo, assalomu alaykum.\n"
    "B: Va alaykum assalom, brending narxi qancha?\n"
    "A: Loyihaga qarab, keling aniqlashtiramiz.\n"
    "B: Yaxshi, ertaga gaplashamiz.\n"
)
ROLES = "Mijoz: " + "menga brending kerak " * 20 + "\nSotuvchi: tushundim, aniqlashtiraman"


def test_speaker_split_generic_labels_are_not_attributed():
    first, second, attributed = speaker_split(GENERIC)
    assert attributed is False
    assert first + second == 100
    assert "aniqlanmadi" in talk_ratio_verdict(first, attributed)


def test_speaker_split_role_labels_are_attributed():
    client_pct, _agent_pct, attributed = speaker_split(ROLES)
    assert attributed is True
    assert client_pct > 55


def test_compute_talk_ratio_reports_zero_when_roles_unknown():
    assert QualityAnalyzer._compute_talk_ratio(GENERIC) == (0, 0)


def test_talk_ratio_metric_skipped_instead_of_scored_30():
    analyzer = QualityAnalyzer()
    result = analyzer.analyze_conversation(GENERIC, conversation_id="c1")

    metrics = {s.metric for s in result.scores}
    assert QualityMetric.TALK_RATIO not in metrics
    assert result.talk_ratio_client == 0
    assert result.talk_ratio_agent == 0


def test_skipping_a_metric_does_not_drag_overall_score_down():
    """Chetlab o'tilgan metrik og'irligi qayta normallashtiriladi."""
    analyzer = QualityAnalyzer()
    generic = analyzer.analyze_conversation(GENERIC, conversation_id="c1")

    # Aynan shu suhbat, lekin rollari belgilangan va sotuvchi ustun gapirgan —
    # talk_ratio jazo balli (30) tushadi. Rolsiz variant undan past
    # bo'lmasligi kerak: transkripsiya formati menejer aybi emas.
    seller_heavy = GENERIC.replace("A:", "Sotuvchi:").replace("B:", "Mijoz:")
    seller_heavy += "Sotuvchi: " + "biz juda ko'p gapiramiz " * 20
    penalised = analyzer.analyze_conversation(seller_heavy, conversation_id="c2")

    client_pct, _, attributed = speaker_split(seller_heavy)
    assert attributed is True and client_pct < 40  # jazo sharti bajarilgan
    assert generic.overall_score >= penalised.overall_score


def test_failed_analyses_excluded_from_manager_rating():
    analyzer = QualityAnalyzer()
    good = analyzer.analyze_conversation(ROLES, conversation_id="ok")
    broken = analyzer._create_fallback_analysis(
        conversation_id="err",
        lead_id=None,
        manager_id=1,
        manager_name="Test",
        duration_seconds=0,
    )

    rating = analyzer.get_manager_rating([good, broken])

    assert rating["total_calls"] == 1
    assert rating["average_score"] == good.overall_score
