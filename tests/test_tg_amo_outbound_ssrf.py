import os
import socket
import tempfile

import httpx
import pytest

from src.services.core.crm.tg_amo_bridge import media, outbound_media


def _public_addrinfo(_host, _port=443, **_kw):
    return [(socket.AF_INET, socket.SOCK_STREAM, 6, "", ("93.184.216.34", 443))]


def _private_addrinfo(_host, _port=443, **_kw):
    return [(socket.AF_INET, socket.SOCK_STREAM, 6, "", ("169.254.169.254", 443))]


def test_outbound_url_allowlist_and_canonicalization(monkeypatch):
    monkeypatch.setattr(socket, "getaddrinfo", _public_addrinfo)

    url = media._validate_outbound_url("https://drive-b.amocrm.ru/download/abc-123/шартнома.pdf?ver=1")
    assert url.startswith("https://drive-b.amocrm.ru/download/abc-123/")
    assert "%D1%88" in url and url.endswith("?ver=1")

    cdn = media._validate_outbound_url("https://18821.selcdn.ru/amo/file_1.ogg")
    assert cdn == "https://18821.selcdn.ru/amo/file_1.ogg"


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
async def test_fetch_to_temp_follows_trusted_redirect_and_sanitizes_filename(monkeypatch):
    monkeypatch.setattr(socket, "getaddrinfo", _public_addrinfo)
    seen = []

    def handler(request: httpx.Request) -> httpx.Response:
        seen.append(str(request.url))
        if request.url.host == "drive-b.amocrm.ru":
            return httpx.Response(302, headers={"Location": "https://9911.selcdn.ru/bucket/voice.ogg"})
        return httpx.Response(200, content=b"OGG_DATA")

    transport = httpx.MockTransport(handler)
    real_client = httpx.AsyncClient

    monkeypatch.setattr(
        outbound_media.httpx,
        "AsyncClient",
        lambda **kw: real_client(transport=transport, follow_redirects=kw.get("follow_redirects", False)),
    )

    path = await media.fetch_to_temp("https://drive-b.amocrm.ru/v1/get/123", "../../bad\\name.ogg")
    try:
        from pathlib import Path

        assert os.path.isfile(path)
        assert Path(path).read_bytes() == b"OGG_DATA"
        assert os.path.basename(os.path.dirname(path)).startswith("amoout_")
        assert seen == [
            "https://drive-b.amocrm.ru/v1/get/123",
            "https://9911.selcdn.ru/bucket/voice.ogg",
        ]
    finally:
        media.cleanup(path)
    assert not os.path.exists(path)


@pytest.mark.asyncio
async def test_fetch_to_temp_blocks_untrusted_redirect_hop(monkeypatch):
    monkeypatch.setattr(socket, "getaddrinfo", _public_addrinfo)

    def handler(_request: httpx.Request) -> httpx.Response:
        return httpx.Response(302, headers={"Location": "https://169.254.169.254/latest/meta-data/"})

    transport = httpx.MockTransport(handler)
    real_client = httpx.AsyncClient
    monkeypatch.setattr(
        outbound_media.httpx,
        "AsyncClient",
        lambda **kw: real_client(transport=transport, follow_redirects=kw.get("follow_redirects", False)),
    )

    with pytest.raises(ValueError):
        await media.fetch_to_temp("https://drive-b.amocrm.ru/v1/get/123", "doc.pdf")


def test_cleanup_ignores_outside_temp_root(tmp_path):
    unrelated = tmp_path / "amoout_keep" / "f.txt"
    unrelated.parent.mkdir()
    unrelated.write_text("keep", encoding="utf-8")
    # If tmp_path is inside system temp root,amoout_ would match; test non-amoout dir explicitly:
    safe_dir = tempfile.mkdtemp(prefix="keepdir_")
    keep_file = os.path.join(safe_dir, "important.txt")
    with open(keep_file, "w", encoding="utf-8") as fh:
        fh.write("safe")
    try:
        media.cleanup(keep_file)
        assert os.path.isfile(keep_file)
    finally:
        os.unlink(keep_file)
        os.rmdir(safe_dir)
