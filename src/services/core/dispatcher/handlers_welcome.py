"""Bot API 10.5: taklif havolasi orqali kelgan foydalanuvchini kutib olish matnlari.

``write_access_allowed`` xizmat xabari polling yoʻlida raw middleware orqali
``ai_features.workflows.handle_botnews_service_update`` ga tushadi; u shu yerdagi
matnlarni ishlatadi. Faqat ``inviter`` boʻlgan (taklif havolasi) holatda
onboarding koʻrsatmasi va egaga xabar yuboriladi.
"""
from __future__ import annotations

import html
import os
from typing import Any, Mapping, Optional

GENERIC_TEXT = "Assalomu alaykum{name}! Oisha-OS tizimiga xush kelibsiz."
INVITE_TEXT = (
    "👋 Assalomu alaykum{name}! Men Oisha — Jon Branding ichki yordamchisiman.\n\n"
    "Boshlash uchun <code>/ulanish Ism Familiya</code> yuboring, "
    "shunda sizni xodimlar roʻyxatiga bogʻlayman."
)


def build_welcome_text(first_name: Optional[str], *, invited: bool = True) -> str:
    clean = (first_name or "").strip()
    name = f", {html.escape(clean)}" if clean else ""
    return (INVITE_TEXT if invited else GENERIC_TEXT).format(name=name)


def build_owner_notice_from_dict(user: Mapping[str, Any]) -> str:
    first = str(user.get("first_name") or "")
    username = user.get("username")
    tag = f" @{username}" if username else ""
    return f"🆕 Botga taklif orqali yangi foydalanuvchi qoʻshildi: {first}{tag} (id {user.get('id', '?')})"


def owner_id_from_env() -> int:
    try:
        return int((os.getenv("OWNER_ID") or "0").strip() or 0)
    except ValueError:
        return 0
