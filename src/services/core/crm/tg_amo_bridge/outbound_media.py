"""Outbound amoCRM -> Telegram media validation, streaming, and archival.

Enforces strict defense-in-depth against SSRF, DNS rebinding, open-redirect
escapes, and path traversal while supporting amoCRM Drive -> CDN 302 redirects.
"""
from __future__ import annotations

import asyncio
import ipaddress
import logging
import mimetypes
import os
import re
import shutil
import socket
import tempfile
from collections.abc import Awaitable, Callable
from urllib.parse import quote, urljoin, urlparse

import httpx

logger = logging.getLogger("TgAmoBridge.outbound_media")

_OUT_TYPES = {"picture", "file", "voice", "video", "sticker", "audio"}
_REDIRECT_CODES = {301, 302, 303, 307, 308}
_MAX_REDIRECTS = 3
_LABEL_RE = re.compile(r"^[a-z0-9](?:[a-z0-9-]{0,61}[a-z0-9])?$")
_SAFE_HOST_CHARS: dict[str, str] = {c: c for c in "abcdefghijklmnopqrstuvwxyz0123456789-."}
_SAFE_REL_CHARS: dict[str, str] = {
    c: c for c in "ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789-._~/?!$&'()*+,;=:%"
}

_EXACT_AMO_HOSTS: dict[str, str] = {
    "amojo.amocrm.ru": "amojo.amocrm.ru",
    "drive.amocrm.ru": "drive.amocrm.ru",
    "drive-a.amocrm.ru": "drive-a.amocrm.ru",
    "drive-b.amocrm.ru": "drive-b.amocrm.ru",
    "drive-c.amocrm.ru": "drive-c.amocrm.ru",
    "amojo.amocrm.com": "amojo.amocrm.com",
    "drive.amocrm.com": "drive.amocrm.com",
    "drive-a.amocrm.com": "drive-a.amocrm.com",
    "drive-b.amocrm.com": "drive-b.amocrm.com",
    "drive-c.amocrm.com": "drive-c.amocrm.com",
    "amojo.kommo.com": "amojo.kommo.com",
    "drive.kommo.com": "drive.kommo.com",
    "drive-a.kommo.com": "drive-a.kommo.com",
    "drive-b.kommo.com": "drive-b.kommo.com",
    "drive-c.kommo.com": "drive-c.kommo.com",
}

_TRUSTED_MEDIA_SUFFIXES: tuple[str, ...] = (
    "amocrm.ru",
    "amocrm.com",
    "kommo.com",
    "selcdn.ru",
    "selectel.ru",
    "amazonaws.com",
    "cloudfront.net",
)


def extract_outbound_media(data: dict) -> dict | None:
    """Return {"type","url","name","size"} for an amoJo webhook carrying a file."""
    message = data.get("message")
    if not isinstance(message, dict):
        return None
    inner = message.get("message") if isinstance(message.get("message"), dict) else message
    mtype = str(inner.get("type") or "").lower()
    url = inner.get("media") or inner.get("media_url") or ""
    if mtype not in _OUT_TYPES or not isinstance(url, str) or not url.startswith("https://"):
        return None
    name = os.path.basename(str(inner.get("file_name") or "")) or None
    size = inner.get("file_size")
    return {"type": mtype, "url": url, "name": name, "size": int(size) if str(size or "").isdigit() else 0}


def _configured_extra_hosts() -> set[str]:
    extra = {
        h.strip().lower()
        for h in os.getenv("TG_AMO_EXTRA_MEDIA_HOSTS", "").split(",")
        if h.strip()
    }
    base_raw = os.getenv("TG_AMO_MEDIA_BASE_URL", "").strip()
    if base_raw:
        base_host = (urlparse(base_raw).hostname or "").strip().lower()
        if base_host:
            extra.add(base_host)
    return extra


def _canonicalize_trusted_host(raw_host: str) -> str:
    """Return an untainted canonical hostname if trusted, else raise ValueError."""
    host = raw_host.strip().rstrip(".").lower()
    if not host or len(host) > 253:
        raise ValueError("invalid outbound media URL")
    if host in {"localhost", "localhost.localdomain"} or host.endswith((".local", ".internal")):
        raise ValueError("blocked outbound host")
    exact = _EXACT_AMO_HOSTS.get(host)
    if exact is not None:
        return exact

    labels = host.split(".")
    if len(labels) < 2 or not all(_LABEL_RE.fullmatch(lbl) for lbl in labels):
        raise ValueError("invalid outbound host syntax")

    matched_suffix = next(
        (sfx for sfx in _TRUSTED_MEDIA_SUFFIXES if host == sfx or host.endswith("." + sfx)),
        None,
    )
    if matched_suffix is None and host not in _configured_extra_hosts():
        raise ValueError("untrusted outbound media host")

    try:
        return "".join(_SAFE_HOST_CHARS[ch] for ch in host)
    except KeyError as exc:
        raise ValueError("invalid host characters") from exc


def _sanitize_relative_target(path: str, query: str) -> str:
    """Validate URL path/query and return untainted RFC-3986 relative target."""
    norm_path = path if path else "/"
    if not norm_path.startswith("/") or norm_path.startswith("//") or "\\" in norm_path:
        raise ValueError("invalid outbound media path")
    if any(seg == ".." for seg in norm_path.split("/")):
        raise ValueError("path traversal in outbound media URL")
    if any(ord(ch) < 0x20 or ord(ch) == 0x7F for ch in norm_path + query):
        raise ValueError("control characters in outbound media URL")
    enc_path = quote(norm_path.lstrip("/"), safe="/-._~%!$&'()*+,;=:")
    enc_query = quote(query, safe="/?-._~%!$&'()*+,;=:") if query else ""
    raw_rel = f"{enc_path}?{enc_query}" if enc_query else enc_path
    try:
        return "".join(_SAFE_REL_CHARS[ch] for ch in raw_rel)
    except KeyError as exc:
        raise ValueError("invalid characters in outbound media target") from exc


def _parse_and_allowlist_url(url: str) -> str:
    """Parse URL, enforce HTTPS + trusted host allowlist, and rebuild canonical URL."""
    parsed = urlparse(url)
    if parsed.scheme != "https" or parsed.username or parsed.password or parsed.fragment:
        raise ValueError("invalid outbound media URL")
    if parsed.port not in (None, 443):
        raise ValueError("blocked outbound port")
    safe_host = _canonicalize_trusted_host(parsed.hostname or "")
    clean_rel = _sanitize_relative_target(parsed.path, parsed.query)
    return f"https://{safe_host}/{clean_rel}"


def _verify_public_ips_sync(host: str) -> None:
    try:
        infos = socket.getaddrinfo(host, 443, type=socket.SOCK_STREAM)
    except OSError as exc:
        raise ValueError("unresolvable outbound host") from exc
    if not infos:
        raise ValueError("unresolvable outbound host")
    for info in infos:
        ip = ipaddress.ip_address(info[4][0])
        if (
            not ip.is_global
            or ip.is_private
            or ip.is_loopback
            or ip.is_link_local
            or ip.is_reserved
            or ip.is_multicast
        ):
            raise ValueError("blocked non-public outbound IP")


def validate_outbound_url(url: str) -> str:
    """Synchronous allowlist + DNS public-IP check returning canonical HTTPS URL."""
    canonical = _parse_and_allowlist_url(url)
    host = urlparse(canonical).hostname or ""
    _verify_public_ips_sync(host)
    return canonical


async def _validate_outbound_url_async(url: str) -> str:
    canonical = _parse_and_allowlist_url(url)
    host = urlparse(canonical).hostname or ""
    await asyncio.to_thread(_verify_public_ips_sync, host)
    return canonical


def _prepare_temp_target(name: str | None) -> tuple[str, str]:
    tmpdir = os.path.abspath(tempfile.mkdtemp(prefix="amoout_"))
    ext = os.path.splitext(name or "")[1]
    suffix = ext if re.fullmatch(r"\.[A-Za-z0-9]{1,10}", ext or "") else (
        mimetypes.guess_extension("application/octet-stream") or ".bin"
    )
    raw_name = os.path.basename(name or f"file{suffix}")
    safe_name = re.sub(r"[^A-Za-z0-9._-]", "_", raw_name).strip("._") or f"file{suffix}"
    path = os.path.abspath(os.path.join(tmpdir, safe_name))
    if os.path.commonpath([tmpdir, path]) != tmpdir or path == tmpdir:
        shutil.rmtree(tmpdir, ignore_errors=True)
        raise ValueError("invalid media path")
    return tmpdir, path


async def fetch_to_temp(url: str, name: str | None, *, limit_bytes: int) -> str:
    """Stream a validated amoCRM media URL into a temp dir; returns the file path."""
    current_url = await _validate_outbound_url_async(url)
    tmpdir, path = _prepare_temp_target(name)
    total = 0
    try:
        async with httpx.AsyncClient(timeout=60, follow_redirects=False) as client:
            for _ in range(_MAX_REDIRECTS + 1):
                async with client.stream("GET", current_url) as resp:
                    if resp.status_code in _REDIRECT_CODES:
                        loc = (resp.headers.get("location") or "").strip()
                        if not loc:
                            raise ValueError("empty redirect location")
                        current_url = await _validate_outbound_url_async(urljoin(current_url, loc))
                        continue
                    resp.raise_for_status()
                    with open(path, "wb") as fh:
                        async for chunk in resp.aiter_bytes():
                            total += len(chunk)
                            if total > limit_bytes:
                                raise ValueError("media too large")
                            fh.write(chunk)
                    return path
            raise ValueError("too many outbound media redirects")
    except Exception:
        shutil.rmtree(tmpdir, ignore_errors=True)
        raise


def cleanup(path: str | None) -> None:
    if not path:
        return
    tmpdir = os.path.abspath(os.path.dirname(path))
    temp_root = os.path.abspath(tempfile.gettempdir())
    if os.path.basename(tmpdir).startswith("amoout_") and os.path.commonpath([temp_root, tmpdir]) == temp_root:
        shutil.rmtree(tmpdir, ignore_errors=True)


async def archive_outbound(
    path: str,
    peer_id: int,
    *,
    enabled: bool,
    uploader: Callable[[str, str, str, int], Awaitable[str]],
) -> None:
    """Best-effort copy of a manager-sent file into Drive."""
    if not enabled:
        return
    try:
        name = os.path.basename(path)
        mime = mimetypes.guess_type(name)[0] or "application/octet-stream"
        await uploader(path, name, mime, peer_id)
    except Exception as exc:
        logger.warning("[TG-AMO] drive archive failed: %s", type(exc).__name__)
