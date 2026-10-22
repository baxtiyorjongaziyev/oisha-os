"""Attendance kalitlari.

``ATTENDANCE_QR_SECRET`` o'rnatilgan bo'lsa — shu ishlatiladi. Aks holda mavjud kuchli
sessiya kalitidan (``JWT_SECRET``/``OISHA_API_SECRET``) HMAC orqali alohida maqsadli kalit
hosil qilinadi: serverga yangi sir qo'shmasdan ishga tushadi, QR kaliti esa sessiya
kalitining o'zi emas (domain separation). Ikkalasi ham yo'q bo'lsa — bo'sh (fail-closed).
"""
from __future__ import annotations

import hashlib
import hmac
import os

_LABEL = b"oisha-attendance-qr-v1"
_MIN = 32


def qr_secret() -> str:
    explicit = os.getenv("ATTENDANCE_QR_SECRET", "").strip()
    if len(explicit) >= _MIN:
        return explicit
    try:
        from src.api.security import _session_secret

        base = _session_secret()
    except Exception:
        base = ""
    if len(base.encode("utf-8")) < _MIN:
        return ""
    return hmac.new(base.encode("utf-8"), _LABEL, hashlib.sha256).hexdigest()
