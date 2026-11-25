"""Airtable boʻsh maydonlarni Telegram orqali bittama-bitta soʻrab toʻldirish."""

from __future__ import annotations

import asyncio
import html
import logging
import os
from dataclasses import dataclass
from typing import Any, Optional

from src.schedulers.moliya.helpers import read_table_checked, select_name

logger = logging.getLogger(__name__)

SESSION_KEY_PREFIX = "at_gap_session_"
SKIP_KEY_PREFIX = "at_gap_skipped_"
CB_PREFIX = "at_gap:"


@dataclass(frozen=True)
class GapPrompt:
    table: str
    record_id: str
    title: str
    field: str
    question: str
    quick_value: Optional[str] = None
    quick_label: Optional[str] = None


def target_finance_user_id() -> Optional[int]:
    """Moliya boʻshliqlari uchun masʼul: avval MOLIYACHI_TELEGRAM_ID, boʻlmasa OWNER_ID."""
    from src.settings import settings

    for raw in (os.getenv("MOLIYACHI_TELEGRAM_ID", ""), getattr(settings, "OWNER_ID", None)):
        try:
            uid = int(raw or 0)
            if uid > 0:
                return uid
        except (TypeError, ValueError):
            continue
    return None


def target_sales_user_id() -> Optional[int]:
    """Loyiha/sotuv boʻshliqlari uchun masʼul: SALES_MANAGER_IDS[0] yoki OWNER_ID."""
    from src.settings import settings

    managers = list(getattr(settings, "SALES_MANAGER_IDS", None) or [])
    for raw in (*managers, getattr(settings, "OWNER_ID", None)):
        try:
            uid = int(raw or 0)
            if uid > 0:
                return uid
        except (TypeError, ValueError):
            continue
    return None


def is_authorized_filler(user_id: int) -> bool:
    from src.settings import settings

    owner = int(getattr(settings, "OWNER_ID", 0) or 0)
    moliyachi = int(os.getenv("MOLIYACHI_TELEGRAM_ID", "0") or 0)
    managers = {int(x) for x in (getattr(settings, "SALES_MANAGER_IDS", None) or []) if int(x or 0) > 0}
    return user_id > 0 and user_id in ({owner, moliyachi} | managers)


def find_next_gap(
    tx_records: list[dict],
    hisob_records: list[dict],
    today_iso: str,
    skipped: set[str] | None = None,
    ask_fakt_saldo: bool = False,
) -> Optional[GapPrompt]:
    """Navbatdagi 1 ta boʻsh maydonni topadi (Tranzaksiyalar).

    Hisoblar fakt saldosi endi moliya guruhidagi kunlik hisobotdan olinadi
    (``daily_report_ingest``), shuning uchun shaxsiy chatda soʻralmaydi.
    ``ask_fakt_saldo=True`` faqat qoʻlda /toldir uchun eski xulq.
    """
    skip = skipped or set()
    for r in (hisob_records if ask_fakt_saldo else []):
        f = r.get("fields") or {}
        if f.get("Faol") is False:
            continue
        rid = str(r.get("id") or "")
        sana = str(f.get("Fakt saldo sanasi") or "")[:10]
        if rid and f"{rid}:Fakt saldo" not in skip and (not sana or sana < today_iso):
            nom = str(f.get("Hisob nomi") or "Hisob")
            val = select_name(f.get("Valyuta")) or "UZS"
            return GapPrompt(
                table="Hisoblar",
                record_id=rid,
                title=nom,
                field="Fakt saldo",
                question=(
                    f"🏦 <b>Hisoblar — {html.escape(nom)}</b>\n"
                    f"Oxirgi fakt saldo sanasi: <code>{sana or 'yoʻq'}</code>\n"
                    f"Joriy fakt saldoni ({val}) raqamda yozing (masalan: <code>1500000</code>):"
                ),
            )

    sorted_tx = sorted(
        tx_records,
        key=lambda x: str((x.get("fields") or {}).get("Sana") or ""),
        reverse=True,
    )
    for r in sorted_tx:
        f = r.get("fields") or {}
        if select_name(f.get("Holat")) == "Bekor qilingan":
            continue
        rid = str(r.get("id") or "")
        title = str(f.get("Tranzaksiya") or "Nomsiz tranzaksiya")
        sana = str(f.get("Sana") or "")[:10]
        if not f.get("Hisobot oyi") and f"{rid}:Hisobot oyi" not in skip:
            oy = sana[:7] if len(sana) >= 7 else today_iso[:7]
            return GapPrompt(
                table="Tranzaksiyalar",
                record_id=rid,
                title=title,
                field="Hisobot oyi",
                question=(
                    f"🧾 <b>Tranzaksiya — {html.escape(title)}</b> ({sana or 'sanasiz'})\n"
                    f"<b>Hisobot oyi</b> boʻsh. Qaysi oyga tegishli? (<code>YYYY-MM</code>):"
                ),
                quick_value=oy,
                quick_label=f"📅 {oy} (tavsiya)",
            )
        if not f.get("Loyiha") and select_name(f.get("Turi")) == "Kirim" and f"{rid}:Loyiha" not in skip:
            return GapPrompt(
                table="Tranzaksiyalar",
                record_id=rid,
                title=title,
                field="Loyiha",
                question=(
                    f"🧾 <b>Tranzaksiya (Kirim) — {html.escape(title)}</b> ({sana})\n"
                    "<b>Loyiha</b> biriktirilmagan. Loyiha nomini yozing:"
                ),
            )
    return None


def build_prompt_markup(prompt: GapPrompt) -> dict:
    rows: list[list[dict[str, str]]] = []
    if prompt.quick_value and prompt.quick_label:
        rows.append([{
            "text": prompt.quick_label,
            "callback_data": f"{CB_PREFIX}quick:{prompt.quick_value}",
        }])
    rows.append([
        {"text": "⏭️ Oʻtkazib yuborish", "callback_data": f"{CB_PREFIX}skip"},
        {"text": "🛑 Toʻxtatish", "callback_data": f"{CB_PREFIX}stop"},
    ])
    return {"inline_keyboard": rows}


async def _resolve_project_id(name: str) -> Optional[str]:
    records, ok = await read_table_checked("Loyihalar")
    if not ok:
        return None
    needle = name.strip().lower()
    for r in records:
        f = r.get("fields") or {}
        title = str(f.get("Loyiha nomi") or f.get("Nomi") or f.get("Mijoz nomi") or "").strip()
        if title and needle in title.lower():
            return str(r.get("id"))
    return None


async def apply_answer(
    prompt: dict[str, Any], answer_text: str, *, actor_label: str, today_iso: str
) -> tuple[bool, str]:
    """Foydalanuvchi javobini tekshirib Airtable ga yozadi."""
    from src.services.core.airtable_sync import AirtableSync

    table = str(prompt["table"])
    rid = str(prompt["record_id"])
    field = str(prompt["field"])
    val = answer_text.strip()
    fields: dict[str, Any]

    if table == "Hisoblar" and field == "Fakt saldo":
        cleaned = val.replace(" ", "").replace(",", ".")
        try:
            amount = float(cleaned)
        except ValueError:
            return False, "Raqam kiriting (masalan: <code>1500000</code>)."
        fields = {
            "Fakt saldo (hisob valyutasida)": amount,
            "Fakt saldo sanasi": today_iso,
            "Fakt saldo manbasi": f"Telegram /toldir ({actor_label})",
        }
    elif table == "Tranzaksiyalar" and field == "Hisobot oyi":
        if len(val) != 7 or val[4] != "-" or not (val[:4] + val[5:]).isdigit():
            return False, "Oy formati <code>YYYY-MM</code> boʻlsin (masalan: <code>2026-11</code>)."
        fields = {"Hisobot oyi": val}
    elif table == "Tranzaksiyalar" and field == "Loyiha":
        proj_id = await _resolve_project_id(val)
        if not proj_id:
            return False, f"«{html.escape(val)}» nomli loyiha topilmadi. Aniqroq yozing yoki oʻtkazib yuboring."
        fields = {"Loyiha": [proj_id]}
    else:
        return False, "Nomaʼlum maydon."

    def _patch() -> bool:
        return bool(AirtableSync(table_name=table).update_project_fields(rid, fields))

    ok = await asyncio.to_thread(_patch)
    if not ok:
        return False, "Airtable ga yozishda xatolik yuz berdi."
    return True, f"✅ <b>{html.escape(str(prompt['title']))}</b> — <code>{html.escape(field)}</code> saqlandi."


async def next_gap_for_user(db: Any, user_id: int, today_iso: str) -> Optional[GapPrompt]:
    tx_records, tx_ok = await read_table_checked("Tranzaksiyalar")
    hisob_records, hisob_ok = await read_table_checked("Hisoblar")
    if not tx_ok and not hisob_ok:
        return None
    skipped = set(await db.get_state(f"{SKIP_KEY_PREFIX}{user_id}_{today_iso}", []) or [])
    return find_next_gap(tx_records if tx_ok else [], hisob_records if hisob_ok else [], today_iso, skipped)


async def run_daily_gap_prompt() -> bool:
    """Har kuni 10:00 da masʼulga navbatdagi 1 ta boʻsh maydonni yuboradi."""
    from src.db import get_db
    from src.settings import settings
    from src.time_utils import get_local_now

    uid = target_finance_user_id()
    bot_token = os.environ.get("BOT_TOKEN") or getattr(settings, "BOT_TOKEN", None)
    if hasattr(bot_token, "get_secret_value"):
        bot_token = bot_token.get_secret_value()
    if not uid or not bot_token:
        return False
    db = get_db()
    today_iso = get_local_now().strftime("%Y-%m-%d")
    prompt = await next_gap_for_user(db, uid, today_iso)
    if prompt is None:
        return True
    await db.set_state(f"{SESSION_KEY_PREFIX}{uid}", prompt.__dict__)
    try:
        from telegram import Bot

        await Bot(token=bot_token).send_message(
            chat_id=uid,
            text=prompt.question,
            parse_mode="HTML",
            reply_markup=build_prompt_markup(prompt),
        )
        return True
    except Exception:
        logger.error("[AIRTABLE-GAP] Kunlik soʻrov yuborilmadi", exc_info=True)
        return False
