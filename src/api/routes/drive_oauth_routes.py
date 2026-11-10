"""FastAPI endpoints for owner-approved Google Drive connection.

These routes rely on random one-time Telegram-issued tickets (and Google
CSRF state); they never accept a browser-supplied owner ID or password.
"""
from __future__ import annotations

import logging

from fastapi import APIRouter, HTTPException
from fastapi.responses import HTMLResponse, RedirectResponse

from src.services.core.crm.drive_oauth_onboarding import (
    begin_authorization,
    complete_authorization,
)

router = APIRouter(tags=["gdrive-onboarding"])
logger = logging.getLogger(__name__)
SECURE_HEADERS = {
    "Cache-Control": "no-store",
    "Referrer-Policy": "no-referrer",
    "X-Content-Type-Options": "nosniff",
}


@router.get("/api/integrations/gdrive/connect")
async def gdrive_connect(ticket: str = ""):
    try:
        url = await begin_authorization(ticket)
    except PermissionError:
        raise HTTPException(status_code=403, detail="Link expired or used") from None
    except RuntimeError:
        logger.warning("GDrive OAuth configuration unavailable")
        raise HTTPException(status_code=503, detail="Google Drive OAuth unavailable") from None
    response = RedirectResponse(url, status_code=303)
    response.headers.update(SECURE_HEADERS)
    return response


@router.get("/api/integrations/gdrive/callback")
async def gdrive_callback(
    state: str = "", code: str = "", error: str = "",
):
    if error:
        raise HTTPException(status_code=403, detail="Google consent was not granted")
    try:
        info = await complete_authorization(state, code)
    except PermissionError:
        raise HTTPException(status_code=403, detail="Google account/state rejected") from None
    except Exception:
        logger.exception("Google Drive authorization or verification failed")
        raise HTTPException(status_code=503, detail="Google Drive authorization failed") from None
    message = (
        "<html><head><meta charset='utf-8'></head>"
        "<body><h2>Google Drive muvaffaqiyatli ulandi</h2>"
        "<p>Ruxsat xavfsiz saqlandi. Endi bu oynani yopishingiz mumkin.</p>"
        "<p>Hisob: " + info["email"] + "</p>"
        "</body></html>"
    )
    return HTMLResponse(content=message, headers=SECURE_HEADERS)
