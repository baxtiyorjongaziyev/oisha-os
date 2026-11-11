"""Meta Ad Library havola generatori (qoʻlda koʻrib chiqish uchun).

Meta Ad Library API (``ads_archive``) EI ga yetmagan tijoriy reklamalarni
qaytarmaydi, yaʼni Oʻzbekistondagi raqobatchi va lid reklamalari API orqali
koʻrinmaydi. Shuning uchun Oisha API chaqirmaydi va sahifani scraping
qilmaydi: u faqat ommaviy Ad Library qidiruv havolasini yasaydi, sotuvchi
uni ochib oʻzi koʻrib chiqadi.
"""
from __future__ import annotations

import re
from typing import List, Optional
from urllib.parse import urlencode, urlparse

AD_LIBRARY_BASE = "https://www.facebook.com/ads/library/"
DEFAULT_COUNTRY = "UZ"
MAX_QUERY_LEN = 100

_SOCIAL_HOSTS = ("instagram.com", "facebook.com", "fb.com")
# Profil emas, post/reel/xizmat sahifalari — ulardan sahifa nomini olib boʻlmaydi.
_RESERVED_PATHS = {
    "p", "reel", "reels", "stories", "explore", "tv", "accounts", "direct",
    "profile.php", "people", "pages", "groups", "watch", "share", "ads",
    "events", "marketplace", "photo", "photo.php", "story.php", "login",
}
_SOCIAL_URL_RE = re.compile(
    r"(?:https?://)?(?:www\.|m\.)?(?:instagram\.com|facebook\.com|fb\.com)/[^\s<>\"')\]]+",
    re.IGNORECASE,
)


def build_ad_library_url(query: str, country: str = DEFAULT_COUNTRY) -> str:
    """Faol reklamalar boʻyicha Ad Library qidiruv havolasini qaytaradi."""
    query = (query or "").strip()[:MAX_QUERY_LEN]
    if not query:
        raise ValueError("Ad Library qidiruvi uchun soʻrov boʻsh")
    params = {
        "active_status": "active",
        "ad_type": "all",
        "country": country.upper(),
        "q": query,
        "search_type": "keyword_unordered",
        "media_type": "all",
    }
    return f"{AD_LIBRARY_BASE}?{urlencode(params)}"


def _handle_from_social_url(raw: str) -> Optional[str]:
    url = raw if raw.lower().startswith(("http://", "https://")) else f"https://{raw}"
    parsed = urlparse(url)
    host = parsed.netloc.lower()
    if not any(host == h or host.endswith(f".{h}") for h in _SOCIAL_HOSTS):
        return None
    parts = [p for p in parsed.path.split("/") if p]
    if not parts or parts[0].lower() in _RESERVED_PATHS:
        return None
    return parts[0].lstrip("@") or None


def extract_page_query(raw: str) -> Optional[str]:
    """Instagram/Facebook havola, @username yoki brend nomidan qidiruv soʻzini oladi."""
    raw = (raw or "").strip()
    if not raw:
        return None
    if _SOCIAL_URL_RE.fullmatch(raw):
        return _handle_from_social_url(raw)
    if raw.lower().startswith(("http://", "https://")):
        return None  # Ijtimoiy tarmoq boʻlmagan havola
    query = raw.lstrip("@").strip()
    return query[:MAX_QUERY_LEN] or None


def find_social_page_queries(text: str, limit: int = 3) -> List[str]:
    """Matndagi Instagram/Facebook profil havolalaridan takrorlanmas qidiruv soʻzlari."""
    found: List[str] = []
    for match in _SOCIAL_URL_RE.finditer(text or ""):
        handle = _handle_from_social_url(match.group(0).rstrip(".,;:!?"))
        if handle and handle.lower() not in {h.lower() for h in found}:
            found.append(handle)
        if len(found) >= limit:
            break
    return found


USAGE_TEXT = (
    "Foydalanish: /adlib <Instagram yoki Facebook havola, @username yoki brend nomi>\n"
    "Misol: /adlib https://instagram.com/brand_uz"
)


def format_ad_library_reply(arg: str) -> str:
    """/adlib buyrugʻi uchun Telegram javob matni."""
    query = extract_page_query(arg)
    if not query:
        return USAGE_TEXT
    url = build_ad_library_url(query)
    return (
        f"📢 Meta Ad Library: {query} (Oʻzbekiston, faol reklamalar)\n"
        f"{url}\n\n"
        "Havolani ochib tekshiring: reklama bormi, nechta, qaysi formatda va "
        "qachondan beri ishlayapti.\n"
        "Natija boʻsh chiqsa, brend nomi bilan qayta qidiring: /adlib <brend nomi>\n"
        "ℹ️ Bu havola qoʻlda koʻrib chiqish uchun: Meta API Oʻzbekistondagi tijoriy "
        "reklamalarni bermaydi."
    )
