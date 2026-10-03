from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest

from src.services.core.crm.auditor import classifier
from src.services.core.crm.auditor.classifier import ClassifierMixin


def _auditor(client=object()):
    auditor = ClassifierMixin.__new__(ClassifierMixin)
    auditor.genai_client = client
    auditor.model_name = "gemini-test"
    return auditor


async def _classify(monkeypatch, response=None, error=None, **history):
    mock = AsyncMock(return_value=(response, "m"), side_effect=error)
    monkeypatch.setattr(classifier, "generate_content_with_fallback", mock)
    kwargs = dict(lead_name="L", contact_name="C", phone="1", username="u",
                  call_summary="", telegram_history="")
    kwargs.update(history)
    return await _auditor().classify_contact(**kwargs), mock


async def test_without_client_returns_default():
    result = await _auditor(None).classify_contact("L", "C", "1", "u", "", "")
    assert result == ("Boshqa", "Gemini API sozlanmagan. Standart toifa 'Boshqa' deb tanlandi.", "", "", "")


async def test_valid_json_response(monkeypatch):
    text = '{"category": "Mijoz", "explanation": "E", "detailed_summary": "S", "next_step_task": "T", "telegram_draft_reply": "D"}'
    result, mock = await _classify(monkeypatch, SimpleNamespace(text=text), call_summary="x" * 5000)
    assert result == ("Mijoz", "E", "S", "T", "D")
    call = mock.await_args
    assert call.kwargs["primary_model"] == "gemini-test"
    assert call.kwargs["env_name"] == "GEMINI_CRM_AUDIT_FALLBACK_MODELS"
    assert call.kwargs["log_prefix"] == "[AUDITOR_GEMINI]"
    assert len(call.kwargs["contents"]) == 1


@pytest.mark.parametrize("text,expected", [
    ('noise {"category": "Kandidat"} tail', ("Kandidat", "Sabab taqdim etilmadi.",
     "Tizim tomonidan avtomatik tahlil: Sabab taqdim etilmadi.",
     "Mijoz bilan bog'lanib, holatni aniqlashtiring.", "")),
    ('{"category": "Nomalum", "explanation": "X"}', ("Boshqa", "X",
     "Tizim tomonidan avtomatik tahlil: X", "Mijoz bilan bog'lanib, holatni aniqlashtiring.", "")),
    ("", ("Boshqa", "Sabab taqdim etilmadi.", "Tizim tomonidan avtomatik tahlil: Sabab taqdim etilmadi.",
          "Mijoz bilan bog'lanib, holatni aniqlashtiring.", "")),
])
async def test_lenient_parsing(monkeypatch, text, expected):
    result, _ = await _classify(monkeypatch, SimpleNamespace(text=text))
    assert result == expected


@pytest.mark.parametrize("history,category,task", [
    ({"telegram_history": "Bu JUNK"}, "Boshqa", ""),
    ({"call_summary": "rezyume yubordim"}, "Kandidat", ""),
    ({"group_history": "logo narxi"}, "Mijoz", "Mijoz bilan bog'lanib, keyingi kelishuvlarni aniqlashtiring."),
    ({"notes_history": "salom"}, "Boshqa", "Mijoz bilan bog'lanib, keyingi kelishuvlarni aniqlashtiring."),
])
async def test_rules_fallback_on_error(monkeypatch, history, category, task):
    result, _ = await _classify(monkeypatch, error=RuntimeError("boom"), **history)
    assert result == (
        category,
        "Xatolik tufayli qoida bo'yicha saralandi (Fallback): boom",
        f"Mijoz va uning yozishmalari tahlili xatolik tufayli yakunlanmadi. Aloqa toifasi: {category}.",
        task,
        "",
    )


async def test_unparseable_text_falls_back(monkeypatch):
    result, _ = await _classify(monkeypatch, SimpleNamespace(text="{broken"))
    assert result == ("Boshqa", "Sabab taqdim etilmadi.", "Tizim tomonidan avtomatik tahlil: Sabab taqdim etilmadi.",
                      "Mijoz bilan bog'lanib, holatni aniqlashtiring.", "")
