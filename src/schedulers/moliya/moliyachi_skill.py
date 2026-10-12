"""Moliyachi (Dilbar) ish tartibini kuzatib, "skill" (ish qo'llanmasi) shakllantirish.

Hisobchi hech narsa yozmaydi va hech kimga javob bermaydi. Faqat:

* Telegram moliya guruhidagi moliyachi harakatlarini **metadata** sifatida yozadi
  (turi: matn/rasm/ovoz/hujjat, topik, summa bormi, soat) — matn saqlanmaydi;
* Airtable ``Tranzaksiyalar`` dagi bugun yaratilgan yozuvlarni (``createdTime``)
  hodisa sifatida qo'shadi;
* hodisalarni vaqt bo'yicha tartiblab, ketma-ketlik (A → B) va kunlik ritmni
  to'playdi — profil har kuni boyib boradi;
* profildan Markdown skill hujjati yasaydi va har yakshanba egasiga yuboradi.

Raqam to'qilmaydi: kuzatuv bo'lmasa "ma'lumot yetarli emas" deyiladi.
"""

from __future__ import annotations

import logging
import os
import re
from collections import Counter
from datetime import datetime
from typing import Any, Optional

from src.schedulers.moliya.helpers import select_name
from src.schedulers.moliya.kuzatuv import _first_link, learn_rules, quality_gaps

logger = logging.getLogger(__name__)

ACTIVITY_PREFIX = "moliyachi_activity_"
PROFILE_KEY = "moliyachi_skill_profile"
MAX_EVENTS_PER_DAY = 500
_AMOUNT_RE = re.compile(r"\d[\d\s.,]{2,}")

ACTION_LABELS = {
    "tg_text": "Guruhga matn yozdi",
    "tg_photo": "Guruhga chek/rasm yubordi",
    "tg_voice": "Guruhga ovozli xabar yubordi",
    "tg_document": "Guruhga hujjat yubordi",
    "at_kirim": "Airtable'ga KIRIM kiritdi",
    "at_chiqim": "Airtable'ga CHIQIM kiritdi",
    "at_other": "Airtable'ga boshqa yozuv kiritdi",
    "gm_in": "Gmail'ga xat keldi",
    "gm_out": "Gmail'dan xat yubordi",
    "xl_edit": "Excel/Sheets jadvalini tahrirladi",
}


def moliyachi_telegram_id() -> int:
    try:
        return int(os.getenv("MOLIYACHI_TELEGRAM_ID", "0") or 0)
    except ValueError:
        return 0


def moliyachi_username() -> str:
    raw = os.getenv("MOLIYACHI_TELEGRAM_USERNAME", "").strip() or "jonbranding_finansist"
    return raw.lstrip("@").lower()


def is_moliyachi(sender_id: int, username: str) -> bool:
    """ID yoki username mos kelsa — moliyachi. Ikkalasi ham bo'sh bo'lsa hammasi."""
    expected_id = moliyachi_telegram_id()
    expected_name = moliyachi_username()
    if not expected_id and not expected_name:
        return True
    if expected_id and int(sender_id or 0) == expected_id:
        return True
    return bool(expected_name) and (username or "").lstrip("@").lower() == expected_name


def classify_message(message: Any) -> str:
    if getattr(message, "photo", None):
        return "tg_photo"
    if getattr(message, "voice", None):
        return "tg_voice"
    if getattr(message, "document", None):
        return "tg_document"
    return "tg_text"


async def record_activity(
    *, action: str, ts: datetime, topic: str = "", has_amount: bool = False
) -> None:
    """Bitta harakatni kunlik ro'yxatga qo'shadi (matnsiz)."""
    try:
        from src.db import get_db

        key = ACTIVITY_PREFIX + ts.strftime("%Y-%m-%d")
        db = get_db()
        events = await db.get_state(key, []) or []
        if len(events) >= MAX_EVENTS_PER_DAY:
            return
        events.append(
            {"t": ts.strftime("%H:%M"), "a": action, "topic": topic, "amount": bool(has_amount)}
        )
        await db.set_state(key, events)
    except Exception:
        logger.warning("[MOLIYACHI] Harakat yozilmadi", exc_info=True)


async def observe_finance_message(
    event: Any, *, kirim_topic_id: Any, chiqim_topic_id: Any, sender: Any = None
) -> None:
    """Moliya guruhidagi xabarni moliyachi harakati sifatida qayd etadi."""
    if not is_moliyachi(
        int(getattr(event, "sender_id", 0) or 0), str(getattr(sender, "username", "") or "")
    ):
        return
    from src.time_utils import get_local_now

    message = getattr(event, "message", None)
    reply_to = getattr(message, "reply_to", None)
    topic_id = getattr(reply_to, "reply_to_msg_id", None) if reply_to else None
    topic = "kirim" if topic_id and topic_id == kirim_topic_id else (
        "chiqim" if topic_id and topic_id == chiqim_topic_id else ""
    )
    text = str(getattr(message, "message", "") or "")
    await record_activity(
        action=classify_message(message),
        ts=get_local_now(),
        topic=topic,
        has_amount=bool(_AMOUNT_RE.search(text)),
    )


def airtable_events(records: list[dict], day: str) -> list[dict]:
    """Bugun yaratilgan Tranzaksiyalar → hodisalar (createdTime UTC → Toshkent +5)."""
    events = []
    for rec in records:
        created = str(rec.get("createdTime") or "")
        try:
            dt = datetime.fromisoformat(created.replace("Z", "+00:00"))
        except ValueError:
            continue
        from datetime import timedelta, timezone

        local = dt.astimezone(timezone(timedelta(hours=5)))
        if local.strftime("%Y-%m-%d") != day:
            continue
        f = rec.get("fields") or {}
        turi = select_name(f.get("Turi"))
        action = {"Kirim": "at_kirim", "Chiqim": "at_chiqim"}.get(turi, "at_other")
        events.append(
            {
                "t": local.strftime("%H:%M"),
                "a": action,
                "kategoriya": _first_link(f.get("Kategoriya")),
                "hujjat": bool(f.get("Hujjat")),
                "loyiha": bool(f.get("Loyiha")),
                "gaps": quality_gaps(f),
            }
        )
    return events


def merge_day(tg_events: list[dict], at_events: list[dict]) -> list[dict]:
    return sorted([*tg_events, *at_events], key=lambda e: e.get("t", ""))


TRANSITION_WINDOW_MIN = 60


def _minutes(t: str) -> int:
    hh, mm = (t or "00:00").split(":")[:2]
    return int(hh) * 60 + int(mm)


def _count_transitions(events: list[dict]) -> Counter:
    """Faqat yaqin (≤60 daqiqa) ketma-ket, turli amallar qadam hisoblanadi."""
    out: Counter = Counter()
    for a, b in zip(events, events[1:]):
        close = 0 <= _minutes(b["t"]) - _minutes(a["t"]) <= TRANSITION_WINDOW_MIN
        if a["a"] != b["a"] and close:
            out[f"{a['a']}>{b['a']}"] += 1
    return out


def update_profile(profile: Optional[dict], day: str, events: list[dict]) -> dict:
    """Kunlik hodisalarni umumiy profilga qo'shadi (idempotent: kun bir marta).

    ``days`` to'liq saqlanadi — hisoblagichlar bilan bir xil davrni qamraydi.
    """
    p = dict(profile or {})
    days = list(p.get("days", []))
    if day in days or not events:
        return p
    days.append(day)
    c = {k: Counter(p.get(k, {})) for k in ("hours", "actions", "first_action", "gaps", "mail", "files")}
    at_total = int(p.get("at_total", 0))
    at_hujjat = int(p.get("at_hujjat", 0))

    for e in events:
        if e["a"] in ("gm_in", "gm_out"):
            c["mail"][f"{e['a']}|{e.get('kind', 'boshqa')}|{e.get('domain', '')}"] += 1
        if e["a"] == "xl_edit":
            c["files"][e.get("file", "?")] += 1
        c["hours"][e["t"][:2]] += 1
        c["actions"][e["a"]] += 1
        if e["a"].startswith("at_"):
            at_total += 1
            at_hujjat += 1 if e.get("hujjat") else 0
            for g in e.get("gaps", []):
                c["gaps"][g] += 1
    c["first_action"][events[0]["a"]] += 1
    transitions = Counter(p.get("transitions", {})) + _count_transitions(events)

    p.update({k: dict(v) for k, v in c.items()})
    p.update(
        days=days,
        transitions=dict(transitions),
        at_total=at_total,
        at_hujjat=at_hujjat,
        last_day_timeline=[f"{e['t']} {ACTION_LABELS.get(e['a'], e['a'])}" for e in events][:40],
    )
    return p


def _section_rhythm(profile: dict) -> list[str]:
    lines = ["## 1. Kunlik ritm"]
    hours = Counter(profile.get("hours", {}))
    if hours:
        top = ", ".join(f"{h}:00 ({c})" for h, c in sorted(hours.most_common(3)))
        lines.append(f"- Eng faol soatlar: {top}")
    first = Counter(profile.get("first_action", {}))
    if first:
        a, c = first.most_common(1)[0]
        lines.append(f"- Kunni odatda shundan boshlaydi: **{ACTION_LABELS.get(a, a)}** ({c} kun)")
    if not hours:
        lines.append("- Ma'lumot yo'q")
    return lines


def _section_steps(profile: dict) -> list[str]:
    lines = [f"## 2. Ish ketma-ketligi (qadamlar, {TRANSITION_WINDOW_MIN} daqiqa ichida)"]
    transitions = Counter(profile.get("transitions", {}))
    for i, (pair, c) in enumerate(transitions.most_common(6), 1):
        a, b = pair.split(">")
        lines.append(f"{i}. {ACTION_LABELS.get(a, a)} → {ACTION_LABELS.get(b, b)} — {c} marta")
    if not transitions:
        lines.append("- Ma'lumot yo'q")
    return lines


def _section_quality(profile: dict) -> list[str]:
    lines = ["## 3. Tranzaksiya kiritish standarti"]
    at_total = int(profile.get("at_total", 0))
    if at_total:
        pct = int(profile.get("at_hujjat", 0)) * 100 // at_total
        lines.append(f"- Jami kuzatilgan yozuv: {at_total}; hujjat (chek) biriktirilgani: {pct}%")
    gaps = Counter(profile.get("gaps", {}))
    if gaps:
        lines.append("- Tez-tez uchraydigan kamchiliklar (checklistga qo'shish kerak):")
        lines.extend(f"  - {g} — {c} marta" for g, c in gaps.most_common(5))
    if not at_total:
        lines.append("- Ma'lumot yo'q")
    return lines


def _section_rules(rules: dict[str, dict], nomlar: dict) -> list[str]:
    lines = ["## 4. Kategoriya qoidalari (nom → kategoriya)"]
    strong = sorted(rules.items(), key=lambda kv: -kv[1]["count"])[:15]
    for key, r in strong:
        kat = nomlar.get(r["kategoriya"], r["kategoriya"])
        lines.append(f"- \"{key}\" → {kat} ({r['count']} marta)")
    if not strong:
        lines.append("- Ma'lumot yo'q")
    return lines


def _section_mail_excel(profile: dict) -> list[str]:
    lines = ["## 5. Gmail va Excel"]
    mail = Counter(profile.get("mail", {}))
    for key, c in mail.most_common(8):
        direction, kind, domain = (key.split("|") + ["", ""])[:3]
        verb = "keladi" if direction == "gm_in" else "yuboradi"
        lines.append(f"- Xat {verb}: {kind}" + (f" ({domain})" if domain else "") + f" — {c} marta")
    files = Counter(profile.get("files", {}))
    lines.extend(f"- Jadval tahrirlaydi: {name} — {c} marta" for name, c in files.most_common(5))
    if not mail and not files:
        lines.append("- Ma'lumot yo'q (Gmail/Sheets sozlanmagan yoki faollik yo'q)")
    return lines


def render_skill(profile: dict, rules: dict[str, dict], nomlar: Optional[dict] = None) -> str:
    """Profil → Markdown skill hujjati."""
    days = profile.get("days", [])
    lines = [
        "# Skill: Moliyachi ish tartibi (Jon Branding)",
        "",
        f"_Manba: {len(days)} kunlik kuzatuv (Telegram, Airtable, Gmail, Excel/Sheets). "
        "Hujjat avtomatik shakllanadi; qoidalar faqat kuzatilgan amallardan olingan._",
        "",
    ]
    if len(days) < 3:
        lines += ["> ⚠️ Ma'lumot hali yetarli emas (kamida 3 kun kerak) — xulosalar dastlabki.", ""]
    for section in (
        _section_rhythm(profile),
        _section_steps(profile),
        _section_quality(profile),
        _section_rules(rules, nomlar or {}),
        _section_mail_excel(profile),
    ):
        lines += [*section, ""]
    timeline = profile.get("last_day_timeline") or []
    if timeline:
        lines.append(f"## 6. Oxirgi kuzatilgan kun ({days[-1] if days else ''})")
        lines.extend(f"- {t}" for t in timeline)
    return "\n".join(lines) + "\n"


async def run_skill_update(day_dt: datetime, *, send: bool = False) -> bool:
    """Tugagan kun (``day_dt``) uchun profilni yangilaydi; send=True — skillni yuboradi.

    Sozlangan manba o'qilmasa False qaytadi — kun claim'i bo'shatiladi va
    keyingi daqiqada qayta urinadi (to'liq bo'lmagan kun profilga yozilmaydi).
    """
    from src.db import get_db
    from src.schedulers.moliya.cashflow import KATEGORIYA_JADVALLARI
    from src.schedulers.moliya.helpers import read_name_map, read_table
    from src.schedulers.moliya.moliyachi_sources import gmail_events, sheet_events

    day = day_dt.strftime("%Y-%m-%d")
    db = get_db()
    records = await read_table("Tranzaksiyalar")
    gmail, sheets = await gmail_events(day_dt), await sheet_events(day_dt)
    if not records or gmail is None or sheets is None:
        logger.warning("[MOLIYACHI] Manba o'qilmadi — %s qayta uriniladi", day)
        return False
    tg = await db.get_state(ACTIVITY_PREFIX + day, []) or []
    events = merge_day([*tg, *gmail, *sheets], airtable_events(records, day))
    profile = update_profile(await db.get_state(PROFILE_KEY, {}) or {}, day, events)
    await db.set_state(PROFILE_KEY, profile)
    if not send:
        return True

    nomlar = await read_name_map(*KATEGORIYA_JADVALLARI)
    doc = render_skill(profile, learn_rules(records), nomlar)
    return await _send_doc_to_owner(doc, f"moliyachi_skill_{day}.md")


async def _send_doc_to_owner(doc: str, filename: str) -> bool:
    from src.settings import settings

    owner_id = getattr(settings, "OWNER_ID", None)
    bot_token = os.environ.get("BOT_TOKEN") or getattr(settings, "BOT_TOKEN", None)
    if hasattr(bot_token, "get_secret_value"):
        bot_token = bot_token.get_secret_value()
    if not owner_id or not bot_token:
        logger.warning("[MOLIYACHI] OWNER_ID yoki BOT_TOKEN yo'q — skill yuborilmadi")
        return False
    try:
        from telegram import Bot, InputFile

        await Bot(token=bot_token).send_document(
            chat_id=owner_id,
            document=InputFile(doc.encode("utf-8"), filename=filename),
            caption="🧠 Moliyachi ish tartibi — haftalik yangilangan skill",
        )
        return True
    except Exception:
        logger.error("[MOLIYACHI] Skill yuborishda xato", exc_info=True)
        return False
