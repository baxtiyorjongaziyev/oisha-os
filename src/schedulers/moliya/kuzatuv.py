"""Hisobchi kuzatuv rejimi — moliyachi ishini kuzatadi va o'rganadi.

Moliyachi kirim/chiqimni "Jamoa — Kirim va chiqim yuborish" Airtable formasi
orqali kiritadi. Hisobchi hech narsa yozmaydi va guruhga javob bermaydi:

* ``Tranzaksiyalar`` dan qoidalar o'rganadi (nom -> kategoriya/hisob);
* bugungi yozuvlar uchun o'zi nima taxmin qilgan bo'lardi — moliyachi bilan
  solishtirib, moslik foizini o'lchaydi (o'rganish sifati);
* yozuv sifatini tekshiradi (hujjat, kategoriya, loyiha, hisobot oyi, kurs);
* moliya guruhidagi xabarlar sonini (``record_observation``) yozib boradi.

Hisobot faqat egasiga (OWNER_ID) shaxsiy xabar sifatida, har kuni 21:00.
Ma'lumot bo'lmasa raqam to'qilmaydi — "ma'lumot yo'q" deyiladi.
"""

from __future__ import annotations

import logging
import os
import re
from collections import Counter, defaultdict
from datetime import datetime
from typing import Any, Optional

from src.schedulers.moliya.cashflow import KATEGORIYA_JADVALLARI, kategoriya_nomi
from src.schedulers.moliya.helpers import esc, fmt, read_name_map, read_table, select_name

logger = logging.getLogger(__name__)

RULES_STATE_KEY = "hisobchi_kuzatuv_rules"
OBSERVATION_STATE_PREFIX = "hisobchi_kuzatuv_obs_"


def rule_key(name: Any) -> str:
    """Tranzaksiya nomidan barqaror kalit: kichik harf, raqam/belgisiz, 3 so'z."""
    words = re.findall(r"[^\W\d_]+", str(name or "").lower())
    return " ".join(words[:3])


def _first_link(value: Any) -> str:
    if isinstance(value, list) and value:
        item = value[0]
        return (item.get("id") or item.get("name") or "") if isinstance(item, dict) else str(item)
    return str(value or "")


def _sana(rec: dict) -> str:
    return str((rec.get("fields") or {}).get("Sana") or "")[:10]


def learn_rules(records: list[dict]) -> dict[str, dict]:
    """Har bir nom-kalit uchun eng ko'p tanlangan kategoriya va hisob."""
    kats: dict[str, Counter] = defaultdict(Counter)
    hisoblar: dict[str, Counter] = defaultdict(Counter)
    for rec in records:
        f = rec.get("fields") or {}
        if select_name(f.get("Holat")) == "Bekor qilingan":
            continue
        key = rule_key(f.get("Tranzaksiya"))
        kat = _first_link(f.get("Kategoriya"))
        if not key or not kat:
            continue
        kats[key][kat] += 1
        hisob = _first_link(f.get("Hisob"))
        if hisob:
            hisoblar[key][hisob] += 1
    return {
        key: {
            "kategoriya": counter.most_common(1)[0][0],
            "hisob": (hisoblar[key].most_common(1)[0][0] if hisoblar[key] else ""),
            "count": sum(counter.values()),
        }
        for key, counter in kats.items()
    }


def quality_gaps(f: dict) -> list[str]:
    """Moliyachi yozuvidagi kamchiliklar (checklist bo'yicha)."""
    gaps = []
    if not f.get("Hujjat"):
        gaps.append("hujjat yo'q")
    if not f.get("Kategoriya"):
        gaps.append("kategoriya yo'q")
    if select_name(f.get("Turi")) == "Kirim" and not f.get("Loyiha"):
        gaps.append("kirimda loyiha yo'q")
    sana = str(f.get("Sana") or "")[:7]
    oy = f.get("Hisobot oyi")
    oy_text = select_name(oy) or link_names_text(oy)
    if sana and oy_text and not oy_text.startswith(sana):
        gaps.append("hisobot oyi sanaga mos emas")
    if select_name(f.get("Valyuta")) == "USD" and not f.get("Kurs"):
        gaps.append("USD kursi yo'q")
    return gaps


def link_names_text(value: Any) -> str:
    if isinstance(value, list):
        return ", ".join(str(v.get("name") if isinstance(v, dict) else v) for v in value)
    return str(value or "")


async def build_kuzatuv_report(
    now: datetime,
    *,
    records: Optional[list[dict]] = None,
    nomlar: Optional[dict[str, str]] = None,
    observation: Optional[dict] = None,
) -> str:
    if records is None:
        records = await read_table("Tranzaksiyalar")
    if nomlar is None:
        nomlar = await read_name_map(*KATEGORIYA_JADVALLARI)
    if observation is None:
        observation = await load_observation(now.strftime("%Y-%m-%d"))

    day = now.strftime("%Y-%m-%d")
    today = [r for r in records if _sana(r) == day]
    history = [r for r in records if _sana(r) and _sana(r) < day]
    rules = learn_rules(history)

    kirim = sum(float((r["fields"].get("Summa UZS") or 0)) for r in today
                if select_name(r["fields"].get("Turi")) == "Kirim")
    chiqim = sum(float((r["fields"].get("Summa UZS") or 0)) for r in today
                 if select_name(r["fields"].get("Turi")) == "Chiqim")

    checked = right = 0
    wrong: list[str] = []
    gap_lines: list[str] = []
    for r in today:
        f = r["fields"]
        rule = rules.get(rule_key(f.get("Tranzaksiya")))
        actual = _first_link(f.get("Kategoriya"))
        if rule and actual:
            checked += 1
            if rule["kategoriya"] == actual:
                right += 1
            elif len(wrong) < 5:
                wrong.append(
                    f"• {esc(f.get('Tranzaksiya'))}: men "
                    f"{esc(kategoriya_nomi(rule['kategoriya'], nomlar))} derdim, moliyachi "
                    f"{esc(kategoriya_nomi(actual, nomlar))} tanladi"
                )
        gaps = quality_gaps(f)
        if gaps and len(gap_lines) < 8:
            gap_lines.append(f"• {esc(f.get('Tranzaksiya') or 'Nomsiz')}: {', '.join(gaps)}")

    lines = [
        f"🧾 <b>Hisobchi kuzatuvi — {day}</b>",
        "<i>Rejim: faqat kuzatish va o'rganish, hech narsa yozilmadi.</i>\n",
        f"Bugun Airtable: <b>{len(today)}</b> ta yozuv "
        f"(kirim {fmt(kirim)}, chiqim {fmt(chiqim)} so'm)",
        f"Guruhda: <b>{int(observation.get('messages', 0))}</b> ta xabar"
        f" ({int(observation.get('photos', 0))} ta rasm/chek)",
        f"O'rganilgan qoidalar: <b>{len(rules)}</b> ta",
    ]
    if checked:
        lines.append(f"Taxmin mosligi: <b>{right}/{checked}</b> ({right * 100 // checked}%)")
    else:
        lines.append("Taxmin mosligi: ma'lumot yo'q")
    if wrong:
        lines.append("\n<b>Farqlar (o'rganyapman):</b>")
        lines.extend(wrong)
    if gap_lines:
        lines.append("\n<b>Yozuv kamchiliklari:</b>")
        lines.extend(gap_lines)
    return "\n".join(lines)


async def record_observation(*, has_photo: bool) -> None:
    """Moliya guruhidagi xabarni sanash — matn saqlanmaydi, faqat son."""
    try:
        from src.db import get_db
        from src.time_utils import get_local_now

        key = OBSERVATION_STATE_PREFIX + get_local_now().strftime("%Y-%m-%d")
        db = get_db()
        obs = await db.get_state(key, {}) or {}
        obs["messages"] = int(obs.get("messages", 0)) + 1
        obs["photos"] = int(obs.get("photos", 0)) + (1 if has_photo else 0)
        await db.set_state(key, obs)
    except Exception:
        logger.warning("[HISOBCHI] Kuzatuv yozilmadi", exc_info=True)


async def load_observation(day: str) -> dict:
    try:
        from src.db import get_db

        return await get_db().get_state(OBSERVATION_STATE_PREFIX + day, {}) or {}
    except Exception:
        logger.warning("[HISOBCHI] Kuzatuv o'qilmadi", exc_info=True)
        return {}


async def run_kuzatuv_report(now: datetime) -> bool:
    from src.settings import settings

    owner_id = getattr(settings, "OWNER_ID", None)
    bot_token = os.environ.get("BOT_TOKEN") or getattr(settings, "BOT_TOKEN", None)
    if hasattr(bot_token, "get_secret_value"):
        bot_token = bot_token.get_secret_value()
    if not owner_id or not bot_token:
        logger.warning("[HISOBCHI] OWNER_ID yoki BOT_TOKEN yo'q — kuzatuv yuborilmadi")
        return False
    text = await build_kuzatuv_report(now)
    try:
        from telegram import Bot

        await Bot(token=bot_token).send_message(
            chat_id=owner_id, text=text[:4000], parse_mode="HTML"
        )
        logger.info("[HISOBCHI] Kuzatuv hisoboti yuborildi")
        return True
    except Exception:
        logger.error("[HISOBCHI] Kuzatuv hisobotini yuborishda xato", exc_info=True)
        return False
