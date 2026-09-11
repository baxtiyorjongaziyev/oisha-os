"""AmoCRM refresh guard: parallel rotatsiya + SIGKILL holatlarida sinmasligi.

Bu qatlam ikkita production nosozlikni yopadi:

1. Ikki instance bir vaqtda refresh qilса — biri rotatsiyani yutadi,
   ikkinchisi bekor bo'lgan token bilan HTTP 400 oladi. Guard 400'da
   darrov bloklamay, bardavom joydan (mock: ``reload_freshest``) yangiroq
   tokenни oladi.
2. Refresh 200 qaytdi-yu, process SIGKILL bilan o'ldi — yangi token
   allaqachon DB'ga yozilgan bo'lsa keyingi start uzilmaydi. Bu yerda
   ``_save_token`` DB'ni fayldan oldin yozishini tekshiramiz.
"""

import time

import pytest

from src.services.core.crm.amocrm.refresh_guard import (
    _access_token_still_valid,
    refresh_with_guard,
)


def _future(seconds: int = 3600) -> dict:
    return {"access_token": "AT", "refresh_token": "RT", "expires_at": time.time() + seconds}


def test_valid_db_token_short_circuits_http_refresh():
    """Lock ostida bardavom joyda yangi token bo'lsa — HTTP refresh chaqirilmaydi."""
    applied = {}
    calls = {"http": 0}

    def do_refresh():
        calls["http"] += 1
        return True

    ok = refresh_with_guard(
        do_refresh=do_refresh,
        reload_freshest=lambda: _future(),
        apply_token=applied.update,
    )

    assert ok is True
    assert calls["http"] == 0
    assert applied.get("access_token") == "AT"


def test_http_4xx_recovers_from_freshest_reload():
    """HTTP refresh 4xx (False) qaytsa — DB'da yangiroq token bo'lsa o'sha ishlatiladi."""
    applied = {}
    seq = iter([None, _future()])  # 1: lock ostida eski/yo'q, 2: refreshdan keyin yangi

    ok = refresh_with_guard(
        do_refresh=lambda: False,
        reload_freshest=lambda: next(seq),
        apply_token=applied.update,
    )

    assert ok is True
    assert applied.get("access_token") == "AT"


def test_all_sources_stale_returns_false():
    """HTTP ham, bardavom joy ham yaroqsiz — blok signali (False)."""
    ok = refresh_with_guard(
        do_refresh=lambda: False,
        reload_freshest=lambda: None,
        apply_token=lambda _d: None,
    )
    assert ok is False


def test_reload_exception_is_swallowed():
    """reload_freshest xato tashlasa — guard yiqilmaydi, HTTP refresh'ga o'tadi."""
    def boom():
        raise RuntimeError("db down")

    ok = refresh_with_guard(
        do_refresh=lambda: True,
        reload_freshest=boom,
        apply_token=lambda _d: None,
    )
    assert ok is True


def test_access_token_validity_checks():
    assert _access_token_still_valid(_future(3600)) is True
    assert _access_token_still_valid({"access_token": "AT", "expires_at": time.time() - 10}) is False
    assert _access_token_still_valid({"expires_at": time.time() + 9999}) is False  # no access_token
    assert _access_token_still_valid(None) is False
    assert _access_token_still_valid({"access_token": "AT"}) is False  # no expires_at


@pytest.mark.asyncio
async def test_save_token_writes_db_before_file(monkeypatch, tmp_path):
    """SIGKILL-proof tartib: _save_token DB'ni fayldan OLDIN yozadi."""
    from src.services.core.crm.amocrm_sync import AmoCRMSync

    order = []

    amocrm = AmoCRMSync(
        "jonbranding", "cid", "csecret", "https://x.test/cb",
        token_file=str(tmp_path / "amocrm_token.json"),
    )
    monkeypatch.setattr(amocrm, "_persist_token_to_db", lambda: order.append("db"))

    real_makedirs = __import__("os").makedirs

    def tracking_makedirs(*a, **k):
        order.append("file")
        return real_makedirs(*a, **k)

    monkeypatch.setattr("src.services.core.crm.amocrm.auth.os.makedirs", tracking_makedirs)

    amocrm._save_token({"access_token": "new-at", "refresh_token": "new-rt", "expires_at": time.time() + 3600})

    assert order[0] == "db", f"DB fayldan oldin yozilishi kerak, tartib: {order}"
    assert amocrm.access_token == "new-at"
