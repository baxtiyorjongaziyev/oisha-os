"""Signed proxy that serves Telegram media stored in Google Drive to amoCRM.

Drive files stay private; only holders of an HMAC-signed, expiring token
(issued by tg_amo_bridge.media) can fetch them.
"""
from __future__ import annotations

import logging
import os
from urllib.parse import quote

from fastapi import APIRouter, HTTPException
from fastapi.responses import FileResponse

from src.services.core.crm.tg_amo_bridge import media

logger = logging.getLogger("TgMediaProxy")

router = APIRouter(tags=["tg_media"])


def _remove(path: str) -> None:
    try:
        os.unlink(path)
    except OSError:
        pass


class _CleanupFileResponse(FileResponse):
    """FileResponse that always removes its temp file, even on 400/416 range errors."""

    async def __call__(self, scope, receive, send) -> None:
        try:
            await super().__call__(scope, receive, send)
        finally:
            _remove(str(self.path))


@router.get("/tg-media/{token}")
async def get_tg_media(token: str):
    data = media.verify_token(token)
    if data is None:
        raise HTTPException(status_code=404, detail="Not found")
    try:
        path = await media.download_to_temp(str(data["f"]))
    except Exception as exc:
        logger.warning("[TG-MEDIA] drive fetch failed: %s", type(exc).__name__)
        raise HTTPException(status_code=502, detail="Media unavailable") from None
    name = os.path.basename(str(data.get("n") or "file"))
    mime = str(data.get("m") or "application/octet-stream")
    inline = mime.split("/")[0] in {"image", "video", "audio"}
    disposition = f"{'inline' if inline else 'attachment'}; filename*=UTF-8''{quote(name)}"
    return _CleanupFileResponse(
        path,
        media_type=mime,
        headers={
            "Content-Disposition": disposition,
            "Cache-Control": "private, max-age=3600",
            "X-Content-Type-Options": "nosniff",
        },
    )
