"""`/api/ai/conversion/*` yo'llari engine'ning haqiqiy API'siga ulanganini tekshiradi."""
from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest
from fastapi.responses import JSONResponse

from src.api.routes.ai_analytics_pkg import conversion


class _FakeVolume:
    def to_dict(self):
        return {"manager_name": "Aziz", "total": 3}


class _FakeEngine:
    async def team_summary(self, days):
        return {"days": days, "total_calls": 4}

    async def conversion_trend(self, days):
        return SimpleNamespace(to_dict=lambda: {"days": days, "current_rate": 25.0})

    async def fetch_volumes(self, days):
        return {"Aziz": _FakeVolume(), "__team__": _FakeVolume()}

    async def diagnose_all(self, days):
        return [
            SimpleNamespace(
                manager_name="Aziz",
                to_dict=lambda: {"manager_name": "Aziz"},
            )
        ]

    def build_seller_card(self, diagnosis, volume=None):
        return f"card:{diagnosis.manager_name}:{volume is not None}"


@pytest.mark.asyncio
async def test_overview_uses_team_summary(monkeypatch):
    monkeypatch.setattr(conversion, "_engine", lambda: _FakeEngine())

    result = await conversion.get_conversion_overview(days=7)

    assert result == {"success": True, "overview": {"days": 7, "total_calls": 4}}


@pytest.mark.asyncio
async def test_trend_serializes_dataclass(monkeypatch):
    monkeypatch.setattr(conversion, "_engine", lambda: _FakeEngine())

    result = await conversion.get_conversion_trend(days=30)

    assert result == {
        "success": True,
        "trend": {"days": 30, "current_rate": 25.0},
    }


@pytest.mark.asyncio
async def test_volume_serializes_every_manager(monkeypatch):
    monkeypatch.setattr(conversion, "_engine", lambda: _FakeEngine())

    result = await conversion.get_conversion_volume(days=30)

    assert result["success"] is True
    assert result["volume"]["Aziz"] == {"manager_name": "Aziz", "total": 3}
    assert result["volume"]["__team__"] == {"manager_name": "Aziz", "total": 3}


@pytest.mark.asyncio
async def test_seller_card_found(monkeypatch):
    monkeypatch.setattr(conversion, "_engine", lambda: _FakeEngine())

    result = await conversion.get_seller_card(seller_name="Aziz", days=30)

    assert result["success"] is True
    assert result["seller_name"] == "Aziz"
    assert result["card"] == "card:Aziz:True"
    assert result["diagnosis"] == {"manager_name": "Aziz"}


@pytest.mark.asyncio
async def test_seller_card_unknown_returns_404(monkeypatch):
    monkeypatch.setattr(conversion, "_engine", lambda: _FakeEngine())

    result = await conversion.get_seller_card(seller_name="Yo'q", days=30)

    assert isinstance(result, JSONResponse)
    assert result.status_code == 404


@pytest.mark.asyncio
async def test_missing_db_returns_503(monkeypatch):
    monkeypatch.setattr(conversion.api_state, "db_instance", None)

    result = await conversion.get_conversion_overview(days=30)

    assert isinstance(result, JSONResponse)
    assert result.status_code == 503


def test_sync_days_accepts_dates_and_caps_window():
    assert conversion._sync_days({"start_date": "2026-01-01", "end_date": "2026-01-10"}) == 10
    assert conversion._sync_days({"days": 500}) == 366
    assert conversion._sync_days({}) == 90


@pytest.mark.asyncio
async def test_sync_revenue_wires_db_and_amocrm(monkeypatch):
    from src.context import app_ctx
    from src.services.core import metasell_revenue

    calls = {}

    class FakeSync:
        def __init__(self, db, amocrm):
            calls["db"] = db
            calls["amocrm"] = amocrm

        async def sync(self, days):
            calls["days"] = days
            return SimpleNamespace(to_dict=lambda: {"checked": 2})

    db = object()
    amocrm = object()
    monkeypatch.setattr(conversion.api_state, "db_instance", db)
    monkeypatch.setattr(app_ctx, "amocrm", amocrm, raising=False)
    monkeypatch.setattr(metasell_revenue, "MetaSellRevenueSync", FakeSync)

    request = SimpleNamespace(json=AsyncMock(return_value={"days": 15}))
    result = await conversion.sync_revenue(request)

    assert result == {"success": True, "result": {"checked": 2}}
    assert calls == {"db": db, "amocrm": amocrm, "days": 15}
