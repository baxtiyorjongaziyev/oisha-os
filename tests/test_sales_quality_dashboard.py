import pytest
import json
from fastapi.responses import JSONResponse

from src.api.routes.state import api_state


@pytest.mark.asyncio
async def test_sales_quality_overview_never_returns_demo_data(monkeypatch):
    from src import api_server

    monkeypatch.setattr(api_state, "db_instance", None)

    payload = await api_server.get_sales_quality_overview()

    assert isinstance(payload, JSONResponse)
    assert payload.status_code == 503
    body = json.loads(payload.body)
    assert body["source"] == "real_call_analytics"
    assert body["real_data"] is False
    assert body["team"]["calls_total"] == 0
    assert body["managers"] == []
    assert "demo" not in str(body).lower()


@pytest.mark.asyncio
async def test_sales_quality_payload_uses_real_rows():
    from src.api_server import _build_sales_quality_payload

    payload = _build_sales_quality_payload(
        [
            {
                "call_id": "real-call-1",
                "lead_id": 777,
                "manager_id": 10,
                "manager_name": "Real Manager",
                "client_name": "Real Client",
                "duration_seconds": 121,
                "overall_score": 88,
                "scores": '[{"metric":"tone","score":90},{"metric":"follow_up","score":80}]',
                "summary": "Real transcriptdan olingan xulosa.",
                "weaknesses": '["Follow-up aniqligi"]',
                "objections": '["Narx"]',
                "outcome": "callback",
            }
        ]
    )

    assert payload["real_data"] is True
    assert payload["team"]["quality_score"] == 88.0
    assert payload["managers"][0]["name"] == "Real Manager"
    assert payload["calls"][0]["client"] == "Real Client"
