"""Rasmiy playbook — bitta manba, ikkala baholovchi ham shundan o'qiydi."""

from src.services.core.sales_playbook import (
    SCORE_RED,
    STAGE_WEIGHTS,
    category_for_score,
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
