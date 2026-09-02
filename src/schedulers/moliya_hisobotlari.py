"""Airtable (Finance V2) → Telegram moliya hisobotlari.

Uchta rejali hisobot:

* **Qarzdorlik** — har dushanba 09:00, to'lovi tugallanmagan loyihalar
* **Cashflow**   — har kuni 19:00, shu oyning kirim/chiqim/sof oqimi
* **Balans**     — har kuni 09:00, hisoblardagi joriy qoldiq

Har biri o'z topikiga tushadi. Topic ID'lar ``settings.py`` da allaqachon
e'lon qilingan (``HISOBCHI_QARZDORLIK_TOPIC_ID``, ``HISOBCHI_CASHFLOW_TOPIC_ID``,
``HISOBCHI_BALANCE_TOPIC_ID``) va deploy ``.env`` ga yoziladi.

Manba — Airtable ``Tranzaksiyalar``, ``Loyihalar``, ``Hisoblar`` jadvallari.
Eski Kirim/Chiqim jadvallari ishlatilmaydi.
"""

from __future__ import annotations

import asyncio
import logging
import os
from datetime import datetime
from typing import Any

logger = logging.getLogger(__name__)

# Qancha qator ko'rsatiladi — xabar 4096 belgidan oshmasligi uchun
MAX_ROWS = 20


# --------------------------------------------------------------------------- #
# Yordamchilar
# --------------------------------------------------------------------------- #

def _fmt(n: Any) -> str:
    """1234567.8 -> '1 234 568'"""
    try:
        return f"{round(float(n or 0)):,}".replace(",", " ")
    except (TypeError, ValueError):
        return "0"


def _esc(s: Any) -> str:
    """Telegram HTML uchun xavfsiz matn."""
    if s is None:
        return "—"
    return (
        str(s)
        .replace("&", "&amp;")
        .replace("<", "&lt;")
        .replace(">", "&gt;")
    )


def _select_name(value: Any) -> str:
    """singleSelect maydoni obyekt yoki matn bo'lishi mumkin."""
    if isinstance(value, dict):
        return (value.get("name") or "").strip()
    return (value or "").strip() if isinstance(value, str) else ""


def _link_names(value: Any) -> str:
    """Linked-record maydonidan nomlarni chiqarish."""
    if not value:
        return ""
    if isinstance(value, list):
        out = []
        for item in value:
            if isinstance(item, dict):
                out.append(item.get("name") or item.get("id") or "")
            else:
                out.append(str(item))
        return ", ".join(x for x in out if x)
    return str(value)


async def _read_table(table_name: str) -> list[dict]:
    """AirtableSync sinxron — thread'da chaqiramiz, event loop bloklanmasin."""
    from src.services.core.airtable_sync import AirtableSync

    def _work() -> list[dict]:
        client = AirtableSync(table_name=table_name)
        return client.get_projects()

    try:
        return await asyncio.to_thread(_work)
    except Exception:
        logger.error("[MOLIYA] '%s' jadvalini o'qishda xato", table_name, exc_info=True)
        return []


async def _send(text: str, topic_attr: str) -> bool:
    """Moliya guruhining kerakli topikiga yuborish.

    ``topic_attr`` — ``settings`` dagi topic o'zgaruvchisi nomi.
    Topic topilmasa guruhning umumiy oqimiga tushadi.
    """
    from src.settings import settings
    from src.services.core.tool_adapters import send_group_message_with_fallback

    group_id = getattr(settings, "HISOBCHI_FINANCE_GROUP_ID", None)
    if not group_id:
        logger.warning("[MOLIYA] HISOBCHI_FINANCE_GROUP_ID sozlanmagan — yuborilmadi")
        return False

    thread_id = getattr(settings, topic_attr, None)

    bot_token = os.environ.get("BOT_TOKEN") or getattr(settings, "BOT_TOKEN", None)
    if hasattr(bot_token, "get_secret_value"):
        bot_token = bot_token.get_secret_value()
    if not bot_token:
        logger.warning("[MOLIYA] BOT_TOKEN topilmadi — yuborilmadi")
        return False

    try:
        from telegram import Bot

        bot = Bot(token=bot_token)
        await send_group_message_with_fallback(
            bot,
            chat_id=group_id,
            text=text[:4000],
            parse_mode="HTML",
            thread_id=thread_id,
            allow_userbot_fallback=False,
        )
        return True
    except Exception:
        logger.error("[MOLIYA] Telegramga yuborishda xato", exc_info=True)
        return False


async def _once_per_day(job_key: str, day: str) -> bool:
    """Kuniga bir marta ishlashini kafolatlash (restart'dan keyin ham)."""
    try:
        from src import db

        if await db.is_job_run(job_key, day):
            return False
        await db.mark_job_run(job_key, day)
        return True
    except Exception:
        # DB ishlamasa ham hisobot yuborilsin — takror kelishi mumkin, lekin
        # butunlay yo'qolganidan ko'ra yaxshi.
        logger.warning("[MOLIYA] job dedup ishlamadi (%s)", job_key, exc_info=True)
        return True


# --------------------------------------------------------------------------- #
# 1. Qarzdorlik
# --------------------------------------------------------------------------- #

async def build_qarzdorlik_report() -> str:
    records = await _read_table("Loyihalar")

    rows = []
    for r in records:
        f = r.get("fields", {}) or {}
        qoldiq = f.get("Qoldiq to‘lov uzs") or f.get("Qoldiq to'lov uzs") or 0
        try:
            qoldiq = float(qoldiq)
        except (TypeError, ValueError):
            qoldiq = 0
        if qoldiq <= 0:
            continue
        rows.append({
            "nom": f.get("Loyihani nomi?") or "Nomsiz",
            "mijoz": _link_names(f.get("Mijoz nomi")),
            "narx": f.get("Jami loyiha narxi (UZS)") or 0,
            "tolangan": f.get("Jami to'langan (UZS)") or f.get("Jami to‘langan (UZS)") or 0,
            "qoldiq": qoldiq,
        })

    rows.sort(key=lambda x: x["qoldiq"], reverse=True)

    if not rows:
        return "💰 <b>Qarzdorlik</b>\n\nQarzdorlik yo‘q — barcha loyihalar to‘liq to‘langan ✅"

    jami = sum(x["qoldiq"] for x in rows)

    lines = [f"💰 <b>Qarzdorlik</b> — {len(rows)} ta loyiha\n"]
    for i, x in enumerate(rows[:MAX_ROWS], 1):
        lines.append(f"{i}. <b>{_esc(x['nom'])}</b>")
        if x["mijoz"]:
            lines.append(f"    {_esc(x['mijoz'])}")
        lines.append(
            f"    {_fmt(x['tolangan'])} / {_fmt(x['narx'])} — "
            f"qoldiq <b>{_fmt(x['qoldiq'])}</b> so‘m"
        )

    if len(rows) > MAX_ROWS:
        qolgan = len(rows) - MAX_ROWS
        lines.append(f"\n<i>… yana {qolgan} ta loyiha</i>")

    lines.append(f"\n<b>Jami qarzdorlik: {_fmt(jami)} so‘m</b>")
    return "\n".join(lines)


async def run_qarzdorlik_report() -> bool:
    text = await build_qarzdorlik_report()
    ok = await _send(text, "HISOBCHI_QARZDORLIK_TOPIC_ID")
    if ok:
        logger.info("[MOLIYA] Qarzdorlik hisoboti yuborildi")
    return ok


# --------------------------------------------------------------------------- #
# 2. Cashflow
# --------------------------------------------------------------------------- #

async def build_cashflow_report(now: datetime) -> str:
    records = await _read_table("Tranzaksiyalar")
    oy = now.strftime("%Y-%m")

    kirim = chiqim = 0.0
    kirim_soni = chiqim_soni = 0
    kategoriyalar: dict[str, float] = {}

    for r in records:
        f = r.get("fields", {}) or {}

        if _select_name(f.get("Holat")) == "Bekor qilingan":
            continue

        sana = f.get("Sana") or ""
        if not str(sana).startswith(oy):
            continue

        turi = _select_name(f.get("Turi"))
        try:
            summa = float(f.get("Summa UZS") or 0)
        except (TypeError, ValueError):
            summa = 0.0

        if turi == "Kirim":
            kirim += summa
            kirim_soni += 1
        elif turi == "Chiqim":
            chiqim += summa
            chiqim_soni += 1
            kat = _link_names(f.get("Kategoriya")) or "Kategoriyasiz"
            kategoriyalar[kat] = kategoriyalar.get(kat, 0.0) + summa

    sof = kirim - chiqim
    belgi = "🟢" if sof >= 0 else "🔴"

    lines = [
        f"📊 <b>Cashflow — {oy}</b>\n",
        f"Kirim:  <b>{_fmt(kirim)}</b> so‘m  ({kirim_soni} ta)",
        f"Chiqim: <b>{_fmt(chiqim)}</b> so‘m  ({chiqim_soni} ta)",
        f"{belgi} Sof oqim: <b>{_fmt(sof)}</b> so‘m",
    ]

    if kategoriyalar:
        top = sorted(kategoriyalar.items(), key=lambda kv: kv[1], reverse=True)[:7]
        lines.append("\n<b>Eng katta xarajatlar:</b>")
        for kat, summa in top:
            ulush = (summa / chiqim * 100) if chiqim else 0
            lines.append(f"• {_esc(kat)} — {_fmt(summa)} ({ulush:.0f}%)")

    if not kirim_soni and not chiqim_soni:
        lines.append("\n<i>Bu oyda hali tranzaksiya yo‘q.</i>")

    return "\n".join(lines)


async def run_cashflow_report(now: datetime) -> bool:
    text = await build_cashflow_report(now)
    ok = await _send(text, "HISOBCHI_CASHFLOW_TOPIC_ID")
    if ok:
        logger.info("[MOLIYA] Cashflow hisoboti yuborildi")
    return ok


# --------------------------------------------------------------------------- #
# 3. Balans
# --------------------------------------------------------------------------- #

async def build_balans_report() -> str:
    records = await _read_table("Hisoblar")

    rows = []
    for r in records:
        f = r.get("fields", {}) or {}
        if f.get("Faol") is False:
            continue
        try:
            balans = float(f.get("Joriy balans (UZS)") or 0)
        except (TypeError, ValueError):
            balans = 0.0
        rows.append({
            "nom": f.get("Hisob nomi") or "Nomsiz",
            "turi": _select_name(f.get("Turi")),
            "balans": balans,
        })

    if not rows:
        return "🏦 <b>Hisob qoldiqlari</b>\n\n<i>Hisoblar topilmadi.</i>"

    rows.sort(key=lambda x: x["balans"], reverse=True)
    jami = sum(x["balans"] for x in rows)

    emoji = {"Kassa": "💵", "Bank": "🏦", "Karta": "💳"}

    lines = ["🏦 <b>Hisob qoldiqlari</b>\n"]
    for x in rows:
        ico = emoji.get(x["turi"], "•")
        lines.append(f"{ico} {_esc(x['nom'])} — <b>{_fmt(x['balans'])}</b> so‘m")

    lines.append(f"\n<b>Jami: {_fmt(jami)} so‘m</b>")

    if jami < 0:
        lines.append("\n⚠️ Umumiy qoldiq manfiy — tekshiring.")

    return "\n".join(lines)


async def run_balans_report() -> bool:
    text = await build_balans_report()
    ok = await _send(text, "HISOBCHI_BALANCE_TOPIC_ID")
    if ok:
        logger.info("[MOLIYA] Balans hisoboti yuborildi")
    return ok


# --------------------------------------------------------------------------- #
# Rejalashtiruvchi
# --------------------------------------------------------------------------- #

async def moliya_hisobotlari_loop() -> None:
    """Uchala hisobotni o'z vaqtida yuboradi.

    ``boot.py`` da bir marta ``asyncio.create_task(...)`` bilan ishga tushiriladi.
    Har 60 soniyada tekshiradi; oyna 5 daqiqa — sikl siljisa ham o'tkazib
    yubormaydi. Kunlik takrorlanish DB orqali to'siladi.
    """
    from src.time_utils import get_local_now

    await asyncio.sleep(120)  # bot to'liq ko'tarilishini kutamiz

    logger.info("[MOLIYA] Hisobot sikli boshlandi")

    while True:
        try:
            now = get_local_now()
            day = now.strftime("%Y-%m-%d")

            # Qarzdorlik — dushanba 09:00
            if now.weekday() == 0 and now.hour == 9 and now.minute < 5:
                if await _once_per_day("moliya_qarzdorlik", day):
                    await run_qarzdorlik_report()

            # Balans — har kuni 09:00
            if now.hour == 9 and now.minute < 5:
                if await _once_per_day("moliya_balans", day):
                    await run_balans_report()

            # Cashflow — har kuni 19:00
            if now.hour == 19 and now.minute < 5:
                if await _once_per_day("moliya_cashflow", day):
                    await run_cashflow_report(now)

        except Exception:
            logger.error("[MOLIYA] Sikl xatosi", exc_info=True)

        await asyncio.sleep(60)
