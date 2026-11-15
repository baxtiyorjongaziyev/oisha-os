#!/usr/bin/env python3
"""
👸 OISHA: Tez Natija kurslari → zakazlar auditi (FAQAT O'QISH)

Har bir "TEZ NATIJA N" guruhi uchun:
  1. Telegram: guruh davri (birinchi/oxirgi xabar) va a'zolar (ism, username, telefon)
  2. AmoCRM:   muvaffaqiyatli (status 142) bitimlar, kontakt telefonlari orqali
  3. Airtable: Mijozlar jadvali (LTV real tushum), telefon orqali
Telefon (oxirgi 9 raqam) bo'yicha solishtiradi va CSV hisobot yozadi.

Hech kimga xabar yubormaydi, CRM/Airtable'da hech narsani o'zgartirmaydi.
--send berilsa, faqat hisobotni o'zingizning "Saqlangan xabarlar"ga yuboradi.

Session: USERBOT_SESSION_STRING ishlatilMAYDI (AuthKeyDuplicatedError xavfi).
TN_AUDIT_SESSION_STRING yoki TELEGRAM_MCP_SESSION_STRING (dedicated) kerak.

Usage (Hetzner prod, <OISHA_DIR> dan):
    cd <OISHA_DIR> && .venv/bin/python scripts/prod/tn_revenue_audit.py [--send]
"""

import argparse
import asyncio
import csv
import os
import re
import sys
from collections import defaultdict
from datetime import datetime, timezone

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", ".."))

import requests  # noqa: E402

AIRTABLE_BASE = os.getenv("TN_AUDIT_AIRTABLE_BASE", "app8xoyx1XCumYFXV")
AIRTABLE_TABLE = "Mijozlar"
WON_STATUS_ID = 142
GROUP_RE = re.compile(r"tez\s*natija\s*(\d+)", re.I)
NAME_TAG_RE = re.compile(r"\bT\s*/?\s*N\s*-?\s*(\d)\b", re.I)
OUT_DIR = os.path.join(os.path.dirname(__file__), "..", "..", "data", "tn_audit")


def phone_key(raw) -> str:
    """Telefonni solishtirish kaliti: oxirgi 9 raqam (UZ format)."""
    digits = re.sub(r"\D", "", str(raw or ""))
    return digits[-9:] if len(digits) >= 9 else ""


def name_tag(name: str) -> str:
    """'Ilhomjon aka (TN6)' → 'TN6'."""
    m = NAME_TAG_RE.search(name or "")
    return f"TN{m.group(1)}" if m else ""


def _secret(value) -> str:
    if value is None:
        return ""
    return value.get_secret_value() if hasattr(value, "get_secret_value") else str(value)


# ---------------------------------------------------------------- Telegram
async def collect_telegram(settings):
    from telethon import TelegramClient
    from telethon.sessions import StringSession

    session = os.getenv("TN_AUDIT_SESSION_STRING") or _secret(settings.TELEGRAM_MCP_SESSION_STRING)
    if not session:
        sys.exit("❌ TN_AUDIT_SESSION_STRING yoki TELEGRAM_MCP_SESSION_STRING kerak.")
    if session == _secret(settings.USERBOT_SESSION_STRING):
        sys.exit("❌ Userbot sessiyasini ishlatib bo'lmaydi (prod userbot uziladi).")

    client = TelegramClient(StringSession(session), settings.API_ID, settings.API_HASH)
    await client.connect()
    if not await client.is_user_authorized():
        sys.exit("❌ Telegram sessiya avtorizatsiyadan o'tmagan.")

    groups = {}
    async for dialog in client.iter_dialogs():
        m = GROUP_RE.search(dialog.name or "")
        if not m or not (dialog.is_group or dialog.is_channel):
            continue
        label = f"TN{m.group(1)}"
        first = await client.get_messages(dialog, limit=1, reverse=True)
        members = []
        try:
            async for u in client.iter_participants(dialog):
                if u.bot:
                    continue
                members.append({
                    "name": " ".join(x for x in (u.first_name, u.last_name) if x),
                    "username": u.username or "",
                    "phone": u.phone or "",
                })
        except Exception as e:  # admin bo'lmasak a'zolar yopiq bo'lishi mumkin
            print(f"⚠️ {dialog.name}: a'zolarni o'qib bo'lmadi ({e})")
        entry = groups.setdefault(label, {"titles": [], "start": None, "end": None, "members": []})
        entry["titles"].append(dialog.name)
        start = first[0].date if first else None
        end = dialog.date
        if start and (entry["start"] is None or start < entry["start"]):
            entry["start"] = start
        if end and (entry["end"] is None or end > entry["end"]):
            entry["end"] = end
        entry["members"].extend(members)
        print(f"✅ {dialog.name}: {len(members)} a'zo")
    return client, groups


# ---------------------------------------------------------------- AmoCRM
def _amo_pages(amo, path, params):
    page = 1
    while True:
        r = requests.get(f"{amo.base_url}/api/v4/{path}", headers=amo._get_headers(),
                         params={**params, "page": page, "limit": 250}, timeout=60)
        if r.status_code == 204:
            return
        r.raise_for_status()
        items = list(r.json().get("_embedded", {}).values())
        if not items or not items[0]:
            return
        yield from items[0]
        page += 1


def collect_amocrm():
    """phone_key → [won lead dict] ro'yxati."""
    from src.services.core.crm.amocrm.sync import AmoCRMSync

    amo = AmoCRMSync()
    amo._load_token()
    won = {}
    for lead in _amo_pages(amo, "leads", {"filter[statuses][0][status_id]": WON_STATUS_ID}):
        won[lead["id"]] = {
            "lead": lead.get("name") or "",
            "price": lead.get("price") or 0,
            "closed": datetime.fromtimestamp(lead.get("closed_at") or 0, timezone.utc).date().isoformat(),
        }
    by_phone = defaultdict(list)
    for c in _amo_pages(amo, "contacts", {"with": "leads"}):
        lead_ids = [x["id"] for x in c.get("_embedded", {}).get("leads", []) if x["id"] in won]
        if not lead_ids:
            continue
        for f in c.get("custom_fields_values") or []:
            if f.get("field_code") != "PHONE":
                continue
            for v in f.get("values", []):
                k = phone_key(v.get("value"))
                if k:
                    by_phone[k].extend(won[i] for i in lead_ids if won[i] not in by_phone[k])
    print(f"✅ AmoCRM: {len(won)} ta muvaffaqiyatli bitim, {len(by_phone)} ta telefon")
    return by_phone


# ---------------------------------------------------------------- Airtable
def collect_airtable(settings):
    token = _secret(settings.AIRTABLE_ACCESS_TOKEN) or _secret(settings.AIRTABLE_API_KEY)
    if not token:
        print("⚠️ Airtable token yo'q — o'tkazib yuborildi")
        return {}, []
    url = f"https://api.airtable.com/v0/{AIRTABLE_BASE}/{AIRTABLE_TABLE}"
    rows, offset = [], None
    while True:
        r = requests.get(url, headers={"Authorization": f"Bearer {token}"},
                         params={"offset": offset} if offset else {}, timeout=60)
        r.raise_for_status()
        data = r.json()
        rows += data.get("records", [])
        offset = data.get("offset")
        if not offset:
            break
    by_phone, all_clients = {}, []
    for rec in rows:
        f = rec.get("fields", {})
        client = {"name": f.get("Mijoz ismi", ""), "ltv": f.get("LTV (real tushum)") or 0,
                  "phone": f.get("Telefon raqami", "")}
        all_clients.append(client)
        k = phone_key(client["phone"])
        if k:
            by_phone[k] = client
    print(f"✅ Airtable: {len(rows)} ta mijoz")
    return by_phone, all_clients


# ---------------------------------------------------------------- Report
def build_rows(groups, amo_by_phone, at_by_phone, at_clients):
    detail, summary = [], []
    for label in sorted(groups, key=lambda x: int(x[2:])):
        g = groups[label]
        seen, buyers, amo_sum, at_sum = set(), 0, 0, 0
        for m in g["members"]:
            k = phone_key(m["phone"])
            key = k or m["username"] or m["name"]
            if key in seen:
                continue
            seen.add(key)
            deals = amo_by_phone.get(k, []) if k else []
            at = at_by_phone.get(k) if k else None
            if not deals and not at:
                continue
            buyers += 1
            amo_total = sum(d["price"] for d in deals)
            amo_sum += amo_total
            at_sum += (at or {}).get("ltv", 0)
            detail.append({
                "kurs": label, "ism": m["name"], "username": m["username"], "telefon": m["phone"],
                "amocrm_bitimlar": "; ".join(f'{d["lead"]} ({d["price"]:,}, {d["closed"]})' for d in deals),
                "amocrm_summa": amo_total, "airtable_mijoz": (at or {}).get("name", ""),
                "airtable_ltv": (at or {}).get("ltv", 0), "manba": "telefon",
            })
        # Telefoni yashirin a'zolar uchun: Airtable ismidagi TN belgisi
        for c in at_clients:
            if name_tag(c["name"]) == label and phone_key(c["phone"]) not in seen:
                buyers += 1
                at_sum += c["ltv"]
                detail.append({"kurs": label, "ism": c["name"], "username": "", "telefon": c["phone"],
                               "amocrm_bitimlar": "", "amocrm_summa": 0, "airtable_mijoz": c["name"],
                               "airtable_ltv": c["ltv"], "manba": "ism belgisi"})
        summary.append({
            "kurs": label, "guruhlar": " | ".join(g["titles"]),
            "boshlangan": g["start"].date().isoformat() if g["start"] else "",
            "oxirgi_xabar": g["end"].date().isoformat() if g["end"] else "",
            "azolar": len(seen), "mijozga_aylangan": buyers,
            "amocrm_summa": amo_sum, "airtable_ltv": at_sum,
        })
    return summary, detail


def write_csv(path, rows):
    if not rows:
        return
    with open(path, "w", newline="", encoding="utf-8-sig") as fh:
        w = csv.DictWriter(fh, fieldnames=list(rows[0]))
        w.writeheader()
        w.writerows(rows)


async def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--send", action="store_true", help="Hisobotni Saqlangan xabarlarga yuborish")
    args = ap.parse_args()

    from src.settings import settings

    client, groups = await collect_telegram(settings)
    try:
        amo = collect_amocrm()
        at_by_phone, at_clients = collect_airtable(settings)
        summary, detail = build_rows(groups, amo, at_by_phone, at_clients)

        os.makedirs(OUT_DIR, exist_ok=True)
        stamp = datetime.now().strftime("%Y%m%d_%H%M")
        files = [os.path.join(OUT_DIR, f"tn_summary_{stamp}.csv"), os.path.join(OUT_DIR, f"tn_detail_{stamp}.csv")]
        write_csv(files[0], summary)
        write_csv(files[1], detail)

        lines = ["📊 Tez Natija → zakazlar auditi"]
        for s in summary:
            lines.append(f'{s["kurs"]} ({s["boshlangan"]}): {s["mijozga_aylangan"]}/{s["azolar"]} mijoz, '
                         f'AmoCRM {s["amocrm_summa"]:,} | Airtable LTV {s["airtable_ltv"]:,}')
        text = "\n".join(lines)
        print("\n" + text + f"\n\n📁 {files[0]}\n📁 {files[1]}")
        if args.send:
            await client.send_message("me", text)
            await client.send_file("me", [f for f in files if os.path.exists(f)])
    finally:
        await client.disconnect()


if __name__ == "__main__":
    asyncio.run(main())
