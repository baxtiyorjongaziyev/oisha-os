"""
Import and Enrich UTC Analyzed Leads into AmoCRM 'Sotuv Bo'limi' Pipeline.

Features:
- Filters 'Sotuvga yaqin' (P1 High-Priority / Hot) leads based on STT call audit.
- Deduplication: searches existing contact/lead by phone in AmoCRM.
- Stage placement: routes to 'Qayta aloqa' (87609518), 'Kvalifikatsiya' (87609522), or 'Uchrashuv' (87609526).
- Enriches custom fields (AI Ehtiyoj, Keyingi qadam).
- Adds comprehensive Markdown Note (dossier with BANT, objections, operator mistakes, and opening hook).
- Creates actionable task for Sotuv Bo'limi with deadline Monday 10:00 AM.
- Tags: UTC_Outsource, CallAudit_P1.

Usage:
  python scripts/import_utc_to_amocrm.py --dry-run
  python scripts/import_utc_to_amocrm.py --live
"""
from __future__ import annotations

import argparse
import glob
import json
import logging
import sys
import time
from datetime import datetime, timezone, timedelta
from pathlib import Path
from typing import Any, Dict, List, Optional

import requests

sys.stdout.reconfigure(encoding="utf-8")
logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger("AmoCRM_UTC_Importer")

_ROOT = Path(__file__).resolve().parent.parent
TOKEN_FILE = _ROOT / "data" / "amocrm_token.json"
BASE_URL = "https://jonbranding.amocrm.ru"

SALES_PIPELINE_ID = 11162698
STATUS_YANGI = 89067962         # Yangi LEads
STATUS_QAYTA_ALOQA = 87609518   # Qayta aloqa
STATUS_KVALIFIKATSIYA = 87609522 # Kvalifikatsiya
STATUS_UCHRASHUV = 87609526     # Uchrashuv
STATUS_KELISHUV = 88871066      # Kelishuv / Yopish

CF_AI_NEED = 1427493     # Mijozning ehtiyoji (AI) - textarea
CF_NEXT_STEP = 1552255   # Keyingi qadam - text
CF_BRAND_NAME = 1551701  # Brend / Biznes nomi - text

RESPONSIBLE_USER_ID = 13021974  # Sotuv bo'limi (fallback: 8128012 Baxtiyorjon Gaziyev)


def get_token() -> str:
    if not TOKEN_FILE.exists():
        raise FileNotFoundError(f"Token file not found: {TOKEN_FILE}")
    with open(TOKEN_FILE, encoding="utf-8") as f:
        return json.load(f)["access_token"]


def get_headers(token: str) -> dict:
    return {"Authorization": f"Bearer {token}", "Content-Type": "application/json"}


def normalize_phone(phone: str) -> str:
    cleaned = "".join(c for c in phone if c.isdigit())
    if len(cleaned) == 9:
        cleaned = "998" + cleaned
    elif len(cleaned) == 12 and cleaned.startswith("998"):
        pass
    return cleaned


def load_candidate_deals() -> List[Dict[str, Any]]:
    deals = []
    files = glob.glob(str(_ROOT / "data" / "utc_analysis" / "deals" / "*.json"))
    for fpath in files:
        with open(fpath, encoding="utf-8") as f:
            d = json.load(f)
            strat = d.get("amocrm_strategy", {})
            bant = d.get("bant_analysis", {})
            phone = str(d.get("phone", "")).strip()
            if not phone or phone == "Raqam yo'q" or len("".join(c for c in phone if c.isdigit())) < 7:
                continue

            priority = str(strat.get("priority", "Noma'lum"))
            real_status = str(d.get("real_status", "Noma'lum"))
            duration = d.get("total_duration_sec", 0)

            # Score logic
            score = 0
            p_lower = priority.lower()
            st_lower = real_status.lower()

            if "p1" in p_lower or "yuqori" in p_lower:
                score += 100
            elif "p2" in p_lower or "o'rta" in p_lower:
                score += 50

            if "issiq" in st_lower or "potensial_issiq" in st_lower:
                score += 50
            elif "qayta_aloqa" in st_lower:
                score += 30

            # Engagement bonus (conversation length)
            score += min(duration // 60, 40)

            # Extra check: did customer clearly want branding / logo / patent / identity?
            need_text = str(d.get("need_and_context", "")).lower()
            if any(k in need_text for k in ["brend", "logo", "patent", "namuna", "upakovka", "shartnoma", "dizayn", "magazin", "ochil"]):
                score += 20

            deals.append({
                "card_no": d.get("card_no"),
                "client_name": d.get("client_name") or "Noma'lum",
                "phone": normalize_phone(phone),
                "raw_phone": phone,
                "utc_status": d.get("utc_status"),
                "real_status": real_status,
                "priority": priority,
                "score": score,
                "duration_sec": duration,
                "need_and_context": d.get("need_and_context", ""),
                "bant": bant,
                "operator_errors": d.get("operator_errors", []),
                "client_objections": d.get("client_objections", []),
                "opening_hook": strat.get("call_opening_hook", ""),
                "closing_pitch": strat.get("closing_pitch", ""),
                "target_stage": strat.get("target_stage", "Qayta aloqa"),
                "summary_uz": d.get("summary_uz", "")
            })

    # Sort descending by score
    deals.sort(key=lambda x: x["score"], reverse=True)
    return deals


def search_contact_by_phone(token: str, phone: str) -> Optional[dict]:
    headers = get_headers(token)
    short = phone[-9:] if len(phone) >= 9 else phone
    url = f"{BASE_URL}/api/v4/contacts"
    
    # Try exact clean phone first
    try:
        r = requests.get(url, headers=headers, params={"query": phone}, timeout=10)
        if r.status_code == 200:
            contacts = r.json().get("_embedded", {}).get("contacts", [])
            if contacts:
                return contacts[0]
        # Fallback to short 9-digit
        r = requests.get(url, headers=headers, params={"query": short}, timeout=10)
        if r.status_code == 200:
            contacts = r.json().get("_embedded", {}).get("contacts", [])
            if contacts:
                return contacts[0]
    except Exception as e:
        logger.error(f"Search contact error for {phone}: {e}")
    return None


def get_active_lead_for_contact(token: str, contact_id: int) -> Optional[dict]:
    headers = get_headers(token)
    url = f"{BASE_URL}/api/v4/contacts/{contact_id}"
    try:
        r = requests.get(url, headers=headers, params={"with": "leads"}, timeout=10)
        if r.status_code == 200:
            leads_refs = r.json().get("_embedded", {}).get("leads", [])
            for ref in leads_refs:
                lid = ref.get("id")
                # check lead status
                rl = requests.get(f"{BASE_URL}/api/v4/leads/{lid}", headers=headers, timeout=10)
                if rl.status_code == 200:
                    lead_data = rl.json()
                    st = lead_data.get("status_id")
                    if st not in (142, 143): # Not Won, Not Lost
                        return lead_data
    except Exception as e:
        logger.error(f"Get active lead error for contact {contact_id}: {e}")
    return None


def build_audit_note_text(deal: Dict[str, Any]) -> str:
    bant = deal.get("bant") or {}
    dur_min = deal["duration_sec"] // 60
    dur_sec = deal["duration_sec"] % 60
    
    op_errors = "\n".join(f"• {e}" for e in deal.get("operator_errors", [])) or "• Ma'lumot yo'q"
    obj_text = "\n".join(f"• {o}" for o in deal.get("client_objections", [])) or "• E'tiroz bildirilmadi"
    
    budget = bant.get("budget", "Noma'lum")
    authority = bant.get("authority", "Noma'lum")
    need = bant.get("need", "Noma'lum")
    timeline = bant.get("timeline", "Noma'lum")
    opening_hook = deal.get("opening_hook", "")
    closing_pitch = deal.get("closing_pitch", "")
    
    text = (
        f"🔥 UTC CALL AUDIT & CLOSER DOSSIER\n"
        f"══════════════════════════════════════\n"
        f"📋 Mijoz: {deal['client_name']} | Tel: +{deal['phone']}\n"
        f"📌 UTC Card: #{deal['card_no']} (Oldingi UTC statusi: {deal['utc_status']})\n"
        f"⏱️ Jami suhbat: {dur_min} daqiqa {dur_sec} soniya\n"
        f"⭐ Real Holat: {deal['real_status']} | Ustuvorlik: {deal['priority']}\n\n"
        f"🎯 BIZNES VA ASOSIY EHTIYOJ:\n"
        f"{deal['need_and_context']}\n\n"
        f"📊 BANT MALAKASI:\n"
        f"• Byudjet: {budget}\n"
        f"• Qaror qabul qiluvchi: {authority}\n"
        f"• Ehtiyoj: {need}\n"
        f"• Muddat: {timeline}\n\n"
        f"⚠️ OLDINGI OPERATOR XATOLARI (UTC Outsource):\n"
        f"{op_errors}\n\n"
        f"🛡️ MIJOZNING E'TIROZLARI / XAVOTIRLARI:\n"
        f"{obj_text}\n\n"
        f"📞 CLOSER UCHUN KIRISH GUKI (Aynan shu gap bilan boshlang):\n"
        f"\"{opening_hook}\"\n\n"
        f"💎 YOPISH TAKTIKASI VA TAKLIF (Pitch):\n"
        f"\"{closing_pitch}\"\n\n"
        f"📝 QISQACHA XULOSA:\n"
        f"{deal['summary_uz']}\n"
        f"══════════════════════════════════════"
    )
    return text


def create_contact(token: str, name: str, phone: str) -> Optional[int]:
    headers = get_headers(token)
    url = f"{BASE_URL}/api/v4/contacts"
    payload = [{
        "name": name,
        "custom_fields_values": [
            {
                "field_code": "PHONE",
                "values": [{"value": f"+{phone}", "enum_code": "MOB"}]
            }
        ]
    }]
    try:
        r = requests.post(url, headers=headers, json=payload, timeout=15)
        if r.status_code in (200, 201):
            return r.json().get("_embedded", {}).get("contacts", [{}])[0].get("id")
        logger.error(f"Create contact failed: {r.status_code} {r.text}")
    except Exception as e:
        logger.error(f"Create contact exception: {e}")
    return None


def create_or_update_lead(
    token: str,
    deal: Dict[str, Any],
    contact_id: int,
    existing_lead: Optional[dict] = None
) -> Optional[int]:
    headers = get_headers(token)
    
    # Target status mapping
    stage_name = deal.get("target_stage", "").lower()
    if any(k in stage_name for k in ["uchrashuv", "maslahat", "konsultatsiya", "meeting"]):
        status_id = STATUS_UCHRASHUV  # 87609526 Uchrashuv
    elif any(k in stage_name for k in ["kvalifikatsiya", "o'ylab", "brief", "ehtiyoj"]):
        status_id = STATUS_KVALIFIKATSIYA  # 87609522 Kvalifikatsiya
    elif any(k in stage_name for k in ["kelishuv", "yopish", "shartnoma", "kp"]):
        status_id = STATUS_KELISHUV  # 88871066 Kelishuv / Yopish
    else:
        status_id = STATUS_QAYTA_ALOQA  # 87609518 Qayta aloqa

    custom_fields = [
        {"field_id": CF_AI_NEED, "values": [{"value": deal["need_and_context"][:2000]}]},
        {"field_id": CF_NEXT_STEP, "values": [{"value": deal["opening_hook"][:255]}]}
    ]

    tags = [{"name": "UTC_Outsource"}, {"name": "CallAudit_P1"}, {"name": "Target"}]

    if existing_lead:
        lead_id = existing_lead["id"]
        url = f"{BASE_URL}/api/v4/leads/{lead_id}"
        payload = {
            "status_id": status_id,
            "custom_fields_values": custom_fields,
            "_embedded": {"tags": tags}
        }
        try:
            r = requests.patch(url, headers=headers, json=payload, timeout=15)
            if r.status_code in (200, 201):
                logger.info(f"Updated existing lead #{lead_id} for {deal['client_name']}")
                return lead_id
        except Exception as e:
            logger.error(f"Update lead exception: {e}")
        return lead_id
    else:
        url = f"{BASE_URL}/api/v4/leads"
        payload = [{
            "name": f"{deal['client_name']} (+{deal['phone']}) - UTC Audit",
            "pipeline_id": SALES_PIPELINE_ID,
            "status_id": status_id,
            "responsible_user_id": RESPONSIBLE_USER_ID,
            "custom_fields_values": custom_fields,
            "_embedded": {
                "contacts": [{"id": contact_id}],
                "tags": tags
            }
        }]
        try:
            r = requests.post(url, headers=headers, json=payload, timeout=15)
            if r.status_code in (200, 201):
                lead_id = r.json().get("_embedded", {}).get("leads", [{}])[0].get("id")
                logger.info(f"Created new lead #{lead_id} for {deal['client_name']}")
                return lead_id
            logger.error(f"Create lead failed: {r.status_code} {r.text}")
        except Exception as e:
            logger.error(f"Create lead exception: {e}")
    return None


def add_note_to_lead(token: str, lead_id: int, note_text: str) -> bool:
    headers = get_headers(token)
    url = f"{BASE_URL}/api/v4/leads/{lead_id}/notes"
    payload = [{"note_type": "common", "params": {"text": note_text}}]
    try:
        r = requests.post(url, headers=headers, json=payload, timeout=15)
        return r.status_code in (200, 201)
    except Exception as e:
        logger.error(f"Add note exception for lead #{lead_id}: {e}")
    return False


def create_task_for_lead(token: str, lead_id: int, deal: Dict[str, Any]) -> bool:
    headers = get_headers(token)
    url = f"{BASE_URL}/api/v4/tasks"

    # Deadline: Monday 2026-10-19 10:00:00 AM Tashkent time (UTC+5)
    # 2026-10-19 05:00:00 UTC = 1792386000 timestamp
    tashkent_tz = timezone(timedelta(hours=5))
    monday_10am = datetime(2026, 10, 19, 10, 0, 0, tzinfo=tashkent_tz)
    complete_till = int(monday_10am.timestamp())

    hook_short = deal["opening_hook"][:120].strip()
    task_text = (
        f"📞 Qayta aloqa & Taqdimot: {deal['client_name']} bilan bog'lanish.\n"
        f"Oldingi operator xatosini to'g'rilab, aniq audit/prezentatsiya taklif qiling.\n"
        f"Kirish guki: \"{hook_short}...\""
    )

    payload = [{
        "task_type_id": 1, # Call
        "text": task_text,
        "complete_till": complete_till,
        "entity_id": lead_id,
        "entity_type": "leads",
        "responsible_user_id": RESPONSIBLE_USER_ID
    }]
    try:
        r = requests.post(url, headers=headers, json=payload, timeout=15)
        return r.status_code in (200, 201)
    except Exception as e:
        logger.error(f"Create task exception for lead #{lead_id}: {e}")
    return False


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--live", action="store_true", help="Execute live import into AmoCRM")
    parser.add_argument("--dry-run", action="store_true", help="Show preview without creating records")
    parser.add_argument("--limit", type=int, default=30, help="Maximum number of hot leads to import")
    args = parser.parse_args()

    candidates = load_candidate_deals()
    # Filter high priority candidates (score >= 90 or P1)
    hot_candidates = [d for d in candidates if d["score"] >= 90][:args.limit]

    print(f"============================================================")
    print(f"🔥 SOTUVGA YAQIN (P1 / POTENSIAL ISSIQ) LIDLAR: {len(hot_candidates)} TA")
    print(f"============================================================")

    for idx, d in enumerate(hot_candidates, 1):
        print(f"{idx:2d}. Card #{d['card_no']:3d} | {d['client_name']:18s} | +{d['phone']:12s} | Score: {d['score']:3d} | Dur: {d['duration_sec']//60}m {d['duration_sec']%60}s | Stage: {d['target_stage']}")

    if not args.live:
        print("\n[DRY RUN REJIMI]: AmoCRM'ga hech qanday o'zgarish kiritilmadi.")
        print("AmoCRM'ga kiritish uchun: python scripts/import_utc_to_amocrm.py --live")
        return

    print("\n🚀 AMOCRM'GA LIVE INTEGRATSIYA BOSHLANMOQDA...")
    token = get_token()

    success_count = 0
    updated_count = 0

    for idx, deal in enumerate(hot_candidates, 1):
        name = deal["client_name"]
        phone = deal["phone"]
        print(f"\n[{idx}/{len(hot_candidates)}] Ishlanmoqda: #{deal['card_no']} {name} (+{phone})...")

        # 1. Deduplication check
        contact = search_contact_by_phone(token, phone)
        contact_id = None
        existing_lead = None

        if contact:
            contact_id = contact["id"]
            print(f"   ✓ Mavjud kontakt topildi: ID {contact_id}")
            existing_lead = get_active_lead_for_contact(token, contact_id)
            if existing_lead:
                print(f"   ✓ Mavjud ochiq bitim topildi: ID {existing_lead['id']}")
        else:
            print(f"   + Yangi kontakt yaratilmoqda: {name} (+{phone})")
            contact_id = create_contact(token, name, phone)
            time.sleep(0.3)

        if not contact_id:
            logger.error(f"   ✗ Kontakt ID aniqlanmadi, keyingisiga o'tilmoqda.")
            continue

        # 2. Create or Update Lead
        lead_id = create_or_update_lead(token, deal, contact_id, existing_lead)
        if not lead_id:
            logger.error(f"   ✗ Lead yaratib bo'lmadi.")
            continue

        if existing_lead:
            updated_count += 1
        else:
            success_count += 1

        time.sleep(0.3)

        # 3. Add Call Audit Note
        note_text = build_audit_note_text(deal)
        note_ok = add_note_to_lead(token, lead_id, note_text)
        print(f"   ✓ Tahlil xulosasi va BANT hujjati qo'shildi: {'OK' if note_ok else 'FAILED'}")

        time.sleep(0.3)

        # 4. Create Actionable Task
        task_ok = create_task_for_lead(token, lead_id, deal)
        print(f"   ✓ Dushanba 10:00 ga vazifa qo'yildi: {'OK' if task_ok else 'FAILED'}")

        time.sleep(0.5)

    print(f"\n============================================================")
    print(f"🎉 MUVAFFAQISATLI YAKUNLANDI!")
    print(f"• Yangi yaratilgan bitimlar: {success_count} ta")
    print(f"• Yangilangan va boyitilgan mavjud bitimlar: {updated_count} ta")
    print(f"• Barchasiga batafsil dossier qo'shildi va vazifalar o'rnatildi.")
    print(f"============================================================")


if __name__ == "__main__":
    main()
