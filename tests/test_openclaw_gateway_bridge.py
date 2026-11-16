"""Tests for OpenClaw gateway <-> bridge contract and agent wiring."""
from __future__ import annotations

import hashlib
import hmac
import json
from types import SimpleNamespace
from unittest.mock import AsyncMock, patch

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from src import openclaw_bridge
from src.api.routes.openclaw_gateway import router


def _signed_post(client: TestClient, payload: dict, secret: str = "test-secret"):
    body = json.dumps(payload).encode("utf-8")
    sig = hmac.new(secret.encode("utf-8"), body, hashlib.sha256).hexdigest()
    return client.post(
        "/webhook/openclaw",
        content=body,
        headers={"x-openclaw-signature": sig, "Content-Type": "application/json"},
    )


def test_openclaw_webhook_accepts_skill_payload_and_calls_bridge(monkeypatch):
    monkeypatch.setenv("OPENCLAW_SECRET", "test-secret")
    app = FastAPI()
    app.include_router(router)
    client = TestClient(app)

    fake_orchestrator = SimpleNamespace(
        determine_intent=AsyncMock(return_value="sales"),
        get_agent_response=AsyncMock(return_value="Narxlarimiz 650 USD dan boshlanadi."),
    )
    with patch.object(openclaw_bridge, "_get_orchestrator", AsyncMock(return_value=fake_orchestrator)):
        resp = _signed_post(
            client,
            {
                "text": "Logotip narxi qancha?",
                "sender": "Dilshod",
                "sender_id": "4242",
                "channel": "telegram",
                "session": "mrjon-1",
            },
        )

    assert resp.status_code == 200
    assert resp.json() == {"reply": "Narxlarimiz 650 USD dan boshlanadi.", "status": "ok"}
    fake_orchestrator.determine_intent.assert_awaited_once_with("Logotip narxi qancha?")
    fake_orchestrator.get_agent_response.assert_awaited_once()
    call_kwargs = fake_orchestrator.get_agent_response.await_args.kwargs
    assert call_kwargs["agent_id"] == "sales"
    assert call_kwargs["user_id"] == 4242
    assert call_kwargs["context"]["channel"] == "telegram"
    assert call_kwargs["context"]["sender_name"] == "Dilshod"


def test_openclaw_webhook_accepts_legacy_message_payload(monkeypatch):
    monkeypatch.setenv("OPENCLAW_SECRET", "test-secret")
    app = FastAPI()
    app.include_router(router)
    client = TestClient(app)

    fake_orchestrator = SimpleNamespace(
        determine_intent=AsyncMock(return_value="support"),
        get_agent_response=AsyncMock(return_value="Yordamga tayyorman."),
    )
    with patch.object(openclaw_bridge, "_get_orchestrator", AsyncMock(return_value=fake_orchestrator)):
        resp = _signed_post(client, {"message": "Yordam kerak", "user_id": "9001"})

    assert resp.status_code == 200
    assert resp.json()["reply"] == "Yordamga tayyorman."
    assert fake_orchestrator.get_agent_response.await_args.kwargs["agent_id"] == "support"


def test_v1_chat_completions_calls_bridge_with_keyword_args():
    app = FastAPI()
    app.include_router(router)
    client = TestClient(app)

    fake_orchestrator = SimpleNamespace(
        determine_intent=AsyncMock(return_value="sales"),
        get_agent_response=AsyncMock(return_value="Salom, men Oisha."),
    )
    with patch.object(openclaw_bridge, "_get_orchestrator", AsyncMock(return_value=fake_orchestrator)):
        resp = client.post(
            "/v1/chat/completions",
            json={"model": "oisha-enterprise", "messages": [{"role": "user", "content": "Salom"}]},
        )

    assert resp.status_code == 200
    assert resp.json()["choices"][0]["message"]["content"] == "Salom, men Oisha."


@pytest.mark.asyncio
async def test_get_orchestrator_registers_core_agents_without_booted_controller(monkeypatch):
    monkeypatch.setattr(openclaw_bridge, "_agent_manager", None)
    monkeypatch.setattr(openclaw_bridge, "_orchestrator", None)

    from src.api.routes.state import api_state
    from src.context import app_ctx

    monkeypatch.setattr(api_state, "msg_controller", None)
    monkeypatch.setattr(app_ctx, "msg_controller", None)

    orchestrator = await openclaw_bridge._get_orchestrator(db=None)
    assert orchestrator.manager.get_agent("sales") is not None
    assert orchestrator.manager.get_agent("support") is not None
    assert orchestrator.manager.get_agent("strategist") is not None
    assert orchestrator.manager.get_agent("researcher") is not None


@pytest.mark.asyncio
async def test_handle_openclaw_message_works_without_session_arg():
    fake_orchestrator = SimpleNamespace(
        determine_intent=AsyncMock(return_value="sales"),
        get_agent_response=AsyncMock(return_value="Mehmon javobi"),
    )
    with patch.object(openclaw_bridge, "_get_orchestrator", AsyncMock(return_value=fake_orchestrator)):
        reply = await openclaw_bridge.handle_openclaw_message(
            text="Salom",
            sender="Mehmon",
            sender_id="123",
            channel="telegram_business",
        )
    assert reply == "Mehmon javobi"
