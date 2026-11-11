"""Juma tabrigi matni va yuborish oynasi — sof (tarmoqsiz) yordamchi modul.

Maqsad: har bir odamga ALOHIDA, qoʻlda yozilgandek qisqa tabrik. Odamlar bir
biriga odatda bir-ikki gapli sodda tabrik yuboradi ("Juma muborak, duolaringiz
ijobat boʻlsin"), uch boʻgʻinli tantanali duolar zanjiri emas — shuning uchun
boʻlaklar qisqa, emoji kam (koʻpincha umuman yoʻq) va bitta jarayonda ikki
kishiga bir xil matn ketmaydi.

Matn (user_id, hafta) boʻyicha deterministik: skript shu hafta ichida qayta
ishga tushsa ham bir odamga oʻsha matn chiqadi.
"""
from __future__ import annotations

import hashlib
import random
import re
from datetime import datetime, timedelta
from typing import Optional

_OPENERS = (
    "Assalomu alaykum",
    "Assalomu alaykum",
    "Assalomu alaykum",
    "Assalomu alaykum va rahmatullohi va barokatuh",
    "Assalomu alaykum va rahmatulloh",
)

_JUMA_PHRASES = (
    "Juma muborak",
    "Juma muborak boʻlsin",
    "Juma ayyomingiz muborak boʻlsin",
    "Jumangiz muborak boʻlsin",
    "Juma ayyomi muborak",
    "Muborak juma ayyomi bilan tabriklayman",
)

#: Boʻsh satr — tilaksiz, faqat tabrikning oʻzi (odamlar koʻpincha shunday yozadi).
_WISHES = (
    "",
    "",
    "Duolaringiz ijobat boʻlsin",
    "Alloh duolaringizni qabul qilsin",
    "Qilgan duolaringiz ijobat boʻlsin",
    "Oilangizga tinchlik, ishlaringizga baraka tilayman",
    "Ishlaringizga baraka bersin",
    "Kuningiz xayrli oʻtsin",
    "Uyingizga fayz, rizqingizga baraka bersin",
    "Alloh niyatlaringizga yetkazsin",
    "Yaxshi niyatlaringiz amalga oshsin",
    "Sogʻ-salomat boʻling, ishlaringiz yurishsin",
    "Oilangiz bilan tinch-omon boʻling",
    "Alloh hamma ishlaringizni oson qilsin",
    "Duolarda eslab qoʻying",
    "Ota-onangizga sihat-salomatlik tilayman",
    "Xonadoningizdan fayz-baraka arimasin",
    "Bugungi kun barchamizga xayrli boʻlsin",
)

_EMOJI = ("", "", "", "", "", " 🤲", " 🤲", " 🌙")

#: Ism sifatida ishlatib boʻlmaydigan soʻzlar (kontakt nomlari, rollar, laqablar).
_NAME_STOPWORDS = frozenset(
    {
        "admin", "test", "bot", "user", "telegram", "account", "deleted",
        "tn", "gr", "tez", "natija", "aka", "opa", "uka", "singil", "ustoz",
        "doʻstim", "dostim", "mijoz", "client", "manager", "menejer", "sales",
        "official", "group", "channel", "kanal", "shop", "store", "market",
        "brand", "branding", "studio", "agency", "media", "smm", "dizayn",
    }
)

_NAME_RE = re.compile(r"^[A-Za-zÀ-žА-Яа-яЁёЎўҚқҒғҲҳʻʼ‘’'`]{3,14}$")
_TN_PREFIX_RE = re.compile(r"^\s*TN\s*\d*\s*Gr\.?\s+", re.IGNORECASE)


def clean_first_name(raw: Optional[str]) -> str:
    """Telegram profilidagi ismdan murojaatga yaroqli ism ajratadi.

    Notoʻgʻri ism bilan murojaat qilish — avtomatik xabarning eng aniq belgisi,
    shuning uchun shubhali holatda boʻsh satr qaytadi (ismsiz tabrik ketadi).
    """
    if not raw:
        return ""
    text = _TN_PREFIX_RE.sub("", str(raw)).strip()
    parts = text.split()
    if len(parts) != 1:
        return ""
    name = parts[0]
    if not _NAME_RE.match(name):
        return ""
    if name.lower() in _NAME_STOPWORDS:
        return ""
    if name.isupper() or name.islower():
        name = name.capitalize()
    return name


def _compose(rng: random.Random, name: str) -> str:
    opener = rng.choice(_OPENERS)
    juma = rng.choice(_JUMA_PHRASES)
    wish = rng.choice(_WISHES)
    emoji = rng.choice(_EMOJI)

    # Ism har doim ham aytilmaydi — odamlar ham har xabarda ism yozmaydi.
    if name and rng.random() < 0.7:
        head = f"{opener}, {name}"
    else:
        head = opener
    head += rng.choice((".", "!", "."))

    juma_end = rng.choice(("!", ".", "!")) if wish else rng.choice(("!", "!", "."))
    text = f"{head} {juma}{juma_end}"
    if wish:
        text += f" {wish}{rng.choice(('.', '.', '', '!'))}"
    return text + emoji


def build_juma_greeting(
    user_id: int,
    first_name: Optional[str],
    week_key: str,
    used: Optional[set] = None,
) -> str:
    """Bitta odam uchun tabrik matni.

    Args:
        user_id: Telegram user ID (deterministik tanlov uchun).
        first_name: Profil ismi (tozalanadi; yaroqsiz boʻlsa ishlatilmaydi).
        week_key: Hafta kaliti, masalan broadcast boshlangan Payshanba sanasi.
        used: Shu jarayonda yuborilgan matnlar toʻplami — berilsa, takror
            matn chiqmaslikka harakat qilinadi va natija shu toʻplamga qoʻshiladi.
    """
    name = clean_first_name(first_name)
    text = ""
    for attempt in range(40):
        digest = hashlib.sha256(f"{week_key}:{user_id}:{attempt}".encode()).digest()
        rng = random.Random(int.from_bytes(digest[:8], "big"))
        text = _compose(rng, name)
        if used is None or text not in used:
            break
    if used is not None:
        used.add(text)
    return text


def juma_window(
    now: datetime, shom_hour: int, shom_minute: int
) -> Optional[tuple[datetime, datetime]]:
    """Yuborish oynasi: (broadcast boshlangan Payshanba, Juma Shomi deadline).

    Payshanba kuni yoki Juma kuni Shomgacha ishga tushsa oyna ochiq. GitHub
    schedule bir necha soat kechikib, Juma tuni (00:00 dan keyin) boshlanishi
    mumkin — bu ham oʻsha haftaning oynasi, yangi hafta emas. Boshqa payt None.
    """
    shom_today = now.replace(
        hour=shom_hour, minute=shom_minute, second=0, microsecond=0
    )
    if now.weekday() == 3:  # Payshanba
        return now, shom_today + timedelta(days=1)
    if now.weekday() == 4 and now < shom_today:  # Juma, Shomgacha
        return now - timedelta(days=1), shom_today
    return None
