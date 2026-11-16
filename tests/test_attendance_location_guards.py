"""Telegram lokatsiya orqali davomat: soxta/eski/forward lokatsiya rad etiladi."""
from datetime import datetime, timedelta, timezone
from types import SimpleNamespace

import pytest

from src.services.core.dispatcher import handlers_attendance as h

NOW = datetime(2026, 11, 16, 10, 0, tzinfo=timezone.utc)


def _loc(**kw):
    base = dict(latitude=41.3, longitude=69.2, live_period=3600, horizontal_accuracy=15.0)
    base.update(kw)
    return SimpleNamespace(**base)


def _msg(**kw):
    base = dict(date=NOW - timedelta(seconds=5), edit_date=None, forward_origin=None, forward_date=None)
    base.update(kw)
    return SimpleNamespace(**base)


def test_live_fresh_location_ok():
    assert h.location_rejection(_msg(), _loc(), edited=False, now=NOW) is None


def test_static_pin_without_accuracy_rejected():
    assert h.location_rejection(_msg(), _loc(live_period=None, horizontal_accuracy=None),
                                edited=False, now=NOW) == "no_accuracy"


def test_keldim_button_location_ok():
    # request_location tugmasi: live_period yo'q, lekin joriy GPS aniqligi bor
    assert h.location_rejection(_msg(), _loc(live_period=None), edited=False, now=NOW) is None


def test_forwarded_rejected():
    assert h.location_rejection(_msg(forward_origin=object()), _loc(), edited=False, now=NOW) == "forwarded"
    assert h.location_rejection(_msg(forward_date=NOW), _loc(), edited=False, now=NOW) == "forwarded"


def test_missing_or_zero_accuracy_rejected():
    assert h.location_rejection(_msg(), _loc(horizontal_accuracy=None), edited=False, now=NOW) == "no_accuracy"
    assert h.location_rejection(_msg(), _loc(horizontal_accuracy=0), edited=False, now=NOW) == "no_accuracy"


def test_stale_rejected():
    old = _msg(date=NOW - timedelta(seconds=h.MAX_LOCATION_AGE_S + 30))
    assert h.location_rejection(old, _loc(), edited=False, now=NOW) == "stale"


def test_edited_uses_edit_date_and_skips_live_period():
    fresh = _msg(date=NOW - timedelta(hours=1), edit_date=NOW - timedelta(seconds=3))
    assert h.location_rejection(fresh, _loc(live_period=None), edited=True, now=NOW) is None
    stale = _msg(date=NOW - timedelta(hours=1), edit_date=NOW - timedelta(minutes=10))
    assert h.location_rejection(stale, _loc(), edited=True, now=NOW) == "stale"


@pytest.mark.asyncio
async def test_rejected_location_never_reaches_on_location(monkeypatch):
    from src.services.core.attendance import auto_presence

    called = []

    async def fake_on_location(*a, **k):
        called.append(a)

    monkeypatch.setattr(auto_presence, "on_location", fake_on_location)
    answers = []

    async def answer(text, **kw):
        answers.append(text)

    msg = _msg(chat=SimpleNamespace(type="private"), from_user=SimpleNamespace(id=1),
               location=_loc(live_period=None, horizontal_accuracy=None), answer=answer)
    await h.handle_location(msg, edited=False)
    assert called == []
    assert answers and "/keldim" in answers[0]


@pytest.mark.asyncio
async def test_keldim_sends_request_location_button():
    sent = []

    async def answer(text, **kw):
        sent.append(kw)

    msg = SimpleNamespace(chat=SimpleNamespace(type="private"), from_user=SimpleNamespace(id=1), answer=answer)
    await h.handle_keldim(msg)
    button = sent[0]["reply_markup"].keyboard[0][0]
    assert button.request_location is True
