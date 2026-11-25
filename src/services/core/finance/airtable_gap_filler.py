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
    """/toldir faqat egasi uchun: moliyachiga DM yuborilmaydi (guruh-yordamchi rejimi)."""
    from src.settings import settings

    owner = int(getattr(settings, "OWNER_ID", 0) or 0)
    return owner > 0 and user_id == owner


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


# ---------------------------------------------------------------------------
# Guruh-yordamchi rejimi: Oisha hech narsa yozmaydi, faqat guruhda eslatadi.
# ---------------------------------------------------------------------------

DEFAULT_BASE_ID = "app8xoyx1XCumYFXV"
TX_TABLE_ID = "tblrqxqIzyrvg7XpQ"
ERROR_LOOKBACK_DAYS = 3
ALERT_JOB_PREFIX = "at_group_alert:"
TRANSFER_HINTS = (
    "kartaga tushir",
    "konvert",
    "naqdga",
    "naqd pulga",
    "yechib ol",
    "hisobga oʻtkaz",
)


@dataclass(frozen=True)
class DigestItem:
    record_id: str
    title: str
    sana: str
    detail: str
    kind: str  # "gap" | "error"


def record_link(record_id: str) -> str:
    from src.settings import settings

    base = str(getattr(settings, "AIRTABLE_BASE_ID", None) or DEFAULT_BASE_ID)
    return f"https://airtable.com/{base}/{TX_TABLE_ID}/{record_id}"


def collect_gaps(tx_records: list[dict]) -> list[DigestItem]:
    """Tranzaksiyalardagi toʻldirilishi kerak kataklar (Hisoblar/Fakt saldo kirmaydi)."""
    out: list[DigestItem] = []
    for r in tx_records:
        f = r.get("fields") or {}
        if select_name(f.get("Holat")) == "Bekor qilingan":
            continue
        rid = str(r.get("id") or "")
        if not rid:
            continue
        title = str(f.get("Tranzaksiya") or "Nomsiz tranzaksiya")
        sana = str(f.get("Sana") or "")[:10]
        if not f.get("Hisobot oyi"):
            out.append(DigestItem(rid, title, sana, "Hisobot oyi", "gap"))
        if not f.get("Loyiha") and select_name(f.get("Turi")) == "Kirim":
            out.append(DigestItem(rid, title, sana, "Loyiha", "gap"))
    return out


def _has_any(f: dict, prefix: str) -> bool:
    return any(k.startswith(prefix) and f.get(k) not in (None, "", [], 0) for k in f)


def fail_reasons(f: dict) -> list[str]:
    """Nazorat holati formulasidagi FAIL qoidalaridan sababni chiqaradi."""
    reasons: list[str] = []
    turi = select_name(f.get("Turi"))
    missing = [k for k in ("Sana", "Turi", "Summa", "Hisob") if not f.get(k)]
    if missing:
        reasons.append("majburiy maydon boʻsh: " + ", ".join(missing))
    if select_name(f.get("Valyuta")) == "USD" and not _has_any(f, "Kurs"):
        reasons.append("USD tranzaksiya kurssiz (Kurs boʻsh)")
    if turi == "Transfer" and not (_has_any(f, "Qabul hisob") and _has_any(f, "Qabul summa")):
        reasons.append("Transfer: qabul hisobi yoki qabul summasi boʻsh")
    if turi == "Chiqim":
        text = " ".join(str(f.get(k) or "") for k in ("Tranzaksiya", "Izoh", "Tavsif")).lower()
        if any(h in text for h in TRANSFER_HINTS):
            reasons.append(
                "hisoblar orasidagi koʻchishga oʻxshaydi — Turi «Transfer» boʻlishi kerak, «Chiqim» emas"
            )
    pnl = str(f.get("P&L — Hisob nazorati") or "")
    if pnl.startswith("XATO:") and not reasons:
        reasons.append(f"P&L — Hisob nazorati: {pnl}")
    if not reasons:
        reasons.append("Nazorat holati = FAIL")
    return reasons


def collect_errors(tx_records: list[dict], today_iso: str) -> list[DigestItem]:
    """Oxirgi 3 kundagi FAIL yoki "XATO:" yozuvlar."""
    from datetime import date, timedelta

    cutoff = (date.fromisoformat(today_iso) - timedelta(days=ERROR_LOOKBACK_DAYS)).isoformat()
    out: list[DigestItem] = []
    for r in tx_records:
        f = r.get("fields") or {}
        rid = str(r.get("id") or "")
        sana = str(f.get("Sana") or "")[:10]
        if not rid or not sana or sana < cutoff:
            continue
        holat = str(f.get("Nazorat holati") or "")
        pnl = str(f.get("P&L — Hisob nazorati") or "")
        if holat != "FAIL" and not pnl.startswith("XATO:"):
            continue
        title = str(f.get("Tranzaksiya") or "Nomsiz tranzaksiya")
        out.append(DigestItem(rid, title, sana, "; ".join(fail_reasons(f)), "error"))
    return out


def format_digest(gaps: list[DigestItem], errors: list[DigestItem]) -> str:
    def _line(it: DigestItem) -> str:
        return (
            f"• <a href=\"{record_link(it.record_id)}\">{html.escape(it.title)}</a> "
            f"({it.sana or 'sanasiz'}) — {html.escape(it.detail)}"
        )

    parts = ["🧾 <b>Airtable nazorati</b> (Tranzaksiyalar)"]
    if errors:
        parts.append("\n❗ <b>Tuzatish kerak</b> (ustun: <i>Nazorat holati</i> = FAIL):")
        parts.extend(_line(e) for e in errors)
    if gaps:
        parts.append("\n✏️ <b>Toʻldirilishi kerak:</b>")
        parts.extend(_line(g) for g in gaps)
    return "\n".join(parts)


def alert_key(it: DigestItem) -> str:
    return f"{ALERT_JOB_PREFIX}{it.kind}:{it.record_id}:{it.detail}"[:250]


async def run_daily_group_digest(
    now: Any = None,
    *,
    read_records: Any = None,
    send_group: Any = None,
    claim: Any = None,
    release: Any = None,
) -> bool:
    """Kuniga bir marta moliya guruhining balans topigiga jamlangan eslatma.

    Har bir ogohlantirish (yozuv + sabab) DB claim bilan faqat bir marta
    yuboriladi. Airtableʼga hech narsa yozilmaydi. Quiet-hours da jim.
    """
    from src.time_utils import get_local_now, is_quiet_hours

    now = now or get_local_now()
    if is_quiet_hours(now):
        return False
    if read_records is None:
        async def read_records() -> tuple[list[dict], bool]:
            return await read_table_checked("Tranzaksiyalar")
    if send_group is None:
        from src.schedulers.moliya.helpers import send

        async def send_group(text: str) -> bool:
            return await send(text, "HISOBCHI_BALANCE_TOPIC_ID")
    if claim is None or release is None:
        from src.db import get_db

        db = get_db()
        claim = claim or db.claim_job_run
        release = release or db.release_job_run

    records, ok = await read_records()
    if not ok:
        return False
    today_iso = now.strftime("%Y-%m-%d")
    fresh: list[DigestItem] = []
    for it in collect_errors(records, today_iso) + collect_gaps(records):
        try:
            if await claim(alert_key(it), "once"):
                fresh.append(it)
        except Exception:
            logger.warning("[AIRTABLE-GAP] claim ishlamadi", exc_info=True)
    if not fresh:
        return True
    errors = [i for i in fresh if i.kind == "error"]
    gaps = [i for i in fresh if i.kind == "gap"]
    if await send_group(format_digest(gaps, errors)):
        return True
    for it in fresh:
        try:
            await release(alert_key(it), "once")
        except Exception:
            logger.warning("[AIRTABLE-GAP] release ishlamadi", exc_info=True)
    return False
