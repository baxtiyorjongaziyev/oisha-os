"""Tests for AUTO_LEAD_MODE lead gating and DM image vision analysis."""

import json
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock

import pytest

from src.handlers.message_handler import _pop_vision_context, should_open_lead
from src.services.core.dm_vision import (
    analyze_dm_image,
    format_for_ai_context,
    format_for_crm_note,
)


# ---------------------------------------------------------------------------
# should_open_lead
# ---------------------------------------------------------------------------


def test_strict_mode_requires_is_lead():
    opened, reason = should_open_lead(
        {"is_lead": False, "intent_category": "HOT_LEAD"}, "narx qancha?", "strict"
    )
    assert opened is False
    assert reason == "strict_no_lead"

    opened, reason = should_open_lead({"is_lead": True}, "narx qancha?", "strict")
    assert opened is True
    assert reason == "is_lead"


def test_balanced_opens_on_intent_signal_without_is_lead():
    """AI 'is_lead' bermasa ham, biror intent bo'lsa balanced ochadi."""
    opened, reason = should_open_lead(
        {"is_lead": False, "intent_category": "POTENTIAL"}, "salom", "balanced"
    )
    assert opened is True
    assert reason == "intent_potential"


def test_balanced_skips_when_no_signal():
    opened, reason = should_open_lead(
        {"is_lead": False, "intent_category": "NO_SIGNAL"}, "salom", "balanced"
    )
    assert opened is False
    assert reason == "no_signal"


@pytest.mark.parametrize(
    "text",
    [
        "mening raqamim +998 90 123 45 67",
        "aloqa: +998901234567",
        "yozing: client@example.com",
        "998901234567 ga qo'ng'iroq qiling",
    ],
)
def test_contact_in_message_always_opens_in_balanced(text):
    """Mijoz o'zi kontakt qoldirsa — AI nima deganidan qat'i nazar ochiladi."""
    opened, reason = should_open_lead(
        {"is_lead": False, "intent_category": "NO_SIGNAL"}, text, "balanced"
    )
    assert opened is True
    assert reason == "contact_in_message"


def test_contact_hint_does_not_override_strict_mode():
    opened, reason = should_open_lead(
        {"is_lead": False, "intent_category": "NO_SIGNAL"},
        "+998901234567",
        "strict",
    )
    assert opened is False
    assert reason == "strict_no_lead"


def test_all_mode_opens_any_substantive_message():
    opened, reason = should_open_lead(
        {"is_lead": False, "intent_category": "NO_SIGNAL"}, "salom", "all"
    )
    assert opened is True
    assert reason == "all_mode"


def test_all_mode_still_skips_empty_message():
    opened, reason = should_open_lead({}, "  ", "all")
    assert opened is False
    assert reason == "empty_message"


def test_missing_lead_data_is_tolerated():
    """AI ishlamay qolsa (None), balanced signalga tayanadi va yiqilmaydi."""
    opened, _ = should_open_lead(None, "+998901234567", "balanced")
    assert opened is True

    opened, reason = should_open_lead(None, "salom", "balanced")
    assert opened is False
    assert reason == "no_signal"


def test_unknown_mode_falls_back_to_balanced():
    opened, reason = should_open_lead(
        {"is_lead": False, "intent_category": "WARM_LEAD"}, "salom", "nonsense"
    )
    assert opened is True
    assert reason == "intent_warm_lead"


# ---------------------------------------------------------------------------
# dm_vision
# ---------------------------------------------------------------------------


def _vision_client(payload, *, wrap_markdown=False, generate_side_effect=None):
    """
    Gemini client mock.

    `aio` atributi ataylab None: generate_content_with_fallback avval
    client.aio.models ni qidiradi, va oddiy MagicMock'da u avtomatik mavjud
    bo'lib qolgani uchun sinaladigan sync yo'l chetlab o'tilardi.
    """
    text = json.dumps(payload) if isinstance(payload, (dict, list)) else payload
    if wrap_markdown:
        text = f"```json\n{text}\n```"

    client = SimpleNamespace(
        aio=None,
        files=SimpleNamespace(
            upload=MagicMock(return_value=SimpleNamespace(uri="files/abc"))
        ),
        models=SimpleNamespace(
            generate_content=MagicMock(
                side_effect=generate_side_effect,
                return_value=SimpleNamespace(text=text),
            )
        ),
    )
    return client


@pytest.mark.asyncio
async def test_analyze_dm_image_parses_and_normalizes():
    client = _vision_client(
        {
            "summary": "Logotip referensi — minimalist qora-oq belgi",
            "category": "reference_design",
            "extracted_text": "JON BRANDING",
            "contact": {"name": "Ali", "phone": "+998901234567", "company": ""},
            "is_business_relevant": True,
            "sales_hint": "Uslub yoqqanini so'ra",
        }
    )

    result = await analyze_dm_image(client, "photo.jpg")

    assert result is not None
    assert result["category"] == "reference_design"
    assert result["is_business_relevant"] is True
    assert result["contact"]["phone"] == "+998901234567"
    # Bo'sh maydon saqlanadi, lekin contact dict yo'qolmaydi
    assert result["contact"]["company"] == ""


@pytest.mark.asyncio
async def test_analyze_dm_image_strips_markdown_fence():
    client = _vision_client(
        {"summary": "Chek rasmi", "category": "receipt", "is_business_relevant": True},
        wrap_markdown=True,
    )

    result = await analyze_dm_image(client, "photo.jpg")

    assert result is not None
    assert result["summary"] == "Chek rasmi"


@pytest.mark.asyncio
async def test_analyze_dm_image_drops_empty_contact():
    client = _vision_client(
        {
            "summary": "Shaxsiy foto",
            "category": "personal",
            "contact": {"name": "", "phone": "", "company": ""},
            "is_business_relevant": False,
        }
    )

    result = await analyze_dm_image(client, "photo.jpg")

    assert result["contact"] == {}
    assert result["is_business_relevant"] is False


@pytest.mark.asyncio
async def test_analyze_dm_image_returns_none_on_non_json():
    """Matnli fallback provayder rasmni ko'rmaydi — erkin matn tashlab yuboriladi."""
    client = _vision_client("Kechirasiz, men rasmni ko'ra olmayman.")

    assert await analyze_dm_image(client, "photo.jpg") is None


@pytest.mark.asyncio
async def test_analyze_dm_image_returns_none_on_non_text_response():
    """Javob obyekti matn bermasa, json.loads ga berilmasligi kerak."""
    client = _vision_client(None)
    client.models.generate_content = MagicMock(
        return_value=SimpleNamespace(text=object())
    )

    assert await analyze_dm_image(client, "photo.jpg") is None


@pytest.mark.asyncio
async def test_analyze_dm_image_survives_upload_failure():
    client = _vision_client({"summary": "x"})
    client.files.upload = MagicMock(side_effect=RuntimeError("upload down"))

    assert await analyze_dm_image(client, "photo.jpg") is None


@pytest.mark.asyncio
async def test_analyze_dm_image_survives_generate_failure(monkeypatch):
    """Barcha provayder yiqilsa, analyze_dm_image None qaytaradi — ko'tarmaydi.

    Non-Gemini fallback ataylab o'chirilgan: aks holda "quota" xatosi transient
    deb hisoblanib, test haqiqiy tarmoq chaqiruviga chiqib ketadi.
    """
    monkeypatch.setattr(
        "src.services.utils.gemini_fallback._non_gemini_fallback",
        AsyncMock(return_value=None),
    )
    client = _vision_client(
        {"summary": "x"}, generate_side_effect=RuntimeError("quota exhausted")
    )

    assert await analyze_dm_image(client, "photo.jpg") is None


@pytest.mark.asyncio
async def test_analyze_dm_image_requires_client_and_path():
    assert await analyze_dm_image(None, "photo.jpg") is None
    assert await analyze_dm_image(_vision_client({"summary": "x"}), "") is None


def test_format_for_crm_note_includes_contact_and_text():
    note = format_for_crm_note(
        {
            "summary": "Vizitka",
            "category": "business_card",
            "extracted_text": "Ali Valiyev, Direktor",
            "contact": {"name": "Ali Valiyev", "phone": "+998901234567", "company": "ABC"},
            "sales_hint": "Raqamni CRM ga yoz",
        },
        "Ali",
    )

    assert "business_card" in note
    assert "+998901234567" in note
    assert "Kompaniya: ABC" in note
    assert "Ali Valiyev, Direktor" in note


def test_format_for_ai_context_is_single_line():
    context = format_for_ai_context(
        {
            "summary": "Raqobatchi ishi",
            "extracted_text": "Brand X",
            "sales_hint": "Farqni tushuntir",
        }
    )

    assert "\n" not in context
    assert context.startswith("[Mijoz rasm yubordi]")
    assert "Brand X" in context


# ---------------------------------------------------------------------------
# vision context cache
# ---------------------------------------------------------------------------


def test_pop_vision_context_is_consumed_once():
    from src.context import app_ctx

    app_ctx.dm_vision_context = {42: {"text": "[Mijoz rasm yubordi] logo", "message_id": 1}}

    assert _pop_vision_context(42) == "[Mijoz rasm yubordi] logo"
    # Ikkinchi chaqiruv bo'sh — eski rasm keyingi javobga ergashmaydi
    assert _pop_vision_context(42) is None


def test_pop_vision_context_handles_missing_cache():
    from src.context import app_ctx

    app_ctx.dm_vision_context = {}
    assert _pop_vision_context(999) is None
