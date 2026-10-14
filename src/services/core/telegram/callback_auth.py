"""Inline-tugma callback'lari uchun ruxsat tekshiruvi.

`callback_data` foydalanuvchi kiritmasi: MTProto mijozi (`messages.getBotCallbackAnswer`)
bot yuborgan, o'zi ko'ra oladigan istalgan xabar ustida ixtiyoriy data yubora
oladi. Shuning uchun xabar qaysi chatda turgani (guruh a'zoligi) ruxsat emas —
moliyaviy mutatsiyani faqat aniq ruxsat berilgan foydalanuvchi bajaradi:

* ``OWNER_ID`` va ``WHITELIST_IDS``;
* ``MOLIYACHI_TELEGRAM_ID`` (moliyachi);
* ``FINANCE_APPROVER_IDS`` — vergul bilan qo'shimcha tasdiqlovchilar.
"""
from __future__ import annotations

import os
from typing import Any

from src.settings import settings


def _as_int(value: Any) -> int:
    try:
        return int(str(value).strip() or 0)
    except (TypeError, ValueError):
        return 0


def finance_approver_ids() -> set[int]:
    ids = {_as_int(item) for item in (getattr(settings, "WHITELIST_IDS", None) or [])}
    ids.add(_as_int(getattr(settings, "OWNER_ID", 0)))
    ids.add(_as_int(os.getenv("MOLIYACHI_TELEGRAM_ID", "")))
    ids.update(_as_int(x) for x in os.getenv("FINANCE_APPROVER_IDS", "").split(","))
    ids.discard(0)
    return ids


def is_trusted_finance_callback(callback: Any) -> bool:
    """Aiogram CallbackQuery moliyaviy amalni bajarishga ruxsatlimi."""
    user_id = _as_int(getattr(getattr(callback, "from_user", None), "id", 0))
    return bool(user_id) and user_id in finance_approver_ids()
