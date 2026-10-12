"""Lid manbasini 7 toifadan biriga ajratish + telefon xeshi bo'yicha sayt tashrifiga bog'lash.

Toifalar (ustuvorlik tartibida — reklamani bosib, saytga kirib, keyin qo'ng'iroq qilgan
odamning manbasi reklama; qo'ng'iroq faqat boshqa iz bo'lmaganda manba bo'ladi):
    reklama → qidiruv → facebook_organik → instagram_organik → sayt_organik
    → kiruvchi_qongiroq → noaniq

Telefon raqami saqlanmaydi: faqat SHA-256 xeshi (`site_visits`), 30 kun.
"""
from __future__ import annotations

import hashlib
import json
import re
import sqlite3
import time
from contextlib import contextmanager
from pathlib import Path
from typing import Dict, Optional

AD, CALL, SEARCH = "reklama", "kiruvchi_qongiroq", "qidiruv"
SITE, FB, IG, UNKNOWN = "sayt_organik", "facebook_organik", "instagram_organik", "noaniq"
LABELS = {
    AD: "Reklama", CALL: "Kiruvchi qo'ng'iroq", SEARCH: "Qidiruv", SITE: "Saytdan organik",
    FB: "Facebook organik", IG: "Instagram organik", UNKNOWN: "Noaniq",
}

_PAID_MEDIUMS = {"cpc", "ppc", "paid", "paid_social", "paidsocial", "ads", "cpm", "target", "targeting"}
_SEARCH_HOSTS = ("google.", "yandex.", "bing.", "duckduckgo.", "yahoo.", "mail.ru", "ya.ru")
VISIT_TTL_SEC = 30 * 86400

_DB_PATH = Path(__file__).resolve().parents[4] / "data" / "site_visits.db"


def _host(url: str) -> str:
    m = re.match(r"^[a-z]+://([^/:?#]+)", (url or "").strip().lower())
    return m.group(1) if m else ""


def classify(tracking: Optional[Dict[str, str]] = None, *, leadgen: bool = False,
             incoming_call: bool = False) -> str:
    t = {k: str(v or "").strip().lower() for k, v in (tracking or {}).items()}
    source, medium = t.get("utm_source", ""), t.get("utm_medium", "")
    if leadgen or t.get("campaign_id") or t.get("fbclid") or t.get("gclid") or t.get("yclid"):
        return AD
    # Faqat utm_source=instagram (medium'siz) — bio/post havolasi bo'lishi mumkin, reklama emas.
    if medium in _PAID_MEDIUMS:
        return AD
    ref = _host(t.get("referrer", ""))
    if source in {"google", "yandex", "bing"} or any(h in ref for h in _SEARCH_HOSTS):
        return SEARCH
    if source in {"facebook", "fb"} or "facebook." in ref or ref == "fb.com" or ref.endswith(".fb.com"):
        return FB
    if source in {"instagram", "ig"} or "instagram." in ref:
        return IG
    if t.get("page_url") or t.get("landing_url") or ref or source:
        return SITE
    if incoming_call:
        return CALL
    return UNKNOWN


def hash_phone(phone: str) -> str:
    digits = re.sub(r"\D", "", phone or "")
    if len(digits) == 9:
        digits = "998" + digits
    return hashlib.sha256(digits.encode()).hexdigest() if digits else ""


@contextmanager
def _connection():
    _DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    with sqlite3.connect(_DB_PATH, timeout=10) as conn:
        conn.execute(
            "CREATE TABLE IF NOT EXISTS site_visits (phone_hash TEXT PRIMARY KEY, ts REAL, tracking TEXT)"
        )
        yield conn


def remember_visit(phone: str, tracking: Dict[str, str], now: Optional[float] = None) -> None:
    """Saytda telefon qoldirgan tashrif izini yozadi (birinchi reklama izi ustun saqlanadi)."""
    ph = hash_phone(phone)
    if not ph or not tracking:
        return
    now = now or time.time()
    with _connection() as conn:
        row = conn.execute("SELECT ts, tracking FROM site_visits WHERE phone_hash = ?", (ph,)).fetchone()
        if row and now - row[0] < VISIT_TTL_SEC and classify(json.loads(row[1])) == AD \
                and classify(tracking) != AD:
            return  # avvalgi reklama izini organik tashrif bilan yo'qotmaymiz
        conn.execute("INSERT OR REPLACE INTO site_visits VALUES (?, ?, ?)", (ph, now, json.dumps(tracking)))
        conn.execute("DELETE FROM site_visits WHERE ts < ?", (now - VISIT_TTL_SEC,))


def visit_for_phone(phone: str, now: Optional[float] = None) -> Optional[Dict[str, str]]:
    ph = hash_phone(phone)
    if not ph:
        return None
    with _connection() as conn:
        row = conn.execute("SELECT ts, tracking FROM site_visits WHERE phone_hash = ?", (ph,)).fetchone()
    if not row or (now or time.time()) - row[0] > VISIT_TTL_SEC:
        return None
    return json.loads(row[1])


def source_for_incoming_call(phone: str) -> str:
    """Kiruvchi qo'ng'iroq: avval saytdagi izni qidiradi, topilmasa — kiruvchi qo'ng'iroq."""
    visit = visit_for_phone(phone)
    return classify(visit, incoming_call=True) if visit else CALL


def tag_for(category: str) -> str:
    return f"manba:{category}"
