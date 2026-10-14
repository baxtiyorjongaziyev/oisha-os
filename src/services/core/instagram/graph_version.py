"""Meta Graph API versiyasi — yagona manba.

Prod'da `META_GRAPH_API_VERSION` env orqali boshqariladi; berilmasa DEFAULT ishlatiladi.
Meta eskirgan versiyani so'raganda o'zi yangisiga ko'taradi (meta_health_check buni
`facebook-api-version` header orqali aniqlaydi) — shuning uchun DEFAULT'ni yangilab turing.
"""
from __future__ import annotations

import os

DEFAULT_GRAPH_API_VERSION = "v25.0"


def graph_api_version() -> str:
    return os.environ.get("META_GRAPH_API_VERSION", "").strip() or DEFAULT_GRAPH_API_VERSION


def graph_base() -> str:
    return f"https://graph.facebook.com/{graph_api_version()}"
