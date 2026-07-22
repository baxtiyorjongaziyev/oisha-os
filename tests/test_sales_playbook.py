"""Rasmiy playbook — bitta manba, ikkala baholovchi ham shundan o'qiydi."""

from src.services.core.sales_playbook import (
    SCORE_RED,
    STAGE_METRICS,
    STAGE_WEIGHTS,
    category_for_score,
    metric_weights,
    rubric_prompt_uz,
)


def test_rubric_contains_agreed_rules():
    """Rahbariyat bilan kelishilgan asosiy qoidalar promptda bor."""
    text = rubric_prompt_uz()

    # Salomlashish: ism + kompaniya majburiy, "qayerdan topdingiz" shartli
    assert "Jon Branding" in text
    assert "BIRINCHI qo'ng'iroqda" in text
    # Narx faqat vilka
    assert "vilka" in text
    # Byudjet birinchi qo'ng'iroqda jazolanmaydi
    assert "KAMAYTIRILMAYDI" in text
    # "O'ylab ko'raman" — muddat + qayta qo'ng'iroq majburiy
    assert "O'ylab ko'raman" in text
    # Yakunlash: 4 ta maqbul natija
    assert "uchrashuv sanasi" in text
    assert "KP yuborish" in text
    # Taqiqlar
    assert "Raqobatchilarni yomonlash" in text
    assert "Savdo ustiga savdo" in text
    # 3 daqiqa qoidasi
    assert "3 daqiqa" in text


def test_stage_weights_sum_and_priorities():
    """E'tiroz va yakunlash — eng og'ir bosqichlar."""
    assert STAGE_WEIGHTS["etirozlar"] == STAGE_WEIGHTS["yakunlash"] == 2.0
    assert max(STAGE_WEIGHTS.values()) == 2.0
    assert len(STAGE_WEIGHTS) == 6


def test_category_thresholds():
    assert category_for_score(95) == "excellent"
    assert category_for_score(80) == "good"
    assert category_for_score(65) == "average"
    assert category_for_score(45) == "poor"
    assert category_for_score(SCORE_RED - 1) == "critical"


def test_call_analyzer_prompt_uses_playbook():
    """AmoCRM qo'ng'iroq tahlilchisi promptida eski qo'lda yozilgan rubrik emas,
    playbook matni ishlatilishini bilvosita tekshiramiz: rubric matni playbook
    funksiyasidan keladi."""
    import inspect

    from src.services.core import call_analyzer

    src = inspect.getsource(call_analyzer)
    assert "rubric_prompt_uz()" in src
    # Eski inline rubrik qaytib kelmasin
    assert "Brif yuborish yoki to'ldirish kelishildi mi" not in src


def test_quality_analyzer_prompt_uses_playbook():
    from src.services.ai.quality_analyzer import _build_scoring_prompt

    prompt = _build_scoring_prompt("Salom")

    assert "RASMIY SOTUV RUBRIKASI" in prompt
    assert "vilka" in prompt
    # Metriklar playbook bosqichlariga bog'langan
    assert "5-bosqich" in prompt


def test_both_analyzers_share_identical_rubric():
    """Ikki baholovchida ikki xil mezon bo'lishi mumkin emas."""
    from src.services.ai.quality_analyzer import _build_scoring_prompt

    rubric = rubric_prompt_uz()
    assert rubric in _build_scoring_prompt("test")


def test_every_metric_belongs_to_exactly_one_stage():
    from src.services.ai.quality_analyzer import QualityMetric

    mapped = [m for metrics in STAGE_METRICS.values() for m in metrics]

    assert sorted(mapped) == sorted(m.value for m in QualityMetric)
    assert len(mapped) == len(set(mapped)), "metrik ikki bosqichga tegishli bo'lolmaydi"
    assert set(STAGE_METRICS) == set(STAGE_WEIGHTS)


def test_metric_weights_normalised_and_follow_stage_priorities():
    weights = metric_weights()

    assert abs(sum(weights.values()) - 1.0) < 1e-9
    # E'tiroz (2.0) salomlashishdan (1.0) aynan 2 barobar og'ir
    assert abs(weights["objection_handling"] / weights["introduction"] - 2.0) < 1e-9
    # Bosqich og'irligi metriklari orasida teng bo'linadi
    assert abs(weights["closing"] - weights["follow_up"]) < 1e-9


def test_quality_analyzer_weights_come_from_playbook():
    """Regressiya: og'irliklar qo'lda yozilib qolgan edi, x2 urg'u yo'qolardi."""
    from src.services.ai.quality_analyzer import QualityAnalyzer, QualityMetric

    weights = QualityAnalyzer.DEFAULT_WEIGHTS

    assert weights == {QualityMetric(k): v for k, v in metric_weights().items()}

    # Playbook e'lon qilgan urg'u BOSQICH darajasida qo'llanadi. Metrikani
    # yakka solishtirib bo'lmaydi: `yakunlash` ikkiga bo'linadi (closing +
    # follow_up), shuning uchun har biri alohida kichikroq ko'rinadi.
    def stage_total(stage: str) -> float:
        return sum(weights[QualityMetric(m)] for m in STAGE_METRICS[stage])

    total = sum(STAGE_WEIGHTS.values())
    for stage, stage_weight in STAGE_WEIGHTS.items():
        assert abs(stage_total(stage) - stage_weight / total) < 1e-9

    # E'tiroz va yakunlash (2.0) ehtiyoj va qiymatdan (1.5) og'irroq
    assert stage_total("etirozlar") > stage_total("ehtiyojlar")
    assert stage_total("yakunlash") > stage_total("qiymat")
    assert abs(stage_total("etirozlar") / stage_total("salomlashish") - 2.0) < 1e-9


def test_both_scoring_paths_agree_on_the_same_call():
    """Bir xil bosqich ballari ikki yo'lda ham bir xil umumiy ball berishi kerak."""
    from src.services.ai.quality_analyzer import QualityAnalyzer

    # Har bosqich bo'yicha bir xil ball -> ikkala usul ham o'sha ballni beradi.
    stage_score = 80

    # call_analyzer yo'li: bosqich og'irliklari bilan
    total_weight = sum(STAGE_WEIGHTS.values())
    call_analyzer_score = round(
        sum(stage_score * w for w in STAGE_WEIGHTS.values()) / total_weight
    )

    # quality_analyzer yo'li: metrik og'irliklari bilan
    analyzer = QualityAnalyzer()
    scores = analyzer._calculate_scores(
        {"metric_scores": {m.value: stage_score for m in analyzer.weights}}
    )
    quality_analyzer_score = analyzer._calculate_overall_score(scores)

    assert call_analyzer_score == quality_analyzer_score == stage_score
