"""Telegram <-> amoCRM media: Google Drive storage + signed Oisha proxy links.

Files never become public in Drive. amoCRM receives a short-lived signed URL
(``{TG_AMO_MEDIA_BASE_URL}/tg-media/{token}``) that the Oisha API resolves and
streams from Drive (see ``src/api/routes/tg_media.py``).
"""
from __future__ import annotations

import asyncio
import base64
import hashlib
import hmac
import json
import logging
import os
import shutil
import tempfile
import threading
import time
from dataclasses import dataclass
from typing import Any

from . import config, outbound_media, sticker_preview

logger = logging.getLogger("TgAmoBridge.media")

_DEFAULT_TTL = 30 * 24 * 3600  # amoCRM re-reads media when a chat is reopened
_FOLDER_MIME = "application/vnd.google-apps.folder"
_folder_cache: dict[str, str] = {}
_folder_lock = threading.Lock()
_drive_local = threading.local()


# ---------------------------------------------------------------- config

def media_enabled() -> bool:
    flag = os.getenv("TG_AMO_MEDIA_ENABLED", "0").strip().lower() in {"1", "true", "yes", "on"}
    return flag and bool(base_url()) and bool(_signing_key())


def base_url() -> str:
    return os.getenv("TG_AMO_MEDIA_BASE_URL", "").strip().rstrip("/")


def max_bytes() -> int:
    raw = os.getenv("TG_AMO_MEDIA_MAX_MB", "50").strip()
    try:
        return max(1, int(raw)) * 1024 * 1024
    except ValueError:
        return 50 * 1024 * 1024


def _ttl() -> int:
    raw = os.getenv("TG_AMO_MEDIA_TTL_SECONDS", str(_DEFAULT_TTL)).strip()
    try:
        return max(300, int(raw))
    except ValueError:
        return _DEFAULT_TTL


def _signing_key() -> bytes:
    key = os.getenv("TG_AMO_MEDIA_SECRET", "").strip() or config.channel_secret()
    return key.encode("utf-8") if key else b""


# ---------------------------------------------------------------- tokens

def _b64(data: bytes) -> str:
    return base64.urlsafe_b64encode(data).decode("ascii").rstrip("=")


def _unb64(data: str) -> bytes:
    return base64.urlsafe_b64decode(data + "=" * (-len(data) % 4))


def make_token(file_id: str, mime: str, name: str, *, ttl: int | None = None) -> str:
    key = _signing_key()
    if not key:
        raise RuntimeError("media signing key missing")
    payload = json.dumps(
        {"f": file_id, "m": mime, "n": name, "e": int(time.time()) + (ttl or _ttl())},
        separators=(",", ":"),
    ).encode("utf-8")
    body = _b64(payload)
    sig = _b64(hmac.new(key, body.encode("ascii"), hashlib.sha256).digest())
    return f"{body}.{sig}"


def verify_token(token: str) -> dict | None:
    """Return {"f","m","n","e"} for a valid, unexpired token, else None."""
    key = _signing_key()
    if not key or not token or token.count(".") != 1:
        return None
    body, sig = token.split(".")
    expected = _b64(hmac.new(key, body.encode("ascii"), hashlib.sha256).digest())
    if not hmac.compare_digest(sig, expected):
        return None
    try:
        data = json.loads(_unb64(body))
    except (ValueError, json.JSONDecodeError):
        return None
    if not isinstance(data, dict) or int(data.get("e", 0)) < time.time() or not data.get("f"):
        return None
    return data


def proxy_url(file_id: str, mime: str, name: str) -> str:
    return f"{base_url()}/tg-media/{make_token(file_id, mime, name)}"


# ---------------------------------------------------------------- drive

def _drive():
    """Return a thread-local GoogleDriveSync (httplib2 is not thread-safe)."""
    inst = getattr(_drive_local, "sync", None)
    if inst is None:
        from src.services.core.gdrive import GoogleDriveSync
        from src.settings import settings

        creds = os.getenv("TG_AMO_MEDIA_CREDS_FILE", "").strip() or settings.GSHEET_CREDS_FILE
        inst = GoogleDriveSync(creds)
        _drive_local.sync = inst
    return inst


def _find_or_create_folder(service: Any, name: str, parent: str | None) -> str:
    key = f"{parent}/{name}"
    with _folder_lock:
        if key in _folder_cache:
            return _folder_cache[key]
        q = f"name = '{name}' and mimeType = '{_FOLDER_MIME}' and trashed = false"
        if parent:
            q += f" and '{parent}' in parents"
        found = (
            service.files()
            .list(q=q, fields="files(id)", supportsAllDrives=True, includeItemsFromAllDrives=True)
            .execute()
            .get("files", [])
        )
        if found:
            folder_id = found[0]["id"]
        else:
            body: dict = {"name": name, "mimeType": _FOLDER_MIME}
            if parent:
                body["parents"] = [parent]
            folder_id = service.files().create(body=body, fields="id", supportsAllDrives=True).execute()["id"]
        _folder_cache[key] = folder_id
        return folder_id


def _is_not_found(exc: Exception) -> bool:
    resp = getattr(exc, "resp", None)
    status = getattr(resp, "status", None) if resp is not None else getattr(exc, "status_code", None)
    return status == 404


def _upload_sync(path: str, name: str, mime: str, peer_id: int) -> str:
    from googleapiclient.http import MediaFileUpload

    service = _drive().service
    custom_root = os.getenv("TG_AMO_MEDIA_FOLDER_ID", "").strip()
    peer_name = f"tg_{int(peer_id)}"
    for attempt in range(2):
        root: str | None = None
        try:
            root = custom_root or _find_or_create_folder(service, "Oisha_TG_Media", None)
            folder = _find_or_create_folder(service, peer_name, root)
            media_body = MediaFileUpload(path, mimetype=mime, resumable=True)
            created = (
                service.files()
                .create(body={"name": name, "parents": [folder]}, media_body=media_body, fields="id", supportsAllDrives=True)
                .execute()
            )
            return created["id"]
        except Exception as exc:
            if attempt == 0 and _is_not_found(exc):
                with _folder_lock:
                    if root:
                        _folder_cache.pop(f"{root}/{peer_name}", None)
                    if not custom_root:
                        _folder_cache.pop("None/Oisha_TG_Media", None)
                continue
            raise
    raise RuntimeError("drive upload exhausted retries")


async def upload(path: str, name: str, mime: str, peer_id: int) -> str:
    return await asyncio.to_thread(_upload_sync, path, name, mime, peer_id)


def _download_sync(file_id: str, dest: str) -> None:
    from googleapiclient.http import MediaIoBaseDownload

    request = _drive().service.files().get_media(fileId=file_id, supportsAllDrives=True)
    with open(dest, "wb") as fh:
        downloader = MediaIoBaseDownload(fh, request, chunksize=8 * 1024 * 1024)
        done = False
        while not done:
            _, done = downloader.next_chunk()


async def download_to_temp(file_id: str) -> str:
    """Download a Drive file to a temp path the caller must delete."""
    fd, dest = tempfile.mkstemp(prefix="tgmedia_")
    os.close(fd)
    try:
        await asyncio.to_thread(_download_sync, file_id, dest)
    except Exception:
        os.unlink(dest)
        raise
    return dest


# ---------------------------------------------------------------- classify

@dataclass
class MediaRef:
    media_type: str  # amoJo: picture | file | voice | video
    url: str
    file_name: str
    file_size: int


_sticker_emoji = sticker_preview.sticker_emoji


def describe_non_file(message: Any) -> str:
    """Text form for Telegram content that has no downloadable file."""
    geo = getattr(message, "geo", None)
    if geo is not None and getattr(geo, "lat", None) is not None:
        venue = getattr(message, "venue", None)
        title = getattr(venue, "title", "") if venue else ""
        head = f"📍 Lokatsiya{': ' + title if title else ''}"
        return f"{head}\nhttps://maps.google.com/?q={geo.lat},{geo.long}"
    contact = getattr(message, "contact", None)
    if contact is not None:
        name = " ".join(filter(None, [getattr(contact, "first_name", ""), getattr(contact, "last_name", "")]))
        phone = getattr(contact, "phone_number", "") or ""
        return f"👤 Kontakt: {name} {('+' + phone.lstrip('+')) if phone else ''}".strip()
    poll = getattr(message, "poll", None)
    if poll is not None:
        inner = getattr(poll, "poll", poll)
        question = getattr(inner, "question", "")
        question = getattr(question, "text", question)
        lines = [f"📊 Soʻrovnoma: {question}"]
        for ans in getattr(inner, "answers", None) or []:
            label = getattr(ans, "text", "")
            lines.append(f"• {getattr(label, 'text', label)}")
        return "\n".join(lines)
    dice = getattr(message, "dice", None)
    if dice is not None:
        return f"{getattr(dice, 'emoticon', '🎲')} {getattr(dice, 'value', '')}".strip()
    return ""


def classify(message: Any) -> tuple[str, str, str] | None:
    """(amo_type, mime, default_ext) for a downloadable Telegram message, else None."""
    if getattr(message, "web_preview", None) is not None:
        return None  # Link previews expose .photo/.document in Telethon; keep as text
    file = getattr(message, "file", None)
    mime = (getattr(file, "mime_type", None) or "").lower()
    if getattr(message, "sticker", None):
        static_exts = {"image/webp": ".webp", "image/png": ".png", "image/jpeg": ".jpg"}
        if mime in static_exts:
            return "picture", mime, static_exts[mime]
        return None  # animated .tgs / video .webm -> handled via sticker_preview
    if getattr(message, "photo", None):
        return "picture", "image/jpeg", ".jpg"
    if getattr(message, "voice", None):
        return "voice", mime or "audio/ogg", ".ogg"
    if getattr(message, "gif", None) or getattr(message, "video_note", None) or getattr(message, "video", None):
        return "video", mime or "video/mp4", ".mp4"
    if getattr(message, "audio", None) or getattr(message, "document", None):
        return "file", mime or "application/octet-stream", getattr(file, "ext", None) or ".bin"
    return None


def _file_name(message: Any, ext: str) -> str:
    file = getattr(message, "file", None)
    name = getattr(file, "name", None)
    if name:
        return os.path.basename(str(name))[:200]
    return f"tg_{getattr(message, 'id', 'x')}{ext}"


async def prepare_inbound(message: Any, peer_id: int) -> tuple[MediaRef | None, str]:
    """Download a Telegram media message to Drive.

    Returns (MediaRef or None, fallback_text). fallback_text is used when the
    media cannot be stored (disabled, too large, unsupported, failure).
    """
    kind = classify(message)
    if kind is None:
        if getattr(message, "sticker", None):
            return await sticker_preview.prepare_inbound_sticker(
                message,
                peer_id,
                enabled=media_enabled(),
                max_bytes=max_bytes(),
                uploader=upload,
                url_builder=proxy_url,
                ref_factory=MediaRef,
            )
        return None, describe_non_file(message)
    amo_type, mime, ext = kind
    name = _file_name(message, ext)
    label = {"picture": "rasm", "voice": "ovozli xabar", "video": "video"}.get(amo_type, "fayl")
    fallback = f"[{label}: {name}]" if amo_type == "file" else f"[{label}]"
    if not media_enabled():
        return None, fallback
    size = int(getattr(getattr(message, "file", None), "size", 0) or 0)
    if size > max_bytes():
        return None, f"[{label}: {name}, {size // (1024 * 1024)} MB — juda katta, Telegramda oching]"
    tmpdir = tempfile.mkdtemp(prefix="tgin_")
    try:
        path = await message.download_media(file=os.path.join(tmpdir, "media" + ext))
        if not path or not os.path.isfile(path):
            return None, fallback
        size = os.path.getsize(path)
        file_id = await upload(path, name, mime, peer_id)
        return MediaRef(amo_type, proxy_url(file_id, mime, name), name, size), ""
    except Exception as exc:
        logger.warning("[TG-AMO] media upload failed: %s", type(exc).__name__)
        return None, fallback
    finally:
        shutil.rmtree(tmpdir, ignore_errors=True)


# ---------------------------------------------------------------- outbound

extract_outbound_media = outbound_media.extract_outbound_media
_validate_outbound_url = outbound_media.validate_outbound_url
cleanup = outbound_media.cleanup


async def fetch_to_temp(url: str, name: str | None) -> str:
    """Stream a validated amoCRM media URL into a temp dir; returns the file path."""
    return await outbound_media.fetch_to_temp(url, name, limit_bytes=max_bytes())


async def archive_outbound(path: str, peer_id: int) -> None:
    """Best-effort copy of a manager-sent file into Drive."""
    await outbound_media.archive_outbound(path, peer_id, enabled=media_enabled(), uploader=upload)
