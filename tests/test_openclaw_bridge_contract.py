"""Gateway -> bridge chaqiruv shartnomasi.

Handler'ni mock qilmaymiz: haqiqiy `handle_openclaw_message` imzosi ishlatiladi,
faqat orkestrator (LLM) almashtiriladi.
"""

import hashlib
import hmac
import json
import subprocess
import sys
from unittest.mock import patch

from fastapi import FastAPI
from fastapi.testclient import TestClient

from src import openclaw_bridge


class _FakeOrchestrator:
    def __init__(self):
        self.calls = []

    async def determine_intent(self, text):
        return "support"

    async def get_agent_response(self, *, agent_id, user_id, message, context):
        self.calls.append((agent_id, user_id, message, context))
        return "javob"


def _client():
    from src.api.routes.openclaw_gateway import router

    app = FastAPI()
    app.include_router(router)
    return TestClient(app)


def _fake_patch(orch):
    async def _get(db):
        return orch

    return patch.object(openclaw_bridge, "_get_orchestrator", _get)


def test_webhook_reaches_agent_with_real_bridge_signature(monkeypatch):
    monkeypatch.setenv("OPENCLAW_SECRET", "k")
    body = json.dumps({"message": "salom", "user_id": "42", "channel": "whatsapp"}).encode()
    sig = hmac.new(b"k", body, hashlib.sha256).hexdigest()
    orch = _FakeOrchestrator()
    with _fake_patch(orch):
        resp = _client().post(
            "/webhook/openclaw", content=body, headers={"x-openclaw-signature": sig}
        )
    assert resp.status_code == 200, resp.text
    assert resp.json()["reply"] == "javob"
    assert orch.calls[0][1] == 1_000_000_000 + 42


def test_v1_chat_completions_reaches_agent():
    orch = _FakeOrchestrator()
    with _fake_patch(orch):
        resp = _client().post(
            "/v1/chat/completions", json={"messages": [{"role": "user", "content": "hi"}]}
        )
    assert resp.status_code == 200, resp.text
    assert resp.json()["choices"][0]["message"]["content"] == "javob"


def test_session_is_optional_for_bridge():
    orch = _FakeOrchestrator()

    async def _run():
        with _fake_patch(orch):
            return await openclaw_bridge.handle_openclaw_message(
                text="hi", sender="a", sender_id="1", channel="telegram_business"
            )

    import asyncio

    assert asyncio.run(_run()) == "javob"


def test_non_numeric_sender_id_is_stable_across_processes():
    code = (
        "from src.openclaw_bridge import _get_numeric_user_id as f;"
        "print(f('abc-user','slack'))"
    )
    outs = {
        subprocess.run(
            [sys.executable, "-c", code],
            capture_output=True,
            text=True,
            env={"PYTHONHASHSEED": seed, "PATH": ""},
            check=True,
        ).stdout.strip()
        for seed in ("1", "2")
    }
    assert len(outs) == 1
