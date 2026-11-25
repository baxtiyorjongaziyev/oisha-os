"""Unit tests for animated (.tgs) and video (.webm) sticker previews in tg_amo_bridge."""
from __future__ import annotations

import os
from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest

from src.services.core.crm.tg_amo_bridge import accounts, inbound, media, sticker_preview
from src.services.core.crm.tg_amo_bridge.store import MessageStore

_WEBP_BYTES = b"RIFF\x24\x00\x00\x00WEBPVP8 " + b"\x00" * 16
_PNG_BYTES = b"\x89PNG\r\n\x1a\n" + b"\x00" * 16
_JPG_BYTES = b"\xff\xd8\xff\xe0" + b"\x00" * 16


class PhotoPathSize:
    def __init__(self, data: bytes = b"svg"):
        self.bytes = data


class PhotoSizeEmpty:
    pass


class VideoSize:
    def __init__(self, size: int = 20000):
        self.size = size


class PhotoSize:
    def __init__(self, size: int = 4096):
        self.size = size


class PhotoStrippedSize:
    def __init__(self, data: bytes = b"123456"):
        self.bytes = data


@pytest.fixture(autouse=True)
def _env(monkeypatch):
    monkeypatch.setenv("TG_AMO_MEDIA_SECRET", "k3y")
    monkeypatch.setenv("TG_AMO_MEDIA_BASE_URL", "https://oisha.example")
    monkeypatch.setenv("TG_AMO_MEDIA_ENABLED", "1")


def _sticker_msg(
    *,
    msg_id: int = 42,
    mime: str = "application/x-tgsticker",
    emoji: str = "😀",
    thumbs=None,
    download_media=None,
    size: int = 4096,
):
    doc = SimpleNamespace(
        attributes=[SimpleNamespace(alt=emoji)] if emoji else [],
        thumbs=thumbs,
    )
    return SimpleNamespace(
        id=msg_id,
        raw_text="",
        photo=None,
        voice=None,
        video=None,
        video_note=None,
        gif=None,
        audio=None,
        document=doc,
        sticker=doc,
        geo=None,
        contact=None,
        poll=None,
        dice=None,
        media=doc,
        web_preview=None,
        file=SimpleNamespace(mime_type=mime, name="AnimatedSticker.tgs", ext=".tgs", size=size),
        download_media=download_media or AsyncMock(return_value=None),
    )


def test_detect_image_format_magic_bytes(tmp_path):
    cases = [
        ("a.bin", _PNG_BYTES, ("image/png", ".png")),
        ("b.bin", _JPG_BYTES, ("image/jpeg", ".jpg")),
        ("c.jpg", _WEBP_BYTES, ("image/webp", ".webp")),
        ("d.bin", b"GIF89a\x01\x00", ("image/gif", ".gif")),
        ("e.tgs", b"\x1f\x8b\x08\x00not-an-image", None),
        ("f.empty", b"", None),
    ]
    for name, raw, expected in cases:
        p = tmp_path / name
        p.write_bytes(raw)
        assert sticker_preview.detect_image_format(str(p)) == expected


def test_select_raster_thumb_skips_svg_and_video():
    small_photo = PhotoSize(1024)
    big_photo = PhotoSize(8192)
    msg = _sticker_msg(thumbs=[PhotoPathSize(), small_photo, VideoSize(50000), big_photo, PhotoSizeEmpty()])
    assert sticker_preview.select_raster_thumb(msg) is big_photo

    svg_only = _sticker_msg(thumbs=[PhotoPathSize(), VideoSize(10000)])
    assert sticker_preview.select_raster_thumb(svg_only) is None

    no_meta = _sticker_msg(thumbs=None)
    assert sticker_preview.select_raster_thumb(no_meta) == -1


@pytest.mark.asyncio
async def test_tgs_sticker_uploads_raster_thumb_as_picture(monkeypatch):
    photo_thumb = PhotoSize(4096)
    uploaded = {}

    async def fake_download(*, file, thumb=None):
        assert thumb is photo_thumb
        # Telethon defaults thumb extension to .jpg even when bytes are WebP.
        out = file + ".jpg"
        with open(out, "wb") as fh:
            fh.write(_WEBP_BYTES)
        return out

    async def fake_upload(path, name, mime, peer_id):
        uploaded.update(name=name, mime=mime, peer_id=peer_id, size=os.path.getsize(path))
        return "DRV_STK_1"

    monkeypatch.setattr(media, "upload", fake_upload)
    msg = _sticker_msg(msg_id=2200284, thumbs=[PhotoPathSize(), photo_thumb], download_media=fake_download)

    ref, fallback = await media.prepare_inbound(msg, 1431546018)
    assert ref is not None
    assert fallback == ""
    assert ref.media_type == "picture"
    assert ref.file_name == "tg_2200284_sticker.webp"
    assert ref.file_size == len(_WEBP_BYTES)
    assert uploaded == {
        "name": "tg_2200284_sticker.webp",
        "mime": "image/webp",
        "peer_id": 1431546018,
        "size": len(_WEBP_BYTES),
    }
    tok = ref.url.rsplit("/tg-media/", 1)[1]
    verified = media.verify_token(tok)
    assert verified["f"] == "DRV_STK_1" and verified["m"] == "image/webp"


@pytest.mark.asyncio
async def test_tgs_sticker_without_raster_thumb_falls_back_to_emoji():
    dl = AsyncMock()
    msg = _sticker_msg(emoji="😀", thumbs=[PhotoPathSize()], download_media=dl)
    ref, fallback = await media.prepare_inbound(msg, 42)
    assert ref is None
    assert fallback == "[stiker 😀]"
    dl.assert_not_awaited()


@pytest.mark.asyncio
async def test_tgs_sticker_respects_media_disabled(monkeypatch):
    monkeypatch.setenv("TG_AMO_MEDIA_ENABLED", "0")
    dl = AsyncMock()
    msg = _sticker_msg(emoji="🔥", thumbs=[PhotoSize(2048)], download_media=dl)
    ref, fallback = await media.prepare_inbound(msg, 42)
    assert ref is None
    assert fallback == "[stiker 🔥]"
    dl.assert_not_awaited()


@pytest.mark.asyncio
async def test_webm_sticker_extracts_first_frame_when_thumb_missing(monkeypatch):
    async def fake_download(*, file, thumb=None):
        if thumb is not None:
            return None
        with open(file, "wb") as fh:
            fh.write(b"\x1a\x45\xdf\xa3fake-webm")
        return file

    class FakeProc:
        returncode = 0

        async def wait(self):
            return 0

        def kill(self):
            pass

    async def fake_exec(*args, **kwargs):
        out_path = args[-1]
        with open(out_path, "wb") as fh:
            fh.write(_PNG_BYTES)
        return FakeProc()

    monkeypatch.setattr(sticker_preview.shutil, "which", lambda cmd: "/usr/bin/ffmpeg")
    monkeypatch.setattr(sticker_preview.asyncio, "create_subprocess_exec", fake_exec)
    monkeypatch.setattr(media, "upload", AsyncMock(return_value="DRV_WEBM_1"))

    msg = _sticker_msg(
        msg_id=901,
        mime="video/webm",
        emoji="🎉",
        thumbs=[PhotoPathSize()],
        download_media=fake_download,
    )
    ref, fallback = await media.prepare_inbound(msg, 55)
    assert ref is not None and fallback == ""
    assert ref.media_type == "picture"
    assert ref.file_name == "tg_901_sticker.png"
    assert media.upload.await_args.args[2] == "image/png"


@pytest.mark.asyncio
async def test_webm_sticker_without_thumb_or_ffmpeg_falls_back(monkeypatch):
    monkeypatch.setattr(sticker_preview.shutil, "which", lambda cmd: None)
    msg = _sticker_msg(mime="video/webm", emoji="🔥", thumbs=[PhotoPathSize()])
    ref, fallback = await media.prepare_inbound(msg, 55)
    assert ref is None
    assert fallback == "[stiker 🔥]"


@pytest.mark.asyncio
async def test_inbound_handle_message_sends_tgs_sticker_as_picture(monkeypatch):
    async def fake_download(*, file, thumb=None):
        out = file + ".jpg"
        with open(out, "wb") as fh:
            fh.write(_JPG_BYTES)
        return out

    monkeypatch.setattr(media, "upload", AsyncMock(return_value="DRV_STK_2"))
    sender = SimpleNamespace(first_name="Akmal", last_name=None, username="akmal", phone=None, bot=False)
    msg = _sticker_msg(msg_id=2200284, thumbs=[PhotoStrippedSize()], download_media=fake_download)
    ev = SimpleNamespace(
        is_private=True,
        out=False,
        chat_id=1431546018,
        message=msg,
        get_sender=AsyncMock(return_value=sender),
    )

    from src.services.core.crm.tg_amo_bridge.amojo_client import AmoJoClient

    amojo = AsyncMock()
    amojo.send_event.return_value = {"ok": True}
    amojo.build_message_event = AmoJoClient("a", "c", "s").build_message_event
    store = MessageStore(None)
    monkeypatch.setattr(store, "record", AsyncMock())
    acc = accounts.Account("owner", "O", "oisha-tg-owner", lambda: None)

    assert await inbound.handle_message(ev, acc, amojo, store)
    sent_msg = amojo.send_event.await_args.args[0]["payload"]["message"]
    assert sent_msg["type"] == "picture"
    assert sent_msg["media"].startswith("https://oisha.example/tg-media/")
    assert sent_msg["file_name"] == "tg_2200284_sticker.jpg"
    assert "text" not in sent_msg
