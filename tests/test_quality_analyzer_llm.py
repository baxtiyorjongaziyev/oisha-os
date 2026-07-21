"""Sifat ballari haqiqiy LLM'dan kelishi va manbasi ochiq bo'lishi kerak.

Ilgari `_ai_analyze` faqat kalit so'z sanardi ("foyda" so'zi uchun +20 ball),
lekin natija oddiy AI bahosi sifatida qaytardi. Endi: Gemini baholaydi,
ishlamasa evristikaga tushadi va `scoring_method` buni aytib turadi.
"""

import json
from types import SimpleNamespace

import pytest

from src.services.ai.quality_analyzer import (
    SCORING_METHOD_AI,
    SCORING_METHOD_HEURISTIC,
    QualityAnalyzer,
    _parse_llm_scores,
)

TRANSCRIPT = (
    "Sotuvchi: Assalomu alaykum, men Jon Branding'dan Sardor.\n"
    "Mijoz: Assalomu alaykum, brending haqida gaplashmoqchi edim.\n"
    "Sotuvchi: Albatta, qaysi yo'nalishda ishlaysiz?\n"
)

LLM_REPLY = {
    "metric_scores": {
        "introduction": 90,
        "need_identification": 80,
        "value_proposition": 70,
        "objection_handling": 60,
        "closing": 50,
        "follow_up": 40,
        "tone": 95,
        "active_listening": 85,
        "question_quality": 75,
    },
    "summary": "Menejer o'zini tanishtirdi va ehtiyojni aniqlay boshladi.",
    "strengths": ["Aniq tanishtirish"],
    "weaknesses": ["Kelishuvga olib chiqilmadi"],
    "client_mood": "positive",
    "client_interest_level": 70,
    "objections": [],
    "outcome": "follow_up",
    "next_steps": ["Taklif yuborish"],
}


def _stub_llm(monkeypatch, raw_text):
    """`generate_content_with_fallback` o'rniga tayyor javob qaytaramiz."""
    calls = {}

    async def fake_generate(client, **kwargs):
        calls["prompt"] = kwargs.get("contents")
        return SimpleNamespace(text=raw_text), "gemini-1.5-flash"

    monkeypatch.setattr(
        "src.services.utils.gemini_fallback.generate_content_with_fallback",
        fake_generate,
    )
    return calls


@pytest.fixture()
def analyzer():
    # Klient obyekt sifatida mavjud, lekin unga hech qachon murojaat qilinmaydi —
    # generate_content_with_fallback stub qilingan.
    return QualityAnalyzer(gemini_client=SimpleNamespace())


@pytest.mark.asyncio
async def test_scores_come_from_the_llm(analyzer, monkeypatch):
    calls = _stub_llm(monkeypatch, json.dumps(LLM_REPLY))

    result = await analyzer.analyze_conversation_ai(TRANSCRIPT, conversation_id="c1")

    assert result.scoring_method == SCORING_METHOD_AI
    assert result.summary == LLM_REPLY["summary"]
    assert result.outcome == "follow_up"
    # Ball LLM raqamlaridan hisoblangan, kalit so'zdan emas.
    by_metric = {s.metric.value: s.score for s in result.scores}
    assert by_metric["introduction"] == 90
    assert by_metric["closing"] == 50
    # Transkripsiya promptga tushgan.
    assert "Jon Branding'dan Sardor" in calls["prompt"]


@pytest.mark.asyncio
async def test_talk_ratio_still_computed_not_guessed(analyzer, monkeypatch):
    """`talk_ratio` LLM'dan emas, transkripsiyadan hisoblanadi."""
    _stub_llm(monkeypatch, json.dumps(LLM_REPLY))

    result = await analyzer.analyze_conversation_ai(TRANSCRIPT, conversation_id="c1")

    assert result.talk_ratio_client + result.talk_ratio_agent == 100


@pytest.mark.asyncio
async def test_falls_back_to_heuristic_when_llm_fails(analyzer, monkeypatch):
    async def boom(client, **kwargs):
        raise RuntimeError("gemini down")

    monkeypatch.setattr(
        "src.services.utils.gemini_fallback.generate_content_with_fallback", boom
    )

    result = await analyzer.analyze_conversation_ai(TRANSCRIPT, conversation_id="c1")

    # Ish to'xtamaydi, lekin ball manbasi yashirilmaydi.
    assert result.scoring_method == SCORING_METHOD_HEURISTIC
    assert result.scores


@pytest.mark.asyncio
async def test_falls_back_when_no_gemini_key(monkeypatch):
    analyzer = QualityAnalyzer()  # klient yo'q
    monkeypatch.setattr(analyzer, "_get_gemini_client", lambda: None)

    result = await analyzer.analyze_conversation_ai(TRANSCRIPT, conversation_id="c1")

    assert result.scoring_method == SCORING_METHOD_HEURISTIC


@pytest.mark.asyncio
async def test_garbage_llm_reply_does_not_produce_fake_scores(analyzer, monkeypatch):
    _stub_llm(monkeypatch, "kechirasiz, javob bera olmayman")

    result = await analyzer.analyze_conversation_ai(TRANSCRIPT, conversation_id="c1")

    assert result.scoring_method == SCORING_METHOD_HEURISTIC


@pytest.mark.asyncio
async def test_sync_method_is_explicitly_heuristic(analyzer):
    result = analyzer.analyze_conversation(TRANSCRIPT, conversation_id="c1")

    assert result.scoring_method == SCORING_METHOD_HEURISTIC


def test_scoring_method_is_exposed_in_payload(analyzer):
    payload = analyzer.analyze_conversation(TRANSCRIPT, conversation_id="c1").to_dict()

    assert payload["scoring_method"] == SCORING_METHOD_HEURISTIC


@pytest.mark.parametrize(
    "raw",
    [
        "",
        "not json at all",
        '{"summary": "metric_scores yo\'q"}',
        '{"metric_scores": "dict emas"}',
    ],
)
def test_parse_llm_scores_rejects_unusable_replies(raw):
    assert _parse_llm_scores(raw) is None


def test_parse_llm_scores_handles_markdown_and_clamps():
    raw = "```json\n" + json.dumps(
        {"metric_scores": {"introduction": 250, "closing": -40, "tone": "yaxshi"}}
    ) + "\n```"

    parsed = _parse_llm_scores(raw)

    assert parsed["metric_scores"]["introduction"] == 100
    assert parsed["metric_scores"]["closing"] == 0
    assert parsed["metric_scores"]["tone"] == 0  # raqam emas → 0
    # So'ralgan barcha metriklar mavjud.
    assert len(parsed["metric_scores"]) == 9
