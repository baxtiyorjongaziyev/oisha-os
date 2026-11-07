import hashlib
import hmac
import json

import pytest

from src.services.core.crm.tg_amo_bridge.amojo_client import (
    AmoJoClient, sign_request, STATUS_ERROR,
)


def test_sign_request_matches_manual():
    body = b'{"a":1}'
    date = "Thu, 06 Nov 2026 10:00:00 GMT"
    h = sign_request("s3", "POST", "/v2/origin/custom/x", body, date=date)
    md5 = hashlib.md5(body, usedforsecurity=False).hexdigest()
    exp = hmac.new(
        b"s3",
        f"POST\n{md5}\napplication/json\n{date}\n/v2/origin/custom/x".encode(),
        hashlib.sha1,
    ).hexdigest()
    assert h["X-Signature"] == exp and h["Content-MD5"] == md5


def _client():
    return AmoJoClient("amojo-uuid", "chan", "secret", scope_id="chan_amojo-uuid")


def test_incoming_event_shape():
    ev = _client().build_message_event(
        conversation_id="42", sender_id="42", sender_name="Ali", text="salom", phone="+998901112233"
    )
    p = ev["payload"]
    assert ev["event_type"] == "new_message"
    assert p["sender"]["profile"]["phone"] == "+998901112233"
    assert p["message"] == {"type": "text", "text": "salom"}
    assert "receiver" not in p


def test_manager_event_moves_to_receiver():
    ev = _client().build_message_event(
        conversation_id="42", sender_id="42", sender_name="Ali", text="x", is_manager=True, silent=True
    )
    p = ev["payload"]
    assert "sender" not in p and p["receiver"]["id"] == "42" and p["silent"] is True


def test_media_event_and_invalid_type():
    c = _client()
    ev = c.build_message_event(
        conversation_id="1", sender_id="1", sender_name="A",
        media_type="picture", media_url="https://x/y.jpg", file_name="y.jpg", file_size=10,
    )
    assert ev["payload"]["message"]["type"] == "picture"
    with pytest.raises(ValueError):
        c.build_message_event(conversation_id="1", sender_id="1", sender_name="A", media_type="gif")


@pytest.mark.asyncio
async def test_connect_and_status_use_signed_post(monkeypatch):
    calls = []

    class Resp:
        status_code = 200
        content = b"{}"

        def json(self):
            return {"scope_id": "chan_amojo"}

    class FakeHttp:
        def __init__(self, *a, **k):
            pass

        async def __aenter__(self):
            return self

        async def __aexit__(self, *a):
            return False

        async def post(self, url, content, headers):
            calls.append((url, json.loads(content), headers))
            return Resp()

    monkeypatch.setattr(
        "src.services.core.crm.tg_amo_bridge.amojo_client.httpx.AsyncClient", FakeHttp
    )
    c = AmoJoClient("amojo-uuid", "chan", "secret")
    assert await c.connect() == "chan_amojo"
    assert calls[0][0].endswith("/v2/origin/custom/chan/connect")
    assert await c.send_status("m1", STATUS_ERROR, "boom")
    assert calls[1][0].endswith("/v2/origin/custom/chan_amojo/m1/delivery_status")
    assert calls[1][1]["error"] == "boom" and "X-Signature" in calls[1][2]


# ---- stage 2: store / outbound / inbound -------------------------------

import asyncio
from types import SimpleNamespace
from unittest.mock import AsyncMock

from src.services.core.crm.tg_amo_bridge import accounts, inbound, outbound
from src.services.core.crm.tg_amo_bridge.store import MessageStore


class FakePool:
    """In-memory sqlite standing in for db_pool."""

    def __init__(self):
        import sqlite3
        self.c = sqlite3.connect(":memory:")

    async def execute(self, q, params=None):
        cur = self.c.execute(q, params or [])
        rows = cur.fetchall()
        self.c.commit()
        return rows


def _amojo_mock():
    m = AsyncMock()
    m.scope_id = "s"
    m.build_message_event = AmoJoClient("a", "c", "x", "s").build_message_event
    m.send_event.return_value = {}
    m.send_status.return_value = True
    return m


@pytest.mark.asyncio
async def test_store_roundtrip():
    s = MessageStore(FakePool())
    await s.record("a1", 7, "owner", 42, "tg_in")
    assert await s.has_amo_msg("a1") and await s.has_tg_msg("owner", 7)
    assert await s.amo_id_for_tg("owner", 7) == "a1"
    assert not await s.has_tg_msg("owner", 8)


@pytest.mark.asyncio
async def test_outbound_dispatch_sends_and_dedups(monkeypatch):
    monkeypatch.setattr(outbound, "_MIN_INTERVAL", 0)
    tg = AsyncMock()
    tg.send_message.return_value = SimpleNamespace(id=99)
    acc = accounts.Account("owner", "O", "oisha-tg-owner", lambda: tg)
    monkeypatch.setattr(accounts, "_ACCOUNTS", {"owner": acc})
    monkeypatch.setattr(accounts, "OWNER", acc)
    store, amojo = MessageStore(FakePool()), _amojo_mock()
    data = {"message": {"msg_id": "m1", "text": "salom", "conversation": {"client_id": "42"}}}
    status, body = await outbound.dispatch(data, amojo, store)
    assert status == 200 and body["msg_id"] == "m1"
    tg.send_message.assert_awaited_once_with(42, "salom")
    assert await store.has_tg_msg("owner", 99)
    status, body = await outbound.dispatch(data, amojo, store)
    assert body.get("duplicate") and tg.send_message.await_count == 1


@pytest.mark.asyncio
async def test_outbound_rejects_bad_input():
    store, amojo = MessageStore(FakePool()), _amojo_mock()
    assert (await outbound.dispatch({"message": {"text": "x"}}, amojo, store))[0] == 200
    bad = {"message": {"text": "x", "conversation": {"client_id": "-5"}}}
    assert (await outbound.dispatch(bad, amojo, store))[0] == 400


def _event(out=False, text="hi", chat_id=42, msg_id=5):
    sender = SimpleNamespace(first_name="Ali", last_name=None, username="ali", phone="998901", bot=False)
    return SimpleNamespace(
        is_private=True, out=out, chat_id=chat_id,
        message=SimpleNamespace(id=msg_id, raw_text=text, voice=None, photo=None, document=None, media=None),
        get_sender=AsyncMock(return_value=sender),
    )


ACC = accounts.Account("owner", "O", "oisha-tg-owner", lambda: None)


@pytest.mark.asyncio
async def test_inbound_client_message_forwarded():
    store, amojo = MessageStore(FakePool()), _amojo_mock()
    assert await inbound.handle_message(_event(), ACC, amojo, store)
    ev = amojo.send_event.await_args.args[0]["payload"]
    assert ev["sender"]["id"] == "42" and ev["silent"] is False
    assert await store.has_tg_msg("owner", 5)


@pytest.mark.asyncio
async def test_inbound_manager_reply_silent_and_echo_skipped(monkeypatch):
    monkeypatch.setattr(inbound, "_ECHO_GRACE_SECONDS", 0)
    store, amojo = MessageStore(FakePool()), _amojo_mock()
    assert await inbound.handle_message(_event(out=True, msg_id=6), ACC, amojo, store)
    ev = amojo.send_event.await_args.args[0]["payload"]
    assert ev["silent"] is True and "receiver" in ev and "sender" not in ev
    await store.record("amo-x", 7, "owner", 42, "amo_out")  # sent on amoCRM's request
    amojo.send_event.reset_mock()
    assert not await inbound.handle_message(_event(out=True, msg_id=7), ACC, amojo, store)
    amojo.send_event.assert_not_awaited()


@pytest.mark.asyncio
async def test_inbound_filters():
    store, amojo = MessageStore(FakePool()), _amojo_mock()
    ev = _event(); ev.is_private = False
    assert not await inbound.handle_message(ev, ACC, amojo, store)
    assert not await inbound.handle_message(_event(text=""), ACC, amojo, store)
    skip = AsyncMock(return_value=(True, "mijoz emas"))
    assert not await inbound.handle_message(_event(), ACC, amojo, store, is_non_client=skip)
    amojo.send_event.assert_not_awaited()


@pytest.mark.asyncio
async def test_resolve_amojo_id_from_crm(monkeypatch):
    from src.services.core.crm.tg_amo_bridge import runtime

    monkeypatch.delenv("AMOCRM_AMOJO_ID", raising=False)
    seen = {}

    class R:
        status_code = 200
        def json(self): return {"amojo_id": "uuid-123"}

    def fake_get(url, params=None, headers=None, timeout=None):
        seen.update(url=url, params=params)
        return R()

    monkeypatch.setattr("requests.get", fake_get)
    crm = SimpleNamespace(base_url="https://x.amocrm.ru", _get_headers=lambda: {"Authorization": "t"})
    assert await runtime.resolve_amojo_id(crm) == "uuid-123"
    assert seen["params"] == {"with": "amojo_id"}
    import os
    assert os.environ["AMOCRM_AMOJO_ID"] == "uuid-123"
    monkeypatch.delenv("AMOCRM_AMOJO_ID", raising=False)
    assert await runtime.resolve_amojo_id(None) is None


@pytest.mark.asyncio
async def test_start_from_app_ctx_noop_when_disabled(monkeypatch):
    from src.services.core.crm.tg_amo_bridge import runtime

    monkeypatch.delenv("TG_AMO_BRIDGE_ENABLED", raising=False)
    assert await runtime.start_from_app_ctx() is False


@pytest.mark.asyncio
async def test_start_from_app_ctx_never_raises(monkeypatch):
    from src.services.core.crm.tg_amo_bridge import runtime

    monkeypatch.setenv("TG_AMO_BRIDGE_ENABLED", "1")
    monkeypatch.setattr(runtime, "start", AsyncMock(side_effect=RuntimeError("boom")))
    assert await runtime.start_from_app_ctx() is False
