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
async def test_http_error_page_is_treated_as_end():
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
    assert stats["completed"] is True


@pytest.mark.asyncio
async def test_leads_without_id_are_skipped():
    analyzer, _ = _analyzer({1: [{"name": "id yo'q"}, {"id": 7}], 2: []})

    stats = await analyzer.backfill_call_recordings(limit=100)

    assert stats["leads_scanned"] == 1
