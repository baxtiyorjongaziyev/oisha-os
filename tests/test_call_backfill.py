"""Tarixiy backfill testlari — eski qo'ng'iroq yozuvlarini tahlil qilish.

NIMA UCHUN: `_run_amocrm_call_backfill` (api_server + amocrm_integration)
`analyzer.backfill_call_recordings(...)` ni chaqirardi, lekin bunday metod
CallAnalyzer'da YO'Q edi. AttributeError `except Exception` ichida yutilib,
holat "xato" deb yozilardi — ya'ni "eski yozuvlarni eshitish" hech qachon
ishlamagan. Quyidagi testlar shu holat qaytmasligini ta'minlaydi.
"""

from unittest.mock import AsyncMock, MagicMock

import pytest

from src.services.core.call_analyzer import CallAnalyzer


class _Resp:
    def __init__(self, leads, status=200):
        self.status_code = status
        self._leads = leads

    def json(self):
        return {"_embedded": {"leads": self._leads}}


def _analyzer(pages, state=None):
    """`pages` — sahifa raqami -> lidlar ro'yxati."""
    state = state if state is not None else {}
    amocrm = MagicMock()
    amocrm.base_url = "https://example.invalid"
    amocrm._request_with_auth = MagicMock(
        side_effect=lambda *a, **kw: _Resp(pages.get(kw["params"]["page"], []))
    )
    db = MagicMock()
    db.get_state = AsyncMock(side_effect=lambda k, d="": state.get(k, d))
    db.set_state = AsyncMock(side_effect=lambda k, v: state.__setitem__(k, v))

    analyzer = CallAnalyzer(
        amocrm=amocrm, voice_processor=MagicMock(), db=db, gemini_client=None
    )
    analyzer._load_persisted_cooldown = AsyncMock()
    analyzer.process_call_recordings_for_lead = AsyncMock(return_value=1)
    return analyzer, state


# ── Metod umuman mavjudligi ──────────────────────────────────────────────


def test_backfill_method_exists():
    """Chaqiruvchi kod aynan shu nomni kutadi."""
    assert callable(getattr(CallAnalyzer, "backfill_call_recordings", None))


# ── Sahifalash va tarix bo'ylab yurish ───────────────────────────────────


@pytest.mark.asyncio
async def test_walks_pages_until_history_is_exhausted():
    analyzer, _ = _analyzer({1: [{"id": 1}, {"id": 2}], 2: [{"id": 3}], 3: []})

    stats = await analyzer.backfill_call_recordings(limit=100)

    assert stats["leads_scanned"] == 3
    assert stats["calls_processed"] == 3
    assert stats["completed"] is True
    assert stats["stopped_reason"] == "history_exhausted"


@pytest.mark.asyncio
async def test_resumes_from_saved_page():
    """Ikkinchi yugurish birinchisi to'xtagan joydan davom etadi."""
    analyzer, state = _analyzer(
        {1: [{"id": i} for i in range(10)], 2: [{"id": 99}], 3: []}
    )

    first = await analyzer.backfill_call_recordings(limit=5)

    assert first["stopped_reason"] == "limit_reached"
    assert state["call_analyzer:backfill_next_page"] == str(first["next_page"])

    second = await analyzer.backfill_call_recordings(limit=100)
    assert second["start_page"] == first["next_page"]


@pytest.mark.asyncio
async def test_history_end_wraps_back_to_first_page():
    """Tarix tugagach keyingi yugurish boshidan — oradagi yangi bitimlar uchun."""
    analyzer, state = _analyzer({1: []})

    stats = await analyzer.backfill_call_recordings(limit=10)

    assert stats["next_page"] == 1
    assert state["call_analyzer:backfill_next_page"] == "1"
    assert "call_analyzer:backfill_completed_at" in state


# ── Chegaralar ───────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_stops_at_limit():
    analyzer, _ = _analyzer({1: [{"id": i} for i in range(50)]})

    stats = await analyzer.backfill_call_recordings(limit=3)

    assert stats["calls_processed"] == 3
    assert stats["stopped_reason"] == "limit_reached"


@pytest.mark.asyncio
async def test_respects_max_pages_per_run():
    analyzer, _ = _analyzer({p: [{"id": p}] for p in range(1, 30)})

    stats = await analyzer.backfill_call_recordings(limit=1000, max_pages_per_run=3)

    assert stats["pages_read"] == 3


@pytest.mark.asyncio
async def test_gemini_cooldown_defers_the_whole_run():
    """Kvota tugagan bo'lsa umuman boshlanmaydi — behuda so'rov yubormaymiz."""
    analyzer, _ = _analyzer({1: [{"id": 1}]})
    analyzer._defer_calls_without_fallback = MagicMock(return_value=True)

    stats = await analyzer.backfill_call_recordings(limit=10)

    assert stats["calls_processed"] == 0
    assert stats["stopped_reason"] == "gemini_quota_cooldown"
    analyzer.process_call_recordings_for_lead.assert_not_awaited()


@pytest.mark.asyncio
async def test_cooldown_midway_saves_progress():
    analyzer, state = _analyzer({1: [{"id": i} for i in range(5)], 2: [{"id": 9}]})
    calls = {"n": 0}

    def _defer():
        calls["n"] += 1
        return calls["n"] > 3  # bir necha lidddan keyin kvota tugaydi

    analyzer._defer_calls_without_fallback = _defer

    stats = await analyzer.backfill_call_recordings(limit=100)

    assert stats["stopped_reason"] == "gemini_quota_cooldown"
    assert "call_analyzer:backfill_next_page" in state


# ── Chidamlilik ──────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_one_broken_lead_does_not_stop_the_run():
    analyzer, _ = _analyzer({1: [{"id": 1}, {"id": 2}, {"id": 3}], 2: []})
    analyzer.process_call_recordings_for_lead = AsyncMock(
        side_effect=[RuntimeError("amocrm down"), 1, 1]
    )

    stats = await analyzer.backfill_call_recordings(limit=100)

    assert stats["leads_scanned"] == 3
    assert stats["calls_processed"] == 2


@pytest.mark.asyncio
async def test_http_error_page_is_not_treated_as_end():
    """PR #475 review (P2): HTTP xato "tarix tugadi" deb yozilmasligi kerak.

    Ilgari 401/429/5xx bo'sh sahifa bilan bir xil ishlov olardi —
    `completed=True` yozilardi va kursor 1-sahifaga qaytardi, ya'ni
    monitoring "muvaffaqiyat" ko'rardi-yu, tarixning aksariyati hech
    qachon o'qilmasdi. Endi bunday holat alohida sabab bilan belgilanadi
    va kursor joyida qoladi.
    """
    amocrm = MagicMock()
    amocrm.base_url = "https://example.invalid"
    amocrm._request_with_auth = MagicMock(return_value=_Resp([], status=402))
    db = MagicMock()
    db.get_state = AsyncMock(return_value="1")
    db.set_state = AsyncMock()
    analyzer = CallAnalyzer(amocrm=amocrm, voice_processor=MagicMock(), db=db, gemini_client=None)
    analyzer._load_persisted_cooldown = AsyncMock()

    stats = await analyzer.backfill_call_recordings(limit=10)

    assert stats["calls_processed"] == 0
    assert stats["completed"] is False
    assert stats["stopped_reason"] == "page_fetch_failed"


@pytest.mark.asyncio
async def test_leads_without_id_are_skipped():
    analyzer, _ = _analyzer({1: [{"name": "id yo'q"}, {"id": 7}], 2: []})

    stats = await analyzer.backfill_call_recordings(limit=100)

    assert stats["leads_scanned"] == 1


# ── PR #475 review: backfill nuqsonlari ──────────────────────────────────
#
# Uchta P1/P2 topilma merge'dan KEYIN keldi. Har biri backfill'ni
# jimgina zararli qilardi, shuning uchun har biriga alohida test.


def _failing_analyzer(status_by_page, state=None):
    """`status_by_page` — sahifa raqami -> HTTP status (yoki Exception)."""
    state = state if state is not None else {}
    amocrm = MagicMock()
    amocrm.base_url = "https://example.invalid"

    def _request(*a, **kw):
        page = kw["params"]["page"]
        outcome = status_by_page.get(page, 200)
        if isinstance(outcome, Exception):
            raise outcome
        return _Resp([{"id": page * 10}] if outcome == 200 else [], status=outcome)

    amocrm._request_with_auth = MagicMock(side_effect=_request)
    db = MagicMock()
    db.get_state = AsyncMock(side_effect=lambda k, d="": state.get(k, d))
    db.set_state = AsyncMock(side_effect=lambda k, v: state.__setitem__(k, v))
    analyzer = CallAnalyzer(
        amocrm=amocrm, voice_processor=MagicMock(), db=db, gemini_client=None
    )
    analyzer._load_persisted_cooldown = AsyncMock()
    analyzer.process_call_recordings_for_lead = AsyncMock(return_value=1)
    return analyzer, state


@pytest.mark.asyncio
async def test_http_error_is_not_reported_as_history_exhausted():
    """429/5xx "tarix tugadi" DEGANI EMAS.

    Aks holda backfill muvaffaqiyat deb yozilardi, kursor 1-sahifaga
    qaytardi va tarixning qolgani hech qachon o'qilmasdi.
    """
    analyzer, state = _failing_analyzer({1: 429})
    stats = await analyzer.backfill_call_recordings(limit=10)

    assert stats["completed"] is False
    assert stats["stopped_reason"] == "page_fetch_failed"
    assert stats["failed_page"] == 1
    # Kursor joyida — keyingi yugurish o'sha sahifadan davom etadi.
    assert state.get("call_analyzer:backfill_next_page") == "1"
    assert "call_analyzer:backfill_done_at" not in state


@pytest.mark.asyncio
async def test_network_exception_keeps_the_cursor_where_it_was():
    analyzer, state = _failing_analyzer(
        {3: ConnectionError("tarmoq yiqildi")},
        state={"call_analyzer:backfill_next_page": "3"},
    )
    stats = await analyzer.backfill_call_recordings(limit=10)

    assert stats["stopped_reason"] == "page_fetch_failed"
    assert stats["completed"] is False
    assert state["call_analyzer:backfill_next_page"] == "3"


@pytest.mark.asyncio
async def test_empty_page_still_means_history_exhausted():
    """204/bo'sh sahifa — bu HAQIQIY tugash, xato emas."""
    analyzer, state = _failing_analyzer({1: 204})
    stats = await analyzer.backfill_call_recordings(limit=10)

    assert stats["completed"] is True
    assert stats["stopped_reason"] == "history_exhausted"
    assert state["call_analyzer:backfill_next_page"] == "1"


@pytest.mark.asyncio
async def test_fetch_page_returns_none_on_failure_and_list_on_success():
    """`None` va `[]` bir xil narsa emas — farq butun mantiqni ushlab turadi."""
    analyzer, _ = _failing_analyzer({1: 200, 2: 500, 3: 204})

    assert await analyzer._fetch_leads_page(1) == [{"id": 10}]
    assert await analyzer._fetch_leads_page(2) is None
    assert await analyzer._fetch_leads_page(3) == []


@pytest.mark.asyncio
async def test_min_duration_defaults_to_configured_threshold():
    """Qisqa yozuvlar (avtojavob, band signali) tahlil qilinmasligi kerak.

    Webhook yo'li `AMOCRM_CALL_ANALYSIS_MIN_DURATION_SECONDS` beradi;
    backfill esa `0` yuborib, shu himoyani o'chirib qo'yardi.
    """
    from src.settings import settings

    analyzer, _ = _analyzer({1: [{"id": 1}], 2: []})
    await analyzer.backfill_call_recordings(limit=1)

    kwargs = analyzer.process_call_recordings_for_lead.await_args.kwargs
    assert kwargs["min_call_duration_seconds"] == (
        settings.AMOCRM_CALL_ANALYSIS_MIN_DURATION_SECONDS
    )
    assert kwargs["min_call_duration_seconds"] > 0


@pytest.mark.asyncio
async def test_explicit_zero_still_disables_the_duration_guard():
    """Ataylab "hammasini ol" deyish imkoniyati saqlanadi."""
    analyzer, _ = _analyzer({1: [{"id": 1}], 2: []})
    await analyzer.backfill_call_recordings(limit=1, min_call_duration_seconds=0)

    kwargs = analyzer.process_call_recordings_for_lead.await_args.kwargs
    assert kwargs["min_call_duration_seconds"] == 0


@pytest.mark.asyncio
async def test_each_lead_is_capped_at_the_remaining_allowance():
    """Bitta bitimda 40 ta yozuv bo'lsa ham, limit=5 bo'lsa 5 tadan oshmaydi."""
    analyzer, _ = _analyzer({1: [{"id": 1}], 2: []})
    await analyzer.backfill_call_recordings(limit=5)

    kwargs = analyzer.process_call_recordings_for_lead.await_args.kwargs
    assert kwargs["max_calls_per_lead"] == 5


@pytest.mark.asyncio
async def test_remaining_allowance_shrinks_after_each_lead():
    analyzer, _ = _analyzer({1: [{"id": 1}, {"id": 2}, {"id": 3}], 2: []})
    analyzer.process_call_recordings_for_lead = AsyncMock(return_value=2)

    await analyzer.backfill_call_recordings(limit=6)

    caps = [
        call.kwargs["max_calls_per_lead"]
        for call in analyzer.process_call_recordings_for_lead.await_args_list
    ]
    # 6 → 4 → 2: har safar qolgan kvota beriladi, hech qachon oshmaydi.
    assert caps == [6, 4, 2]


@pytest.mark.asyncio
async def test_cap_never_drops_below_one():
    """Kvota tugagach sikl to'xtaydi — 0 yoki manfiy cap uzatilmaydi."""
    analyzer, _ = _analyzer({1: [{"id": 1}, {"id": 2}], 2: []})
    analyzer.process_call_recordings_for_lead = AsyncMock(return_value=5)

    await analyzer.backfill_call_recordings(limit=3)

    caps = [
        call.kwargs["max_calls_per_lead"]
        for call in analyzer.process_call_recordings_for_lead.await_args_list
    ]
    assert all(cap >= 1 for cap in caps)
