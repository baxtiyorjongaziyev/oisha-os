"""
daily_sales_calls_report.py — Kunlik sotuvchilar qo'ng'iroq hisoboti.

Moizvonki API (calls.list) orqali o'tgan kunning qo'ng'iroq
statistikasini yig'ib, Telegram guruhga yuboradi.

Ishlatish:
    python scripts/daily_sales_calls_report.py [--date YYYY-MM-DD]

Muhit o'zgaruvchilari (.env):
    MOIZVONKI_API_KEY    — Moizvonki JSON-RPC API kaliti
    MOIZVONKI_DOMAIN     — masalan: jonbrandingagency.moizvonki.ru
    BOT_TOKEN            — Telegram bot token
    CRM_SALES_REPORT_GROUP_ID — Telegram guruh ID (hisobot yuborish uchun)
    CRM_SALES_REPORT_TOPIC_ID — Topic ID (agar supergroup bo'lsa)
"""
from __future__ import annotations

import argparse
import asyncio
import logging
import os
import sys
from collections import defaultdict
from datetime import datetime, timedelta, timezone

import requests
from typing import Any, Dict, List, Optional, Tuple

# Project root
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
logger = logging.getLogger("daily_sales_calls")


# ── Sotuvchilar telefon raqamlari xaritasi ──────────────────────
# Moizvonki'dan kelgan src_number (chiquvchi) / dst_number (kiruvchi)
# raqamlarni sotuvchi nomiga bog'laydi.
# Yangi sotuvchi qo'shilsa, shu yerga qo'shing.
SALES_REPS: Dict[str, str] = {
    # raqam oxiri (oxirgi 9 raqam) -> ism
    # TODO: Haqiqiy telefon raqamlarini qo'shish kerak
    # Misol:
    # "998901234567": "Nozima",
    # "998907654321": "Bobur",
    # "998908765432": "Ziyoda",
}


def _load_env() -> None:
    """Load .env faylini yuklash."""
    try:
        from dotenv import load_dotenv
        load_dotenv()
    except ImportError:
        pass


def _normalize_phone(raw: str) -> str:
    """Telefon raqamdan faqat raqamlarni ajratadi."""
    return "".join(ch for ch in str(raw or "") if ch.isdigit())


def _resolve_rep_name(phone: str) -> str:
    """Telefon raqamni sotuvchi ismiga bog'laydi."""
    digits = _normalize_phone(phone)
    if digits in SALES_REPS:
        return SALES_REPS[digits]
    # Oxirgi 9 raqam bo'yicha qidirish
    suffix = digits[-9:] if len(digits) >= 9 else digits
    for key, name in SALES_REPS.items():
        if key.endswith(suffix) or suffix.endswith(key[-9:]):
            return name
    # Topilmasa — raqamning o'zi
    return phone or "Noma'lum"


# ── Moizvonki API ───────────────────────────────────────────────
def fetch_calls(
    api_key: str,
    domain: str,
    from_ts: int,
    to_ts: int,
    user_name: str = "jonbranding@agency.uz",
) -> List[Dict[str, Any]]:
    """Moizvonki calls.list API orqali qo'ng'iroqlar ro'yxatini oladi.

    API format: POST /api/v1
    Payload: user_name, api_key, action=calls.list, from_date, max_results
    Javob:   {"results": [...], "results_count": N, "results_remains": N}
    """
    url = f"https://{domain}/api/v1"
    all_calls: List[Dict[str, Any]] = []
    offset = 0
    max_per_page = 100

    while True:
        payload: Dict[str, Any] = {
            "user_name": user_name,
            "api_key": api_key,
            "action": "calls.list",
            "from_date": from_ts,
            "max_results": max_per_page,
        }
        if offset > 0:
            payload["results_offset"] = offset

        try:
            resp = requests.post(url, json=payload, timeout=30)
            resp.raise_for_status()
            data = resp.json()
        except requests.RequestException as exc:
            logger.error("[REPORT] Moizvonki API xatosi: %s", exc)
            break
        except ValueError as exc:
            logger.error("[REPORT] Moizvonki JSON parse xatosi: %s", exc)
            break

        results = data.get("results") or []
        if not isinstance(results, list):
            logger.warning("[REPORT] calls.list kutilmagan format: %s", type(results))
            break

        # to_ts dan keyingi qo'ng'iroqlarni filtrlash
        for call in results:
            start = int(call.get("start_time", 0) or 0)
            if start <= to_ts:
                all_calls.append(call)

        remains = int(data.get("results_remains", 0) or 0)
        if remains <= 0 or not results:
            break
        offset += len(results)

    logger.info("[REPORT] Moizvonki'dan %d ta qo'ng'iroq olindi", len(all_calls))
    return all_calls


# ── Hisobot generatsiya ─────────────────────────────────────────
def _format_duration(seconds: int) -> str:
    """Sekundlarni 'Xh Ym Zs' formatiga aylantiradi."""
    if seconds < 0:
        seconds = 0
    h, remainder = divmod(seconds, 3600)
    m, s = divmod(remainder, 60)
    parts = []
    if h:
        parts.append(f"{h}s")
    if m or h:
        parts.append(f"{m}d")
    parts.append(f"{s}s")
    return " ".join(parts)


def build_report(
    calls: List[Dict[str, Any]],
    report_date: str,
) -> str:
    """Qo'ng'iroqlar ro'yxatidan o'zbekcha hisobot matni yaratadi."""
    if not calls:
        return (
            f"📞 *Kunlik Qo'ng'iroq Hisoboti*\n"
            f"📅 Sana: {report_date}\n\n"
            f"⚠️ Bu kunda qo'ng'iroqlar topilmadi."
        )

    # Har bir sotuvchi bo'yicha aggregatsiya
    rep_stats: Dict[str, Dict[str, Any]] = defaultdict(
        lambda: {
            "total": 0,
            "answered": 0,
            "missed": 0,
            "incoming": 0,
            "outgoing": 0,
            "total_duration": 0,
            "clients": set(),
        }
    )

    total_calls = 0
    total_duration = 0
    total_answered = 0
    total_missed = 0

    for call in calls:
        # Moizvonki API haqiqiy maydonlari:
        #   direction: 0=chiquvchi, 1=kiruvchi
        #   client_number: mijoz raqami
        #   duration: davomiyligi (sek)
        #   answered: 0/1
        #   src_id: xodim (qurilma) IDsi
        #   client_name: kontakt nomi (agar CRM da bo'lsa)
        direction = call.get("direction", 0)
        duration = int(call.get("duration", 0) or 0)
        is_answered = bool(call.get("answered", 0))

        is_incoming = (direction == 1)
        is_outgoing = (direction == 0)

        # Sotuvchini aniqlash: src_id yoki src_number
        src_id = str(call.get("src_id", "") or "")
        rep_phone = str(call.get("src_number", "") or "")
        client_phone = str(call.get("client_number", "") or "")

        # Agar src_number bo'sh bo'lsa, src_id asosida aniqlash
        rep_key = rep_phone if rep_phone else f"Xodim #{src_id}"
        rep_name = _resolve_rep_name(rep_key)

        stats = rep_stats[rep_name]
        stats["total"] += 1
        stats["total_duration"] += duration
        if is_answered:
            stats["answered"] += 1
        else:
            stats["missed"] += 1
        if is_incoming:
            stats["incoming"] += 1
        elif is_outgoing:
            stats["outgoing"] += 1
        if client_phone:
            stats["clients"].add(_normalize_phone(client_phone))

        total_calls += 1
        total_duration += duration
        if is_answered:
            total_answered += 1
        else:
            total_missed += 1

    # Hisobot matni
    lines = [
        f"📞 *Kunlik Qo'ng'iroq Hisoboti*",
        f"📅 Sana: {report_date}",
        "",
        f"📊 *Umumiy statistika:*",
        f"  • Jami qo'ng'iroqlar: *{total_calls}*",
        f"  • Javob berilgan: *{total_answered}*",
        f"  • Javobsiz: *{total_missed}*",
        f"  • Umumiy davomiylik: *{_format_duration(total_duration)}*",
        "",
        "👥 *Sotuvchilar bo'yicha:*",
    ]

    # Sotuvchilarni qo'ng'iroq soni bo'yicha tartiblash
    sorted_reps = sorted(
        rep_stats.items(),
        key=lambda x: x[1]["total"],
        reverse=True,
    )

    for i, (rep_name, stats) in enumerate(sorted_reps, 1):
        avg_dur = (
            stats["total_duration"] // stats["answered"]
            if stats["answered"] > 0
            else 0
        )
        uniq_clients = len(stats["clients"])

        lines.append(f"\n{'─' * 30}")
        lines.append(f"*{i}. {rep_name}*")
        lines.append(
            f"  📱 Jami: {stats['total']} "
            f"(📥 {stats['incoming']} kiruvchi, "
            f"📤 {stats['outgoing']} chiquvchi)"
        )
        lines.append(
            f"  ✅ Javob: {stats['answered']} | "
            f"❌ Javobsiz: {stats['missed']}"
        )
        lines.append(f"  ⏱ Umumiy: {_format_duration(stats['total_duration'])}")
        lines.append(f"  ⏳ O'rtacha: {_format_duration(avg_dur)}")
        lines.append(f"  👤 Noyob mijozlar: {uniq_clients}")

    lines.append(f"\n{'═' * 30}")
    lines.append("🤖 _Hisobot Oisha-OS tomonidan avtomatik yaratildi_")

    return "\n".join(lines)


# ── Telegram yuborish ────────────────────────────────────────────
async def send_telegram_report(
    bot_token: str,
    chat_id: int,
    text: str,
    topic_id: Optional[int] = None,
) -> bool:
    """Telegram Bot API orqali hisobotni yuboradi."""
    import aiohttp

    url = f"https://api.telegram.org/bot{bot_token}/sendMessage"
    payload: Dict[str, Any] = {
        "chat_id": chat_id,
        "text": text,
        "parse_mode": "Markdown",
        "disable_web_page_preview": True,
    }
    if topic_id:
        payload["message_thread_id"] = topic_id

    try:
        async with aiohttp.ClientSession() as session:
            async with session.post(url, json=payload, timeout=aiohttp.ClientTimeout(total=30)) as resp:
                result = await resp.json()
                if resp.status == 200 and result.get("ok"):
                    logger.info(
                        "[REPORT] Hisobot Telegramga yuborildi (chat=%s)",
                        chat_id,
                    )
                    return True
                logger.error(
                    "[REPORT] Telegram xatosi: status=%s body=%s",
                    resp.status,
                    result,
                )
                return False
    except Exception as exc:
        logger.error("[REPORT] Telegram yuborishda xato: %s", exc)
        return False


# ── Asosiy funksiya ──────────────────────────────────────────────
def _parse_date(date_str: Optional[str]) -> Tuple[datetime, str]:
    """CLI argumentdan sanani aniqlaydi. Default = kecha."""
    tz = timezone(timedelta(hours=5))  # Asia/Tashkent = UTC+5
    if date_str:
        dt = datetime.strptime(date_str, "%Y-%m-%d").replace(tzinfo=tz)
    else:
        dt = datetime.now(tz) - timedelta(days=1)
    return dt, dt.strftime("%Y-%m-%d")


async def main() -> None:
    """Asosiy ishga tushirish funksiyasi."""
    _load_env()

    parser = argparse.ArgumentParser(description="Kunlik sotuvchilar qo'ng'iroq hisoboti")
    parser.add_argument(
        "--date",
        type=str,
        default=None,
        help="Hisobot sanasi (YYYY-MM-DD). Default: kecha.",
    )
    args = parser.parse_args()

    # Sozlamalar
    api_key = os.environ.get("MOIZVONKI_API_KEY", "")
    domain = os.environ.get("MOIZVONKI_DOMAIN", "jonbrandingagency.moizvonki.ru")
    bot_token = os.environ.get("BOT_TOKEN", "")
    chat_id = int(os.environ.get("CRM_SALES_REPORT_GROUP_ID", "0") or "0")
    topic_id_str = os.environ.get("CRM_SALES_REPORT_TOPIC_ID") or os.environ.get("TOPIC_REPORTS_ID")
    topic_id = int(topic_id_str) if topic_id_str else None

    # Tekshirish
    if not api_key:
        logger.error("MOIZVONKI_API_KEY topilmadi. .env ga qo'shing.")
        sys.exit(1)
    if not bot_token:
        logger.error("BOT_TOKEN topilmadi. .env ga qo'shing.")
        sys.exit(1)
    if not chat_id:
        logger.error("CRM_SALES_REPORT_GROUP_ID topilmadi. .env ga qo'shing.")
        sys.exit(1)

    # Sanani aniqlash
    report_dt, report_date = _parse_date(args.date)
    from_ts = int(report_dt.replace(hour=0, minute=0, second=0, microsecond=0).timestamp())
    to_ts = from_ts + 86400 - 1

    logger.info(
        "[REPORT] Hisobot yaratilmoqda: sana=%s, from=%s, to=%s",
        report_date, from_ts, to_ts,
    )

    # Moizvonki'dan qo'ng'iroqlarni olish
    calls = fetch_calls(api_key, domain, from_ts, to_ts)

    # Hisobot matni
    report_text = build_report(calls, report_date)
    logger.info("[REPORT] Hisobot:\n%s", report_text)

    # Telegramga yuborish
    success = await send_telegram_report(bot_token, chat_id, report_text, topic_id)
    if success:
        logger.info("[REPORT] ✅ Hisobot muvaffaqiyatli yuborildi!")
    else:
        logger.error("[REPORT] ❌ Hisobot yuborilmadi!")
        sys.exit(1)


if __name__ == "__main__":
    asyncio.run(main())
