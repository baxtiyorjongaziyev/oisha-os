"""Kunlik sotuvchilar qo'ng'iroq hisoboti (Moizvonki -> Telegram).

Admin API key + ``supervised=1`` bilan butun jamoaning qo'ng'iroqlari olinadi,
har bir sotuvchi (Moizvonki hisobi / email) bo'yicha guruhlanadi.

Ishlatish:
    python scripts/daily_sales_calls_report.py                 # kecha
    python scripts/daily_sales_calls_report.py --date 2026-09-28
    python scripts/daily_sales_calls_report.py --dry-run       # faqat chop etish

Env:
    MOIZVONKI_EMAIL, MOIZVONKI_API_KEY   admin hisob
    MOIZVONKI_DOMAIN                     default: jonbrandingagency.moizvonki.ru
    MOIZVONKI_REP_NAMES                  ixtiyoriy: "email:Ism,email2:Ism2"
    MOIZVONKI_EXCLUDE_ACCOUNTS           ixtiyoriy: hisobotdan chiqariladigan email'lar
                                         (admin MOIZVONKI_EMAIL doim chiqariladi)
    BOT_TOKEN; CRM_SALES_REPORT_GROUP_ID / _TOPIC_ID (default: settings.py qiymatlari)
"""
from __future__ import annotations

import argparse
import html
import logging
import os
import sys
from pathlib import Path

# Repository rootni sys.path ga qo'shish
_REPO_ROOT = str(Path(__file__).resolve().parents[1])
if _REPO_ROOT not in sys.path:
    sys.path.insert(0, _REPO_ROOT)
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from typing import Dict, Iterable, List, Optional

import requests

logger = logging.getLogger("daily_sales_calls_report")

TASHKENT = timezone(timedelta(hours=5))
DIRECTION_IN = 0  # Moizvonki: 0 - kiruvchi, 1 - chiquvchi
DIRECTION_OUT = 1
PAGE_SIZE = 100  # API maksimumi
# src/settings.py dagi CRM_SALES_REPORT_GROUP_ID / CRM_SALES_REPORT_TOPIC_ID defaultlari
DEFAULT_REPORT_GROUP_ID = -1003854308552
DEFAULT_REPORT_TOPIC_ID = 115


# ---------------------------------------------------------------- fetch

def _api_url(domain: str) -> str:
    domain = (domain or "jonbrandingagency.moizvonki.ru").replace("https://", "").strip("/")
    if "." not in domain:
        domain += ".moizvonki.ru"
    return f"https://{domain}/api/v1"


def fetch_calls(email: str, api_key: str, from_ts: int, to_ts: int, domain: str = "") -> List[dict]:
    """Admin nomidan barcha xodimlar qo'ng'iroqlarini sahifalab oladi."""
    url = _api_url(domain)
    calls: List[dict] = []
    offset = 0
    while True:
        payload = {
            "user_name": email,
            "api_key": api_key,
            "action": "calls.list",
            "from_date": from_ts,
            "to_date": to_ts,
            "max_results": PAGE_SIZE,
            "from_offset": offset,
            "supervised": 1,
        }
        resp = requests.post(url, json=payload, timeout=60)
        if resp.status_code != 200:
            raise RuntimeError(f"Moizvonki calls.list http={resp.status_code}: {resp.text[:200]}")
        data = resp.json()
        batch = data.get("results") or []
        calls.extend(batch)
        next_offset = data.get("results_next_offset") or 0
        if not batch or not data.get("results_remains") or next_offset <= offset:
            break
        offset = next_offset
    return calls


# ---------------------------------------------------------------- aggregate

SHORT_CALL_SECONDS = 10  # javobli, lekin juda qisqa suhbat
SOLID_CALL_SECONDS = 180  # kamida 3 daqiqa gaplashilgan sifatli suhbat


@dataclass
class RepStats:
    account: str
    total: int = 0
    outgoing: int = 0
    outgoing_answered: int = 0
    incoming: int = 0
    incoming_answered: int = 0
    talk_seconds: int = 0
    longest: int = 0
    short_calls: int = 0
    solid_calls: int = 0  # javobli va davomiyligi kamida 3 daqiqa (180s)
    wait_seconds: int = 0  # kiruvchiga javob berguncha kutish (jami)
    first_ts: int = 0
    last_ts: int = 0
    clients: set = field(default_factory=set)
    no_callback: int = 0

    @property
    def answered(self) -> int:
        return self.outgoing_answered + self.incoming_answered

    @property
    def missed(self) -> int:
        return self.total - self.answered

    @property
    def outgoing_missed(self) -> int:
        return self.outgoing - self.outgoing_answered

    @property
    def incoming_missed(self) -> int:
        return self.incoming - self.incoming_answered

    @property
    def avg_talk(self) -> int:
        return self.talk_seconds // self.answered if self.answered else 0

    @property
    def avg_wait(self) -> int:
        return self.wait_seconds // self.incoming_answered if self.incoming_answered else 0

    @property
    def answer_rate(self) -> int:
        return round(100 * self.answered / self.total) if self.total else 0

    def add(self, c: dict) -> None:
        self.total += 1
        start = int(c.get("start_time") or 0)
        if start:
            self.first_ts = min(self.first_ts, start) if self.first_ts else start
            self.last_ts = max(self.last_ts, start)
        phone = _norm_phone(c.get("client_number"))
        if phone:
            self.clients.add(phone)
        answered = bool(c.get("answered"))
        if c.get("direction") == DIRECTION_IN:
            self.incoming += 1
            if answered:
                self.incoming_answered += 1
                answer = int(c.get("answer_time") or 0)
                if answer and start and answer >= start:
                    self.wait_seconds += answer - start
        else:
            self.outgoing += 1
            if answered:
                self.outgoing_answered += 1
        if answered:
            dur = int(c.get("duration") or 0)
            self.talk_seconds += dur
            self.longest = max(self.longest, dur)
            if dur < SHORT_CALL_SECONDS:
                self.short_calls += 1
            if dur >= SOLID_CALL_SECONDS:
                self.solid_calls += 1


@dataclass
class Report:
    day: str
    reps: List[RepStats] = field(default_factory=list)
    total: RepStats = field(default_factory=lambda: RepStats(account="Jami"))
    missed_no_callback: List[dict] = field(default_factory=list)
    hourly: Dict[int, int] = field(default_factory=dict)


def _norm_phone(raw) -> str:
    return "".join(ch for ch in str(raw or "") if ch.isdigit())[-9:]


def build_report(
    calls: Iterable[dict],
    day: str,
    followup_calls: Iterable[dict] = (),
    exclude_accounts: Iterable[str] = (),
    known_accounts: Iterable[str] = (),
) -> Report:
    """Qo'ng'iroqlarni sotuvchi bo'yicha guruhlaydi.

    followup_calls — hisobot kunidan keyingi qo'ng'iroqlar; javobsiz kiruvchiga
    keyinroq qayta aloqa bo'lganini aniqlash uchun. Istisno qilingan hisoblar
    (admin) statistikaga kirmaydi, lekin ularning qayta qo'ng'irog'i hisoblanadi.
    """
    excluded = {a.strip().lower() for a in exclude_accounts if a and a.strip()}
    all_calls = sorted(calls, key=lambda c: c.get("start_time") or 0)
    rep_calls = [c for c in all_calls if (c.get("user_account") or "").lower() not in excluded]

    report = Report(day=day)
    reps: Dict[str, RepStats] = {}
    for c in rep_calls:
        account = c.get("user_account") or "noma'lum"
        reps.setdefault(account, RepStats(account=account)).add(c)
        report.total.add(c)
        if c.get("start_time"):
            hour = datetime.fromtimestamp(c["start_time"], TASHKENT).hour
            report.hourly[hour] = report.hourly.get(hour, 0) + 1

    # Javobsiz kiruvchi -> keyin shu raqam bilan javobli suhbat yoki chiquvchi bo'lmagan
    later = all_calls + sorted(followup_calls, key=lambda c: c.get("start_time") or 0)
    seen: set = set()
    for c in rep_calls:
        if c.get("direction") != DIRECTION_IN or c.get("answered"):
            continue
        phone = _norm_phone(c.get("client_number"))
        if not phone or phone in seen:
            continue
        t0 = c.get("start_time") or 0
        handled = any(
            _norm_phone(x.get("client_number")) == phone
            and (x.get("start_time") or 0) > t0
            and (x.get("answered") or x.get("direction") == DIRECTION_OUT)
            for x in later
        )
        if not handled:
            seen.add(phone)
            report.missed_no_callback.append(c)
            reps[c.get("user_account") or "noma'lum"].no_callback += 1
            report.total.no_callback += 1

    # Ro'yxatdagi, lekin bu kun qo'ng'iroq qilmagan sotuvchilar ham ko'rinsin
    present = {a.lower() for a in reps}
    for account in known_accounts:
        if account and account.lower() not in present and account.lower() not in excluded:
            reps[account] = RepStats(account=account)
            present.add(account.lower())

    report.reps = sorted(reps.values(), key=lambda r: (r.talk_seconds, r.total), reverse=True)
    return report


# ---------------------------------------------------------------- format

def fmt_duration(seconds: int) -> str:
    seconds = int(seconds or 0)
    h, rem = divmod(seconds, 3600)
    m, s = divmod(rem, 60)
    if h:
        return f"{h} soat {m} daq"
    if m:
        return f"{m} daq {s} son"
    return f"{s} son"


def _hhmm(ts: int) -> str:
    return datetime.fromtimestamp(ts, TASHKENT).strftime("%H:%M") if ts else "—"


def parse_rep_names(raw: str) -> Dict[str, str]:
    names: Dict[str, str] = {}
    for part in (raw or "").split(","):
        if ":" in part:
            email, name = part.split(":", 1)
            names[email.strip().lower()] = name.strip()
    return names


def _display_name(account: str, names: Dict[str, str]) -> str:
    if account.lower() in names:
        return names[account.lower()]
    local = account.split("@")[0]
    return local.capitalize() if local else account


def _stats_lines(r: RepStats) -> List[str]:
    lines = [
        f"   📞 Jami: <b>{r.total}</b>   ✅ Javob: <b>{r.answered}</b>   "
        f"❌ Ko'tarmadi: <b>{r.missed}</b>  ({r.answer_rate}%)",
        f"   ⬆️ Chiquvchi: {r.outgoing}  (✅ {r.outgoing_answered} / ❌ {r.outgoing_missed})",
        f"   ⬇️ Kiruvchi: {r.incoming}  (✅ {r.incoming_answered} / ❌ {r.incoming_missed})",
        f"   ⏱ Gaplashdi: <b>{fmt_duration(r.talk_seconds)}</b>",
    ]
    if r.answered:
        lines.append(f"   📊 O'rtacha: {fmt_duration(r.avg_talk)}   Eng uzun: {fmt_duration(r.longest)}")
    extra = [f"👥 Mijozlar: {len(r.clients)}"]
    if r.short_calls:
        extra.append(f"⚡ &lt;{SHORT_CALL_SECONDS}s: {r.short_calls}")
    if r.incoming_answered:
        extra.append(f"⏳ Javob kutish: {fmt_duration(r.avg_wait)}")
    lines.append("   " + "   ".join(extra))
    lines.append(f"   🕘 Ish vaqti: {_hhmm(r.first_ts)} – {_hhmm(r.last_ts)}")
    if r.no_callback:
        lines.append(f"   ⚠️ Qayta qo'ng'iroq qilinmagan: <b>{r.no_callback}</b>")
    return lines


def format_report(report: Report, names: Optional[Dict[str, str]] = None) -> str:
    """Format call report using clean ROP motivation format."""
    from src.services.call_analytics.call_report_formatter import format_report_rop

    return format_report_rop(report, names)


def split_message(text: str, limit: int = 4000) -> List[str]:
    """Telegram 4096 belgi chegarasi uchun qatorlar bo'yicha bo'ladi."""
    chunks: List[str] = []
    current = ""
    for line in text.split("\n"):
        if current and len(current) + len(line) + 1 > limit:
            chunks.append(current)
            current = line
        else:
            current = f"{current}\n{line}" if current else line
    if current:
        chunks.append(current)
    return chunks


# ---------------------------------------------------------------- send

def send_telegram(bot_token: str, chat_id: str, text: str, topic_id: Optional[str] = None) -> None:
    payload = {"chat_id": chat_id, "text": text, "parse_mode": "HTML", "disable_web_page_preview": True}
    if topic_id:
        payload["message_thread_id"] = int(topic_id)
    resp = requests.post(f"https://api.telegram.org/bot{bot_token}/sendMessage", json=payload, timeout=30)
    if resp.status_code != 200:
        raise RuntimeError(f"Telegram sendMessage http={resp.status_code}: {resp.text[:200]}")


# ---------------------------------------------------------------- main

def _day_bounds(day: Optional[str]) -> tuple[datetime, datetime]:
    if day:
        start = datetime.strptime(day, "%Y-%m-%d").replace(tzinfo=TASHKENT)
    else:
        start = (datetime.now(TASHKENT) - timedelta(days=1)).replace(hour=0, minute=0, second=0, microsecond=0)
    return start, start + timedelta(days=1)


def main(argv: Optional[List[str]] = None) -> int:
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
    parser = argparse.ArgumentParser(description="Kunlik sotuvchilar qo'ng'iroq hisoboti")
    parser.add_argument("--date", help="YYYY-MM-DD (default: kecha, Toshkent vaqti)")
    parser.add_argument("--dry-run", action="store_true", help="Telegramga yubormay chop etish")
    args = parser.parse_args(argv)

    try:
        from dotenv import find_dotenv, load_dotenv

        load_dotenv(find_dotenv(usecwd=True))
    except ImportError:
        pass

    email = os.environ.get("MOIZVONKI_EMAIL", "")
    api_key = os.environ.get("MOIZVONKI_API_KEY", "")
    if not email or not api_key:
        logger.error("MOIZVONKI_EMAIL / MOIZVONKI_API_KEY topilmadi")
        return 1
    domain = os.environ.get("MOIZVONKI_DOMAIN", "")

    start, end = _day_bounds(args.date)
    now_ts = int(datetime.now(TASHKENT).timestamp())
    calls = fetch_calls(email, api_key, int(start.timestamp()), int(end.timestamp()) - 1, domain)
    followup = []
    if int(end.timestamp()) < now_ts:
        followup = fetch_calls(email, api_key, int(end.timestamp()), now_ts, domain)

    # Admin hisobi sotuvchi emas; qo'shimcha istisnolar MOIZVONKI_EXCLUDE_ACCOUNTS orqali
    exclude = [email, *os.environ.get("MOIZVONKI_EXCLUDE_ACCOUNTS", "").split(",")]
    names = parse_rep_names(os.environ.get("MOIZVONKI_REP_NAMES", ""))
    report = build_report(calls, start.strftime("%Y-%m-%d"), followup, exclude, known_accounts=names)
    text = format_report(report, names)

    if args.dry_run:
        print(text)
        return 0

    bot_token = os.environ.get("BOT_TOKEN", "")
    # oracle-deploy .env ga bu qiymatlarni yozmaydi -> settings.py defaultlari
    chat_id = os.environ.get("CRM_SALES_REPORT_GROUP_ID") or str(DEFAULT_REPORT_GROUP_ID)
    topic_id = os.environ.get("CRM_SALES_REPORT_TOPIC_ID") or str(DEFAULT_REPORT_TOPIC_ID)
    if not bot_token:
        logger.error("BOT_TOKEN topilmadi")
        return 1
    for chunk in split_message(text):
        send_telegram(bot_token, chat_id, chunk, topic_id)
    logger.info("Hisobot yuborildi: %s, %d qo'ng'iroq", report.day, len(calls))
    return 0


if __name__ == "__main__":
    sys.exit(main())
