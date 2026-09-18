import asyncio
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import AsyncMock

from src.api.routes.marketing_dashboard import get_marketing_performance
from src.services.core.uzbek_call_queue import CallQueueManager, QueuedCall


ROOT = Path(__file__).resolve().parents[1]


def test_marketing_endpoint_returns_real_attribution_shape():
    """Meta Ads spend + AmoCRM attribution ulangandan keyin endpoint endi
    RuntimeError/503 otmaydi — real (bo'sh bo'lsa ham) hisob-kitob qaytaradi."""
    result = asyncio.run(get_marketing_performance("2026-07-01", "2026-07-14"))
    assert result["start_date"] == "2026-07-01"
    assert result["end_date"] == "2026-07-14"
    assert isinstance(result["campaigns"], list)
    totals = result["totals"]
    for key in ("spend", "leads", "cost_per_lead", "deals_won", "revenue_won", "roas"):
        assert key in totals


def test_call_queue_sends_real_operator_notification():
    db = SimpleNamespace(
        execute=AsyncMock(return_value=[{"telegram_id": 99801}]),
        commit=AsyncMock(),
    )
    bot = SimpleNamespace(send_message=AsyncMock())
    manager = CallQueueManager(db=db, bot_client=bot)
    call = QueuedCall(
        id=7,
        entrepreneur_id=1,
        entrepreneur_name="Ali",
        entrepreneur_phone="+998901234567",
        priority=10,
        status="assigned",
        assigned_operator_id=2,
        queued_at="2026-07-14T09:00:00",
        started_at=None,
        completed_at=None,
    )

    assert asyncio.run(manager.notify_operator(2, call)) is True
    bot.send_message.assert_awaited_once()


def test_call_queue_reports_failure_without_bot_client(monkeypatch):
    db = SimpleNamespace(
        execute=AsyncMock(return_value=[{"telegram_id": 99801}]),
        commit=AsyncMock(),
    )
    manager = CallQueueManager(db=db)
    monkeypatch.setattr("src.context.app_ctx.bot_client", None)
    call = QueuedCall(7, 1, "Ali", "+99890", 10, "assigned", 2, "now", None, None)

    assert asyncio.run(manager.notify_operator(2, call)) is False


def test_nginx_exposes_all_health_variants_without_basic_auth():
    config = (ROOT / "deploy" / "nginx-oisha.conf").read_text(encoding="utf-8")
    assert "location ~ ^/(healthz|readyz)/?$" in config
    health_location = config.split("location ~ ^/(healthz|readyz)/?$", 1)[1].split("}", 1)[0]
    assert "auth_basic off" in health_location
