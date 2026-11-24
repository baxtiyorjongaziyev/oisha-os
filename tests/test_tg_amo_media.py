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
    assert not f.exists()


def test_proxy_route_cleans_up_temp_file_on_416_and_400(monkeypatch, tmp_path):
    from fastapi import FastAPI
    from fastapi.testclient import TestClient

    from src.api.routes.tg_media import router

    app = FastAPI()
    app.include_router(router)
    tok = media.make_token("F", "video/mp4", "v.mp4")

    for hdr, expected in (("bytes=999-1000", 416), ("bytes=bad", 400)):
        f = tmp_path / f"range_{expected}.bin"
        f.write_bytes(b"DATA")
        monkeypatch.setattr(media, "download_to_temp", AsyncMock(return_value=str(f)))
        resp = TestClient(app).get("/tg-media/" + tok, headers={"Range": hdr})
        assert resp.status_code == expected
        assert not f.exists()


def test_classify_ignores_web_preview():
    msg = _msg(
        raw_text="https://jonbranding.uz",
        photo=1,
        web_preview=SimpleNamespace(url="https://jonbranding.uz"),
        file=SimpleNamespace(mime_type="image/jpeg", name=None, ext=".jpg", size=100),
    )
    assert media.classify(msg) is None


@pytest.mark.asyncio
async def test_shared_contact_phone_not_passed_to_automerge(monkeypatch):
    sender = SimpleNamespace(first_name="Ali", last_name=None, username="ali", phone=None, bot=False)
    msg = _msg(
        raw_text="",
        contact=SimpleNamespace(first_name="Dilnoza", last_name="", phone_number="998901234567"),
    )
    ev = SimpleNamespace(
        is_private=True, out=False, chat_id=42, message=msg,
        get_sender=AsyncMock(return_value=sender),
    )
    merger = SimpleNamespace(ensure_chat_linked_before_send=AsyncMock(return_value=None))
    amojo = _amojo()
    store = MessageStore(FakePool())
    monkeypatch.setattr(store, "record", AsyncMock())
    acc = accounts.Account("owner", "O", "oisha-tg-owner", lambda: None)

    assert await inbound.handle_message(ev, acc, amojo, store, merger=merger)
    assert merger.ensure_chat_linked_before_send.await_args.kwargs["message_text"] == ""
    sent_text = amojo.send_event.await_args.args[0]["payload"]["message"]["text"]
    assert "+998901234567" in sent_text


@pytest.mark.asyncio
async def test_outbound_long_caption_splits_and_logs_shape(monkeypatch, tmp_path, caplog):
    monkeypatch.setattr(outbound, "_MIN_INTERVAL", 0)
    p = tmp_path / "doc.pdf"
    p.write_bytes(b"%PDF")
    monkeypatch.setattr(media, "fetch_to_temp", AsyncMock(return_value=str(p)))
    monkeypatch.setattr(media, "archive_outbound", AsyncMock())
    monkeypatch.setattr(media, "cleanup", lambda path: None)
    tg = AsyncMock()
    tg.send_file.return_value = SimpleNamespace(id=101)
    tg.send_message.return_value = SimpleNamespace(id=102)
    acc = accounts.Account("owner", "O", "oisha-tg-owner", lambda: tg)
    monkeypatch.setattr(accounts, "_ACCOUNTS", {"owner": acc})
    monkeypatch.setattr(accounts, "OWNER", acc)
    store = MessageStore(FakePool())
    monkeypatch.setattr(store, "has_amo_msg", AsyncMock(return_value=False))
    rec = AsyncMock()
    monkeypatch.setattr(store, "record", rec)

    long_text = "A" * 1024 + "SECRET_TAIL_DEADLINE"
    data = {
        "message": {
            "msg_id": "m55",
            "conversation": {"client_id": "42"},
            "message": {
                "type": "file",
                "text": long_text,
                "media": "https://drive.amocrm.ru/download/secret-token",
                "file_name": "doc.pdf",
            },
        }
    }
    with caplog.at_level("INFO", logger="TgAmoBridge.outbound"):
        status, _ = await outbound.dispatch(data, AsyncMock(), store)

    assert status == 200
    assert tg.send_file.await_args.kwargs["caption"] == "A" * 1024
    assert tg.send_message.await_args.args == (42, "SECRET_TAIL_DEADLINE")
    assert rec.await_count == 2
    assert any("host=drive.amocrm.ru" in r.message and "parsed=True" in r.message for r in caplog.records)
    assert all("SECRET_TAIL_DEADLINE" not in r.message and "secret-token" not in r.message for r in caplog.records)


def test_drive_thread_local_creates_separate_instances(monkeypatch):
    import threading
    from src.services.core import gdrive as gdrive_mod

    created = []

    class FakeDrive:
        def __init__(self, creds):
            created.append(self)

    monkeypatch.setattr(gdrive_mod, "GoogleDriveSync", FakeDrive)
    monkeypatch.setattr(media, "_drive_local", threading.local())
    results = []

    def worker():
        results.append(media._drive())

    t1, t2 = threading.Thread(target=worker), threading.Thread(target=worker)
    t1.start()
    t2.start()
    t1.join()
    t2.join()
    assert len(results) == 2 and results[0] is not results[1]


def test_upload_evicts_deleted_folder_cache_and_retries(monkeypatch, tmp_path):
    from unittest.mock import MagicMock

    f = tmp_path / "img.jpg"
    f.write_bytes(b"JPG")
    monkeypatch.setenv("TG_AMO_MEDIA_FOLDER_ID", "root_id")
    media._folder_cache.clear()
    media._folder_cache["root_id/tg_77"] = "stale_folder"

    class NotFound404(Exception):
        status_code = 404

    calls = {"upload": 0}
    files_api = MagicMock()
    files_api.list.return_value.execute.return_value = {"files": []}

    def create_side_effect(**kwargs):
        req = MagicMock()
        if kwargs.get("body", {}).get("mimeType") == media._FOLDER_MIME:
            req.execute.return_value = {"id": "fresh_folder"}
        else:
            calls["upload"] += 1
            if calls["upload"] == 1:
                req.execute.side_effect = NotFound404("gone")
            else:
                req.execute.return_value = {"id": "uploaded_1"}
        return req

    files_api.create.side_effect = create_side_effect
    fake_service = MagicMock()
    fake_service.files.return_value = files_api
    monkeypatch.setattr(media, "_drive", lambda: SimpleNamespace(service=fake_service))

    assert media._upload_sync(str(f), "img.jpg", "image/jpeg", 77) == "uploaded_1"
    assert calls["upload"] == 2
    assert media._folder_cache["root_id/tg_77"] == "fresh_folder"


def test_extract_handles_non_dict_message():
    assert media.extract_outbound_media({"message": "bad"}) is None
    assert media.extract_outbound_media({"message": None}) is None


def test_gdrive_oauth_onboarding_routes_are_public():
    from src.api.security import is_protected_path

    assert is_protected_path("/api/integrations/gdrive/connect") is False
    assert is_protected_path("/api/integrations/gdrive/callback") is False
    assert is_protected_path("/api/integrations/gdrive/complete") is False
    assert is_protected_path("/tg-media/any.token") is False
    assert is_protected_path("/api/integrations/other") is True


def test_upload_recovers_when_cached_default_root_deleted(monkeypatch, tmp_path):
    from unittest.mock import MagicMock

    f = tmp_path / "img2.jpg"
    f.write_bytes(b"JPG")
    monkeypatch.delenv("TG_AMO_MEDIA_FOLDER_ID", raising=False)
    media._folder_cache.clear()
    media._folder_cache["None/Oisha_TG_Media"] = "deleted_root"

    class NotFound404(Exception):
        status_code = 404

    files_api = MagicMock()
    files_api.list.return_value.execute.return_value = {"files": []}

    def create_side_effect(**kwargs):
        req = MagicMock()
        body = kwargs.get("body", {})
        if body.get("parents") == ["deleted_root"]:
            req.execute.side_effect = NotFound404("root gone")
        elif body.get("mimeType") == media._FOLDER_MIME:
            req.execute.return_value = {"id": "new_root" if not body.get("parents") else "new_child"}
        else:
            req.execute.return_value = {"id": "uploaded_ok"}
        return req

    files_api.create.side_effect = create_side_effect
    fake_service = MagicMock()
    fake_service.files.return_value = files_api
    monkeypatch.setattr(media, "_drive", lambda: SimpleNamespace(service=fake_service))

    assert media._upload_sync(str(f), "img2.jpg", "image/jpeg", 88) == "uploaded_ok"
    assert media._folder_cache["None/Oisha_TG_Media"] == "new_root"
    assert media._folder_cache["new_root/tg_88"] == "new_child"


@pytest.mark.asyncio
async def test_outbound_continuation_failure_retry_skips_file(monkeypatch, tmp_path):
    monkeypatch.setattr(outbound, "_MIN_INTERVAL", 0)
    p = tmp_path / "doc2.pdf"
    p.write_bytes(b"%PDF")
    monkeypatch.setattr(media, "fetch_to_temp", AsyncMock(return_value=str(p)))
    monkeypatch.setattr(media, "archive_outbound", AsyncMock())
    monkeypatch.setattr(media, "cleanup", lambda path: None)
    tg = AsyncMock()
    tg.send_file.return_value = SimpleNamespace(id=201)
    tg.send_message.side_effect = [RuntimeError("net"), SimpleNamespace(id=202)]
    acc = accounts.Account("owner", "O", "oisha-tg-owner", lambda: tg)
    monkeypatch.setattr(accounts, "_ACCOUNTS", {"owner": acc})
    monkeypatch.setattr(accounts, "OWNER", acc)
    recorded = set()
    store = MessageStore(FakePool())
    monkeypatch.setattr(store, "has_amo_msg", AsyncMock(side_effect=lambda k: k in recorded))
    monkeypatch.setattr(store, "record", AsyncMock(side_effect=lambda k, *a: recorded.add(k)))

    data = {
        "message": {
            "msg_id": "m99",
            "conversation": {"client_id": "42"},
            "message": {
                "type": "file",
                "text": "B" * 1024 + "TAIL",
                "media": "https://drive.amocrm.ru/f",
                "file_name": "doc2.pdf",
            },
        }
    }
    amojo = AsyncMock()
    s1, _ = await outbound.dispatch(data, amojo, store)
    assert s1 == 502 and "m99:file" in recorded and "m99" not in recorded
    s2, _ = await outbound.dispatch(data, amojo, store)
    assert s2 == 200 and tg.send_file.await_count == 1 and tg.send_message.await_count == 2
