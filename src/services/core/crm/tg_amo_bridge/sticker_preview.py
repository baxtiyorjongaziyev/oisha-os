"""Preview extraction for Telegram animated (.tgs) and video (.webm) stickers.

amoCRM renders static raster images (WebP/PNG/JPEG) inline via ``type="picture"``,
whereas raw Lottie ``.tgs`` files cannot be displayed and ``.webm`` video stickers
fail on Safari/iOS players. This module extracts Telegram's built-in raster
thumbnail (or frame 0 via ``ffmpeg`` for ``.webm``) and falls back to
``[stiker <emoji>]`` when no valid image can be obtained.
"""
from __future__ import annotations

import asyncio
import logging
import os
import shutil
import tempfile
from typing import Any, Awaitable, Callable, Optional, Tuple

logger = logging.getLogger("TgAmoBridge.sticker_preview")

_SKIP_THUMB_TYPES = frozenset({"PhotoPathSize", "PhotoSizeEmpty", "VideoSize"})
_FFMPEG_TIMEOUT_SECONDS = 10.0


def _sticker_docs(message: Any) -> Tuple[Any, ...]:
    docs = []
    for attr_name in ("sticker", "document"):
        obj = getattr(message, attr_name, None)
        if obj is not None and obj not in docs:
            docs.append(obj)
    return tuple(docs)


def sticker_emoji(message: Any) -> str:
    """Return the alt emoji attribute of a Telegram sticker, or empty string."""
    for doc in _sticker_docs(message):
        for attr in getattr(doc, "attributes", None) or []:
            alt = getattr(attr, "alt", None)
            if alt:
                return str(alt)
    return ""


def sticker_fallback_text(message: Any) -> str:
    """Plain-text placeholder when a sticker cannot be rendered as an image."""
    emoji = sticker_emoji(message)
    return f"[stiker {emoji}]" if emoji else "[stiker]"


def detect_image_format(path: str) -> Optional[Tuple[str, str]]:
    """Identify raster image ``(mime_type, ext)`` from magic bytes, else ``None``."""
    try:
        with open(path, "rb") as fh:
            head = fh.read(16)
    except OSError:
        return None
    if len(head) < 4:
        return None
    if head.startswith(b"\x89PNG\r\n\x1a\n"):
        return "image/png", ".png"
    if head.startswith(b"\xff\xd8\xff"):
        return "image/jpeg", ".jpg"
    if len(head) >= 12 and head[:4] == b"RIFF" and head[8:12] == b"WEBP":
        return "image/webp", ".webp"
    if head[:6] in (b"GIF87a", b"GIF89a"):
        return "image/gif", ".gif"
    return None


def select_raster_thumb(message: Any) -> Any:
    """Pick the largest static raster thumb object, ``-1`` if absent, or ``None``.

    When ``document.thumbs`` is a non-empty list containing only non-raster
    entries (e.g. ``PhotoPathSize`` SVG outlines or ``VideoSize``), returns
    ``None`` so we avoid Telethon's ``IndexError`` and skip wasted downloads.
    """
    thumbs = None
    for doc in _sticker_docs(message):
        candidate = getattr(doc, "thumbs", None)
        if isinstance(candidate, (list, tuple)):
            thumbs = candidate
            break
    if thumbs is None or not thumbs:
        return -1
    best: Any = None
    best_size = -1
    for thumb in thumbs:
        if type(thumb).__name__ in _SKIP_THUMB_TYPES:
            continue
        sizes = getattr(thumb, "sizes", None)
        raw_bytes = getattr(thumb, "bytes", None)
        if isinstance(sizes, (list, tuple)) and sizes:
            size = int(max(sizes))
        elif isinstance(getattr(thumb, "size", None), int):
            size = int(thumb.size)
        elif isinstance(raw_bytes, (bytes, bytearray)):
            size = len(raw_bytes)
        else:
            size = 0
        if size >= best_size:
            best = thumb
            best_size = size
    return best


async def _download_thumb(message: Any, tmpdir: str) -> Optional[Tuple[str, str, str]]:
    thumb = select_raster_thumb(message)
    if thumb is None:
        return None
    target = os.path.join(tmpdir, "sticker_thumb")
    try:
        path = await message.download_media(file=target, thumb=thumb)
    except Exception as exc:
        logger.debug("[TG-AMO] sticker thumb download skipped: %s", type(exc).__name__)
        return None
    if not path or not os.path.isfile(path) or os.path.getsize(path) == 0:
        return None
    detected = detect_image_format(path)
    if detected is None:
        return None
    mime, ext = detected
    return path, mime, ext


async def _extract_webm_frame(
    message: Any, tmpdir: str, max_bytes: int
) -> Optional[Tuple[str, str, str]]:
    ffmpeg = shutil.which("ffmpeg")
    if not ffmpeg:
        return None
    size = int(getattr(getattr(message, "file", None), "size", 0) or 0)
    if size > max_bytes:
        return None
    src_path = await message.download_media(file=os.path.join(tmpdir, "sticker.webm"))
    if (
        not src_path
        or not os.path.isfile(src_path)
        or os.path.getsize(src_path) == 0
        or os.path.getsize(src_path) > max_bytes
    ):
        return None
    out_path = os.path.join(tmpdir, "sticker_frame.png")
    proc = await asyncio.create_subprocess_exec(
        ffmpeg,
        "-y",
        "-loglevel",
        "error",
        "-i",
        src_path,
        "-frames:v",
        "1",
        out_path,
        stdout=asyncio.subprocess.DEVNULL,
        stderr=asyncio.subprocess.DEVNULL,
    )
    try:
        await asyncio.wait_for(proc.wait(), timeout=_FFMPEG_TIMEOUT_SECONDS)
    except asyncio.TimeoutError:
        proc.kill()
        await proc.wait()
        return None
    if proc.returncode != 0 or not os.path.isfile(out_path):
        return None
    detected = detect_image_format(out_path)
    if detected is None:
        return None
    return out_path, detected[0], detected[1]


async def download_preview(
    message: Any, tmpdir: str, *, max_bytes: int
) -> Optional[Tuple[str, str, str]]:
    """Return ``(local_path, mime, ext)`` for a sticker preview, or ``None``."""
    preview = await _download_thumb(message, tmpdir)
    if preview is not None:
        return preview
    mime = (getattr(getattr(message, "file", None), "mime_type", None) or "").lower()
    if mime == "video/webm":
        return await _extract_webm_frame(message, tmpdir, max_bytes)
    return None


async def prepare_inbound_sticker(
    message: Any,
    peer_id: int,
    *,
    enabled: bool,
    max_bytes: int,
    uploader: Callable[[str, str, str, int], Awaitable[str]],
    url_builder: Callable[[str, str, str], str],
    ref_factory: Callable[[str, str, str, int], Any],
) -> Tuple[Optional[Any], str]:
    """Upload a static preview for animated/video stickers, or fall back to text."""
    fallback = sticker_fallback_text(message)
    if not enabled:
        return None, fallback
    tmpdir = tempfile.mkdtemp(prefix="tgstk_")
    try:
        preview = await download_preview(message, tmpdir, max_bytes=max_bytes)
        if preview is None:
            return None, fallback
        path, mime, ext = preview
        name = f"tg_{getattr(message, 'id', 'x')}_sticker{ext}"
        size = os.path.getsize(path)
        file_id = await uploader(path, name, mime, peer_id)
        return ref_factory("picture", url_builder(file_id, mime, name), name, size), ""
    except Exception as exc:
        logger.warning("[TG-AMO] sticker preview failed: %s", type(exc).__name__)
        return None, fallback
    finally:
        shutil.rmtree(tmpdir, ignore_errors=True)
