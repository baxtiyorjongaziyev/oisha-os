"""Moliyachi kuzatuvi uchun qo'shimcha manbalar: Gmail va Excel/Google Sheets.

Hammasi faqat o'qiydi va faqat metadata oladi — xat matni, jadval qiymatlari
saqlanmaydi. Sozlanmagan manba jim o'tkazib yuboriladi (bo'sh ro'yxat).

* **Gmail** — IMAP, Google "App passwords" orqali. Sozlamalar: manzil va
  ilova kaliti env o'zgaruvchilari (pastda, .env.example). Kiruvchi (INBOX) va yuborilgan (Sent)
  xatlar: vaqt, jo'natuvchi domeni, mavzu turi (hisob-faktura, to'lov, bank,
  soliq, akt...), ilova turi.
* **Excel / Google Sheets** — Google Drive revision tarixi:
  ``MOLIYACHI_SHEET_IDS`` (vergul bilan Drive fayl ID'lari),
  ``MOLIYACHI_EMAIL`` (faqat shu odam tahrirlari). Service account fayl
  ``HISOBCHI_GSHEET_CREDS_FILE`` / ``GSHEET_CREDS_FILE``; fayllar unga
  "Viewer" sifatida ulashilgan bo'lishi kerak.
"""

from __future__ import annotations

import asyncio
import email.utils
import imaplib
import logging
import os
import re
from datetime import datetime, timedelta, timezone
from email.header import decode_header, make_header
from typing import Optional

logger = logging.getLogger(__name__)

TASHKENT = timezone(timedelta(hours=5))

SUBJECT_KINDS = (
    ("hisob-faktura", r"faktura|invoice|счет|счёт|schet|hisob"),
    ("to'lov", r"to.?lov|payment|оплат|platej|платеж|перевод"),
    ("bank", r"bank|банк|kapital|hamkor|ipak|anor|tbc|uzum"),
    ("soliq", r"soliq|tax|налог|didox|soliq\.uz|my\.soliq"),
    ("akt/shartnoma", r"akt|акт|shartnoma|договор|contract|dogovor"),
    ("hisobot", r"hisobot|report|отчет|отчёт|balans|баланс"),
)


def _env(name: str) -> str:
    return os.getenv(name, "").strip()


def subject_kind(subject: str) -> str:
    s = (subject or "").lower()
    for kind, pattern in SUBJECT_KINDS:
        if re.search(pattern, s):
            return kind
    return "boshqa"


def _decode(value: Optional[str]) -> str:
    try:
        return str(make_header(decode_header(value or "")))
    except Exception:
        return value or ""


def _domain(address: str) -> str:
    _, addr = email.utils.parseaddr(address or "")
    return addr.rsplit("@", 1)[-1].lower() if "@" in addr else ""


def parse_gmail_headers(raw_headers: bytes, *, direction: str, has_attachment: bool) -> Optional[dict]:
    """Bitta xat sarlavhasidan hodisa (matn saqlanmaydi)."""
    msg = email.message_from_bytes(raw_headers)
    try:
        dt = email.utils.parsedate_to_datetime(msg.get("Date"))
    except Exception:
        return None
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    local = dt.astimezone(TASHKENT)
    who = msg.get("From") if direction == "in" else msg.get("To")
    return {
        "day": local.strftime("%Y-%m-%d"),
        "t": local.strftime("%H:%M"),
        "a": "gm_in" if direction == "in" else "gm_out",
        "kind": subject_kind(_decode(msg.get("Subject"))),
        "domain": _domain(_decode(who)),
        "attachment": has_attachment,
    }


_ATTACH_RE = re.compile(rb'"(?:attachment|application)"', re.IGNORECASE)


def _fetch_gmail(day: datetime) -> list[dict]:
    address = _env("MOLIYACHI_GMAIL_ADDRESS")
    password = _env("MOLIYACHI_GMAIL_APP_PASSWORD")
    if not address or not password:
        return []
    since = day.strftime("%d-%b-%Y")
    before = (day + timedelta(days=1)).strftime("%d-%b-%Y")
    target = day.strftime("%Y-%m-%d")
    events: list[dict] = []
    imap = imaplib.IMAP4_SSL("imap.gmail.com", 993, timeout=30)
    try:
        imap.login(address, password)
        for folder, direction in (("INBOX", "in"), ('"[Gmail]/Sent Mail"', "out")):
            status, _ = imap.select(folder, readonly=True)
            if status != "OK":
                continue
            status, data = imap.search(None, "SINCE", since, "BEFORE", before)
            if status != "OK" or not data or not data[0]:
                continue
            for num in data[0].split()[:200]:
                status, parts = imap.fetch(
                    num, "(BODYSTRUCTURE BODY.PEEK[HEADER.FIELDS (FROM TO SUBJECT DATE)])"
                )
                if status != "OK" or not parts:
                    continue
                header = b""
                structure = b""
                for part in parts:
                    if isinstance(part, tuple):
                        structure += part[0]
                        header = part[1]
                    elif isinstance(part, bytes):
                        structure += part
                ev = parse_gmail_headers(
                    header, direction=direction, has_attachment=bool(_ATTACH_RE.search(structure))
                )
                if ev and ev.pop("day") == target:
                    events.append(ev)
    finally:
        try:
            imap.logout()
        except Exception:
            logger.debug("[MOLIYACHI] IMAP logout", exc_info=True)
    return events


async def gmail_events(day: datetime) -> list[dict]:
    try:
        return await asyncio.to_thread(_fetch_gmail, day)
    except Exception:
        logger.warning("[MOLIYACHI] Gmail o'qilmadi", exc_info=True)
        return []


def revisions_to_events(revisions: list[dict], *, file_name: str, day: str, email_filter: str) -> list[dict]:
    events = []
    for rev in revisions:
        user = (rev.get("lastModifyingUser") or {}).get("emailAddress", "").lower()
        if email_filter and user != email_filter.lower():
            continue
        try:
            dt = datetime.fromisoformat(str(rev.get("modifiedTime", "")).replace("Z", "+00:00"))
        except ValueError:
            continue
        local = dt.astimezone(TASHKENT)
        if local.strftime("%Y-%m-%d") != day:
            continue
        events.append({"t": local.strftime("%H:%M"), "a": "xl_edit", "file": file_name})
    return events


def _fetch_sheet_revisions(day: str) -> list[dict]:
    file_ids = [x.strip() for x in _env("MOLIYACHI_SHEET_IDS").split(",") if x.strip()]
    creds_file = _env("HISOBCHI_GSHEET_CREDS_FILE") or _env("GSHEET_CREDS_FILE") or "service_account.json"
    if not file_ids or not os.path.exists(creds_file):
        return []
    from google.oauth2.service_account import Credentials
    from googleapiclient.discovery import build

    creds = Credentials.from_service_account_file(
        creds_file, scopes=["https://www.googleapis.com/auth/drive.metadata.readonly"]
    )
    drive = build("drive", "v3", credentials=creds, cache_discovery=False)
    email_filter = _env("MOLIYACHI_EMAIL")
    events: list[dict] = []
    for file_id in file_ids:
        try:
            meta = drive.files().get(fileId=file_id, fields="name").execute()
            revs = drive.revisions().list(
                fileId=file_id, fields="revisions(modifiedTime,lastModifyingUser)", pageSize=200
            ).execute()
        except Exception:
            logger.warning("[MOLIYACHI] Drive fayl o'qilmadi: %s", file_id, exc_info=True)
            continue
        events.extend(
            revisions_to_events(
                revs.get("revisions", []), file_name=meta.get("name", file_id),
                day=day, email_filter=email_filter,
            )
        )
    return events


async def sheet_events(day: datetime) -> list[dict]:
    try:
        return await asyncio.to_thread(_fetch_sheet_revisions, day.strftime("%Y-%m-%d"))
    except Exception:
        logger.warning("[MOLIYACHI] Excel/Sheets o'qilmadi", exc_info=True)
        return []
