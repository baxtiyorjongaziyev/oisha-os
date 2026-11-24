import time
from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest

from src.services.core.crm.tg_amo_bridge import accounts, inbound, media, outbound
from src.services.core.crm.tg_amo_bridge.store import MessageStore


@pytest.fixture(autouse=True)
def _env(monkeypatch):
    monkeypatch.setenv("TG_AMO_MEDIA_SECRET", "k3y")
    monkeypatch.setenv("TG_AMO_MEDIA_BASE_URL", "https://oisha.example")
    monkeypatch.setenv("TG_AMO_MEDIA_ENABLED", "1")


def test_token_roundtrip_and_tamper():
    tok = media.make_token("F1", "image/jpeg", "a.jpg")
    assert media.verify_token(tok)["f"] == "F1"
    body, sig = tok.split(".")
    assert media.verify_token(body + "." + sig[:-1] + ("A" if sig[-1] != "A" else "B")) is None
    assert media.verify_token("garbage") is None


def test_token_expired(monkeypatch):
    tok = media.make_token("F1", "image/jpeg", "a.jpg", ttl=300)
    monkeypatch.setattr(time, "time", lambda: 10**12)
    assert media.verify_token(tok) is None


def test_disabled_without_base_url(monkeypatch):
    monkeypatch.setenv("TG_AMO_MEDIA_BASE_URL", "")
    assert not media.media_enabled()


def _msg(**kw):
    base = dict(id=7, raw_text="", photo=None, voice=None, video=None, video_note=None, gif=None,
                audio=None, document=None, sticker=None, geo=None, contact=None, poll=None,
                dice=None, media=None, file=None)
    base.update(kw)
    return SimpleNamespace(**base)


def test_classify_types():
    f = lambda m: SimpleNamespace(mime_type=m, name=None, ext=".x", size=10)
    assert media.classify(_msg(photo=1, file=f("image/jpeg")))[0] == "picture"
    assert media.classify(_msg(voice=1, document=1, file=f("audio/ogg")))[0] == "voice"
    assert media.classify(_msg(gif=1, document=1, file=f("video/mp4")))[0] == "video"
    assert media.classify(_msg(document=1, file=f("application/pdf")))[0] == "file"
    assert media.classify(_msg(sticker=1, document=1, file=f("image/webp")))[0] == "picture"
    assert media.classify(_msg(sticker=1, document=1, file=f("application/x-tgsticker"))) is None


def test_non_file_text():
    geo = _msg(geo=SimpleNamespace(lat=41.3, long=69.2))
    assert "maps.google.com/?q=41.3,69.2" in media.describe_non_file(geo)
    c = _msg(contact=SimpleNamespace(first_name="Ali", last_name="", phone_number="998901"))
    assert "+998901" in media.describe_non_file(c)


def _amojo():
    m = AsyncMock()
    m.send_event.return_value = {"ok": True}
    from src.services.core.crm.tg_amo_bridge.amojo_client import AmoJoClient

    m.build_message_event = AmoJoClient("a", "c", "s").build_message_event
    return m


class FakePool:
    def __init__(self):
        self.rows = []

    async def execute(self, sql, params=()):
        if sql.strip().upper().startswith("INSERT"):
            self.rows.append(params)
        return None

    async def fetchone(self, sql, params=()):
        for r in self.rows:
            if set(params) <= set(r):
                return r
        return None


@pytest.mark.asyncio
async def test_inbound_photo_sent_as_picture(monkeypatch):
    async def fake_prepare(message, peer_id):
        return media.MediaRef("picture", "https://oisha.example/tg-media/t", "a.jpg", 5), ""

    monkeypatch.setattr(media, "prepare_inbound", fake_prepare)
    sender = SimpleNamespace(first_name="Ali", last_name=None, username="ali", phone=None, bot=False)
    msg = _msg(raw_text="izoh", photo=1, file=SimpleNamespace(mime_type="image/jpeg", name=None, size=5))
    ev = SimpleNamespace(is_private=True, out=False, chat_id=42, message=msg,
                         get_sender=AsyncMock(return_value=sender))
    amojo = _amojo()
    store = MessageStore(FakePool())
    monkeypatch.setattr(store, "record", AsyncMock())
    acc = accounts.Account("owner", "O", "oisha-tg-owner", lambda: None)
    assert await inbound.handle_message(ev, acc, amojo, store)
    m = amojo.send_event.await_args.args[0]["payload"]["message"]
    assert m["type"] == "picture" and m["media"].endswith("/tg-media/t") and m["text"] == "izoh"


@pytest.mark.asyncio
async def test_outbound_voice_uses_send_file(monkeypatch, tmp_path):
    monkeypatch.setattr(outbound, "_MIN_INTERVAL", 0)
    p = tmp_path / "v.ogg"
    p.write_bytes(b"x")
    monkeypatch.setattr(media, "fetch_to_temp", AsyncMock(return_value=str(p)))
    monkeypatch.setattr(media, "archive_outbound", AsyncMock())
    monkeypatch.setattr(media, "cleanup", lambda path: None)
    tg = AsyncMock()
    tg.send_file.return_value = SimpleNamespace(id=11)
    acc = accounts.Account("owner", "O", "oisha-tg-owner", lambda: tg)
    monkeypatch.setattr(accounts, "_ACCOUNTS", {"owner": acc})
    monkeypatch.setattr(accounts, "OWNER", acc)
    store = MessageStore(FakePool())
    monkeypatch.setattr(store, "has_amo_msg", AsyncMock(return_value=False))
    monkeypatch.setattr(store, "record", AsyncMock())
    data = {"message": {"msg_id": "m9", "conversation": {"client_id": "42"},
                        "message": {"type": "voice", "media": "https://amojo.example/v.ogg", "file_name": "v.ogg"}}}
    status, _ = await outbound.dispatch(data, AsyncMock(), store)
    assert status == 200
    kwargs = tg.send_file.await_args.kwargs
    assert kwargs["voice_note"] is True and tg.send_file.await_args.args[0] == 42


def test_extract_rejects_non_https():
    data = {"message": {"type": "file", "media": "http://x/y"}}
    assert media.extract_outbound_media(data) is None


def test_proxy_route_rejects_bad_token():
    from fastapi import FastAPI
    from fastapi.testclient import TestClient

    from src.api.routes.tg_media import router

    app = FastAPI()
    app.include_router(router)
    assert TestClient(app).get("/tg-media/bad.token").status_code == 404


def test_proxy_route_serves_file(monkeypatch, tmp_path):
    from fastapi import FastAPI
    from fastapi.testclient import TestClient

    from src.api.routes.tg_media import router

    f = tmp_path / "a"
    f.write_bytes(b"IMG")
    monkeypatch.setattr(media, "download_to_temp", AsyncMock(return_value=str(f)))
    app = FastAPI()
    app.include_router(router)
    r = TestClient(app).get("/tg-media/" + media.make_token("F", "image/jpeg", "a.jpg"))
    assert r.status_code == 200 and r.content == b"IMG" and r.headers["content-type"] == "image/jpeg"
