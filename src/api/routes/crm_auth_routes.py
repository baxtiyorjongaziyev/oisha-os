"""CRM Seller Authentication & PIN Verification API Routes.

Ushbu marshrutlar sotuvchilar (Shahnoza, Rayxona, Mumtozmaxal, Baxtiyorjon va h.k.)
uchun xavfsiz backend PIN tekshiruvini amalga oshiradi va HttpOnly cookie
hamda sessiya tokeni beradi.

Xavfsizlik qoidalari:
1. Hech qanday maxfiy PIN kod frontendga yoki ommaviy API ga berilmaydi.
2. PIN kodlar bazada faqat PBKDF2-SHA256 xeshlangan holda saqlanadi.
3. Sessiya tokenlari HttpOnly cookie yoki X-CRM-Session-Token sarlavhasi
   orqali uzatiladi.
4. Noto'g'ri urinishlar serverda qat'iy 401 Unauthorized bilan to'xtatiladi.
"""
from __future__ import annotations

import logging
from typing import Any, Dict
from fastapi import APIRouter, Depends, HTTPException, Request, Response, status
from pydantic import BaseModel, Field

from src.api.crm_access import require_crm_permission
from src.services.core.crm.seller_auth import (
    STRONG_PIN_MIN_LENGTH,
    extract_session_token,
    seller_auth_service,
    get_crm_seller_session,
    get_current_crm_seller,
)

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/crm/dialer/auth", tags=["CRM Seller Auth"])

# Same answer for a wrong PIN and an unknown phone/seller: no account enumeration.
INVALID_LOGIN_DETAIL = "Notoʻgʻri PIN-kod yoki xodim topilmadi!"


class SellerLoginPayload(BaseModel):
    slug: str = Field(..., min_length=1, max_length=50, description="Sotuvchi identifikatori")
    pin: str = Field(..., min_length=4, max_length=20, description="Sotuvchining maxfiy PIN-kodi")


class PhoneLoginPayload(BaseModel):
    phone: str = Field(..., min_length=7, max_length=25, description="Sotuvchi telefon raqami")
    pin: str = Field(..., min_length=4, max_length=20, description="Sotuvchining maxfiy PIN-kodi")


class ChangePinPayload(BaseModel):
    old_pin: str = Field(..., min_length=4, max_length=20, description="Amaldagi eski PIN")
    new_pin: str = Field(
        ..., min_length=STRONG_PIN_MIN_LENGTH, max_length=20, description="Yangi 6-20 belgili PIN"
    )


@router.get("/sellers")
async def get_available_sellers() -> Dict[str, Any]:
    """Kirish oynasi uchun ochiq roʻyxat: faqat slug va ism."""
    sellers = seller_auth_service.list_public_sellers()
    return {"success": True, "sellers": sellers}


@router.post("/login")
async def seller_login(payload: SellerLoginPayload, response: Response) -> Dict[str, Any]:
    """Sotuvchi kiritgan PIN-kodni serverda tekshirish va xavfsiz sessiya ochish."""
    retry_after = seller_auth_service.login_retry_after(payload.slug)
    if retry_after:
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail="Juda koʻp notoʻgʻri urinish. Birozdan keyin qayta urinib koʻring.",
            headers={"Retry-After": str(retry_after)},
        )
    auth_result = seller_auth_service.authenticate_seller(
        slug=payload.slug,
        pin=payload.pin,
    )
    if not auth_result:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=INVALID_LOGIN_DETAIL,
        )

    token = auth_result["token"]
    seller = auth_result["seller"]

    # Xavfsiz HttpOnly cookie o'rnatish (30 kunlik)
    response.set_cookie(
        key="crm_session_token",
        value=token,
        max_age=30 * 86400,
        httponly=True,
        samesite="lax",
        secure=True,
        path="/",
    )

    logger.info("CRM Seller authenticated: %s (%s)", seller["name"], seller["slug"])
    return {
        "success": True,
        "token": token,
        "seller": seller,
        "pin_change_required": bool(auth_result.get("must_change_pin")),
        "message": f"Xush kelibsiz, {seller['name']}!",
    }


@router.post("/login-by-phone")
async def seller_login_by_phone(payload: PhoneLoginPayload, response: Response) -> Dict[str, Any]:
    """Telefon raqami orqali sotuvchini aniqlash va PIN bilan kirish."""
    matched_slug = seller_auth_service.find_slug_by_phone(payload.phone)
    if not matched_slug:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail=INVALID_LOGIN_DETAIL)

    return await seller_login(SellerLoginPayload(slug=matched_slug, pin=payload.pin), response)


@router.post("/logout")
async def seller_logout(request: Request, response: Response) -> Dict[str, Any]:
    """Sotuvchi sessiyasini yakunlash va cookie'ni tozalash."""
    token = request.cookies.get("crm_session_token")
    if not token:
        auth_header = request.headers.get("Authorization", "")
        if auth_header.startswith("Bearer "):
            token = auth_header[7:].strip()
        else:
            token = request.headers.get("X-CRM-Session-Token", "")

    if token:
        seller_auth_service.revoke_session(token)

    response.delete_cookie(key="crm_session_token", path="/")
    return {"success": True, "message": "Tizimdan muvaffaqiyatli chiqildi."}


@router.get("/me")
async def get_current_seller(
    current_seller: Dict[str, Any] = Depends(get_crm_seller_session),
) -> Dict[str, Any]:
    """Joriy tizimga kirgan sotuvchi profilini qaytarish."""
    return {
        "success": True,
        "seller": current_seller,
        "pin_change_required": bool(current_seller.get("must_change_pin")),
    }


@router.post("/change-pin")
async def change_seller_pin(
    payload: ChangePinPayload,
    request: Request,
    current_seller: Dict[str, Any] = Depends(get_crm_seller_session),
) -> Dict[str, Any]:
    """Sotuvchi o'zining shaxsiy PIN-kodini o'zgartirishi."""
    retry_after = seller_auth_service.login_retry_after(current_seller["slug"])
    if retry_after:
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail="Juda koʻp notoʻgʻri urinish. Birozdan keyin qayta urinib koʻring.",
            headers={"Retry-After": str(retry_after)},
        )
    ok = seller_auth_service.change_seller_pin(
        slug=current_seller["slug"],
        old_pin=payload.old_pin,
        new_pin=payload.new_pin,
        keep_token=extract_session_token(request, request.headers.get("Authorization")),
    )
    if not ok:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Eski PIN-kod notoʻgʻri yoki yangi PIN talabga javob bermaydi (kamida 6 belgi, eskisidan farqli).",
        )
    return {"success": True, "message": "PIN-kod muvaffaqiyatli yangilandi!"}


@router.get("/admin/sellers")
async def list_sellers_for_admin(
    _actor: Dict[str, Any] = require_crm_permission("manage_users"),
) -> Dict[str, Any]:
    """Administrator: xodimlar va ularning PIN holati."""
    return {"success": True, "sellers": seller_auth_service.list_sellers_for_admin()}


class ResetPinPayload(BaseModel):
    slug: str = Field(..., pattern=r"^[a-z0-9_-]{1,50}$")


@router.post("/admin/reset-pin")
async def reset_seller_pin(
    payload: ResetPinPayload,
    response: Response,
    actor: Dict[str, Any] = require_crm_permission("manage_users"),
) -> Dict[str, Any]:
    """Administrator: xodimga vaqtinchalik PIN berish (faqat shu javobda koʻrinadi)."""
    slug = payload.slug
    temp_pin = seller_auth_service.reset_seller_pin(slug)
    if not temp_pin:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Xodim topilmadi.")
    response.headers["Cache-Control"] = "no-store"
    # The temporary PIN itself is never logged.
    logger.info("CRM seller PIN reset: %s by %s", slug, actor.get("slug"))
    return {"success": True, "slug": slug, "temp_pin": temp_pin}


@router.get("/verify-guard")
async def verify_auth_guard(
    current_seller: Dict[str, Any] = Depends(get_current_crm_seller),
) -> Dict[str, Any]:
    """Tizim himoyalanganligini tekshirish uchun test endpoint."""
    return {
        "status": "protected",
        "authenticated_as": current_seller["name"],
        "role": current_seller["role"],
    }
