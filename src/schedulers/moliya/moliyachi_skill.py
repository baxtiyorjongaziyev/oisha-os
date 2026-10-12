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
}


def moliyachi_telegram_id() -> int:
    try:
        return int(os.getenv("MOLIYACHI_TELEGRAM_ID", "0") or 0)
    except ValueError:
        return 0


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


async def observe_finance_message(event: Any, *, kirim_topic_id: Any, chiqim_topic_id: Any) -> None:
    """Moliya guruhidagi xabarni moliyachi harakati sifatida qayd etadi."""
    expected = moliyachi_telegram_id()
    if expected and int(getattr(event, "sender_id", 0) or 0) != expected:
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


def update_profile(profile: Optional[dict], day: str, events: list[dict]) -> dict:
    """Kunlik hodisalarni umumiy profilga qo'shadi (idempotent: kun bir marta)."""
    p = dict(profile or {})
    days = list(p.get("days", []))
    if day in days or not events:
        return p
    days.append(day)
    hours = Counter(p.get("hours", {}))
    actions = Counter(p.get("actions", {}))
    transitions = Counter(p.get("transitions", {}))
    first = Counter(p.get("first_action", {}))
    gaps = Counter(p.get("gaps", {}))
    at_total = int(p.get("at_total", 0))
    at_hujjat = int(p.get("at_hujjat", 0))

    for e in events:
        hours[e["t"][:2]] += 1
        actions[e["a"]] += 1
        if e["a"].startswith("at_"):
            at_total += 1
            at_hujjat += 1 if e.get("hujjat") else 0
            for g in e.get("gaps", []):
                gaps[g] += 1
    for a, b in zip(events, events[1:]):
        if a["a"] != b["a"]:
            transitions[f"{a['a']}>{b['a']}"] += 1
    first[events[0]["a"]] += 1

    p.update(
        days=days[-90:],
        hours=dict(hours),
        actions=dict(actions),
        transitions=dict(transitions),
        first_action=dict(first),
        gaps=dict(gaps),
        at_total=at_total,
        at_hujjat=at_hujjat,
        last_day_timeline=[f"{e['t']} {ACTION_LABELS.get(e['a'], e['a'])}" for e in events][:40],
    )
    return p


def render_skill(profile: dict, rules: dict[str, dict], nomlar: Optional[dict] = None) -> str:
    """Profil → Markdown skill hujjati."""
    nomlar = nomlar or {}
    days = profile.get("days", [])
    lines = [
        "# Skill: Moliyachi ish tartibi (Jon Branding)",
        "",
        f"_Manba: {len(days)} kunlik kuzatuv (Telegram moliya guruhi + Airtable Tranzaksiyalar). "
        "Hujjat avtomatik shakllanadi; qoidalar faqat kuzatilgan amallardan olingan._",
        "",
    ]
    if len(days) < 3:
        lines.append("> ⚠️ Ma'lumot hali yetarli emas (kamida 3 kun kerak) — xulosalar dastlabki.")
        lines.append("")

    hours = Counter(profile.get("hours", {}))
    lines.append("## 1. Kunlik ritm")
    if hours:
        top = ", ".join(f"{h}:00 ({c})" for h, c in sorted(hours.most_common(3)))
        lines.append(f"- Eng faol soatlar: {top}")
    first = Counter(profile.get("first_action", {}))
    if first:
        a, c = first.most_common(1)[0]
        lines.append(f"- Kunni odatda shundan boshlaydi: **{ACTION_LABELS.get(a, a)}** ({c} kun)")
    if not hours:
        lines.append("- Ma'lumot yo'q")
    lines.append("")

    lines.append("## 2. Ish ketma-ketligi (qadamlar)")
    transitions = Counter(profile.get("transitions", {}))
    if transitions:
        for i, (pair, c) in enumerate(transitions.most_common(6), 1):
            a, b = pair.split(">")
            lines.append(
                f"{i}. {ACTION_LABELS.get(a, a)} → {ACTION_LABELS.get(b, b)} — {c} marta"
            )
    else:
        lines.append("- Ma'lumot yo'q")
    lines.append("")

    lines.append("## 3. Tranzaksiya kiritish standarti")
    at_total = int(profile.get("at_total", 0))
    if at_total:
        pct = int(profile.get("at_hujjat", 0)) * 100 // at_total
        lines.append(f"- Jami kuzatilgan yozuv: {at_total}; hujjat (chek) biriktirilgani: {pct}%")
    gaps = Counter(profile.get("gaps", {}))
    if gaps:
        lines.append("- Tez-tez uchraydigan kamchiliklar (checklistga qo'shish kerak):")
        for g, c in gaps.most_common(5):
            lines.append(f"  - {g} — {c} marta")
    if not at_total:
        lines.append("- Ma'lumot yo'q")
    lines.append("")

    lines.append("## 4. Kategoriya qoidalari (nom → kategoriya)")
    strong = sorted(rules.items(), key=lambda kv: -kv[1]["count"])[:15]
    if strong:
        for key, r in strong:
            kat = nomlar.get(r["kategoriya"], r["kategoriya"])
            lines.append(f"- \"{key}\" → {kat} ({r['count']} marta)")
    else:
        lines.append("- Ma'lumot yo'q")
    lines.append("")

    timeline = profile.get("last_day_timeline") or []
    if timeline:
        lines.append(f"## 5. Oxirgi kuzatilgan kun ({days[-1] if days else ''})")
        lines.extend(f"- {t}" for t in timeline)
    return "\n".join(lines) + "\n"


async def run_skill_update(now: datetime, *, send: bool = False) -> bool:
    """Kunlik: profilni yangilaydi. send=True bo'lsa skillni egasiga yuboradi."""
    from src.db import get_db
    from src.schedulers.moliya.cashflow import KATEGORIYA_JADVALLARI
    from src.schedulers.moliya.helpers import read_name_map, read_table

    day = now.strftime("%Y-%m-%d")
    db = get_db()
    records = await read_table("Tranzaksiyalar")
    tg = await db.get_state(ACTIVITY_PREFIX + day, []) or []
    events = merge_day(tg, airtable_events(records, day))
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
