import os
from pathlib import Path
import socket
import tempfile
from types import SimpleNamespace

import httpx
import pytest

from src.services.core.crm.tg_amo_bridge import media, outbound_media


def _public_addrinfo(_host, _port=443, **_kw):
    return [(socket.AF_INET, socket.SOCK_STREAM, 6, "", ("93.184.216.34", 443))]


def _private_addrinfo(_host, _port=443, **_kw):
    return [(socket.AF_INET, socket.SOCK_STREAM, 6, "", ("169.254.169.254", 443))]


def test_outbound_url_allowlist_canonicalization_and_semicolon(monkeypatch):
    monkeypatch.setattr(socket, "getaddrinfo", _public_addrinfo)

    url = media._validate_outbound_url("https://drive-b.amocrm.ru/download/abc-123/шартнома.pdf?ver=1")
    assert url.startswith("https://drive-b.amocrm.ru/download/abc-123/")
    assert "%D1%88" in url and url.endswith("?ver=1")

    semi = media._validate_outbound_url("https://9911.selcdn.ru/bucket/file;v=2?token=abc")
    assert semi == "https://9911.selcdn.ru/bucket/file;v=2?token=abc"


@pytest.mark.parametrize(
    "bad_url",
    [
        "http://drive.amocrm.ru/a.pdf",
        "https://evil.example.com/a.pdf",
        "https://amocrm.ru.evil.com/a.pdf",
        "https://user:pass@drive.amocrm.ru/a.pdf",
        "https://drive.amocrm.ru:8443/a.pdf",
        "https://drive.amocrm.ru/a/../../etc/passwd",
        "https://localhost/a.pdf",
        "https://drive.amocrm.ru//evil.com/a.pdf",
    ],
)
def test_outbound_url_rejects_untrusted_or_malformed(monkeypatch, bad_url):
    monkeypatch.setattr(socket, "getaddrinfo", _public_addrinfo)
    with pytest.raises(ValueError):
        media._validate_outbound_url(bad_url)


def test_outbound_url_blocks_private_dns_rebinding(monkeypatch):
    monkeypatch.setattr(socket, "getaddrinfo", _private_addrinfo)
    with pytest.raises(ValueError, match="non-public"):
        media._validate_outbound_url("https://drive.amocrm.ru/file.pdf")


@pytest.mark.asyncio
async def test_fetch_to_temp_follows_trusted_redirect_and_sanitizes_filenames(monkeypatch):
    monkeypatch.setattr(socket, "getaddrinfo", _public_addrinfo)
    seen = []

    def handler(request: httpx.Request) -> httpx.Response:
        seen.append(str(request.url))
        if request.url.host == "drive-b.amocrm.ru":
            return httpx.Response(302, headers={"Location": "https://9911.selcdn.ru/bucket/voice;v=1.ogg"})
        return httpx.Response(200, content=b"OGG_DATA")

    transport = httpx.MockTransport(handler)
    real_client = httpx.AsyncClient
    monkeypatch.setattr(
        outbound_media.httpx,
        "AsyncClient",
        lambda **kw: real_client(transport=transport, follow_redirects=kw.get("follow_redirects", False)),
    )

    path = await media.fetch_to_temp("https://drive-b.amocrm.ru/v1/get/123", "../../bad$name.ogg")
    try:
        assert os.path.isfile(path)
        assert os.path.basename(path) == "bad_name.ogg"
        assert Path(path).read_bytes() == b"OGG_DATA"
        assert os.path.basename(os.path.dirname(path)).startswith("amoout_")
        assert seen == [
            "https://drive-b.amocrm.ru/v1/get/123",
            "https://9911.selcdn.ru/bucket/voice;v=1.ogg",
        ]
    finally:
        media.cleanup(path)
    assert not os.path.exists(path)

    cyr_path = await media.fetch_to_temp("https://9911.selcdn.ru/bucket/doc.pdf", "шартнома.pdf")
    try:
        assert os.path.basename(cyr_path) == "file.pdf"
    finally:
        media.cleanup(cyr_path)


@pytest.mark.asyncio
async def test_fetch_to_temp_blocks_untrusted_redirect_and_connected_private_peer(monkeypatch):
    monkeypatch.setattr(socket, "getaddrinfo", _public_addrinfo)

    def redirect_handler(_request: httpx.Request) -> httpx.Response:
        return httpx.Response(302, headers={"Location": "https://169.254.169.254/latest/meta-data/"})

    real_client = httpx.AsyncClient
    monkeypatch.setattr(
        outbound_media.httpx,
        "AsyncClient",
        lambda **kw: real_client(
            transport=httpx.MockTransport(redirect_handler),
            follow_redirects=kw.get("follow_redirects", False),
        ),
    )
    with pytest.raises(ValueError):
        await media.fetch_to_temp("https://drive-b.amocrm.ru/v1/get/123", "doc.pdf")

    rebind_stream = SimpleNamespace(get_extra_info=lambda k: ("127.0.0.1", 443) if k == "peername" else None)

    def rebind_handler(_request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, content=b"SECRET", extensions={"network_stream": rebind_stream})

    monkeypatch.setattr(
        outbound_media.httpx,
        "AsyncClient",
        lambda **kw: real_client(
            transport=httpx.MockTransport(rebind_handler),
            follow_redirects=kw.get("follow_redirects", False),
        ),
    )
    with pytest.raises(ValueError, match="non-public"):
        await media.fetch_to_temp("https://drive-b.amocrm.ru/v1/get/123", "doc.pdf")


def test_cleanup_only_deletes_direct_amoout_subdir_of_temp_root(monkeypatch, tmp_path):
    fake_temp_root = tmp_path / "sys_tmp"
    fake_temp_root.mkdir()
    monkeypatch.setattr(tempfile, "gettempdir", lambda: str(fake_temp_root))

    outside_amoout = tmp_path / "amoout_outside" / "keep.txt"
    outside_amoout.parent.mkdir()
    outside_amoout.write_text("keep", encoding="utf-8")
    media.cleanup(str(outside_amoout))
    assert outside_amoout.is_file()

    nested_amoout = fake_temp_root / "sub" / "amoout_nested" / "keep.txt"
    nested_amoout.parent.mkdir(parents=True)
    nested_amoout.write_text("keep", encoding="utf-8")
    media.cleanup(str(nested_amoout))
    assert nested_amoout.is_file()

    valid_amoout = fake_temp_root / "amoout_valid" / "temp.bin"
    valid_amoout.parent.mkdir()
    valid_amoout.write_text("gone", encoding="utf-8")
    media.cleanup(str(valid_amoout))
    assert not valid_amoout.parent.exists()
