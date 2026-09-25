import os
import sys
import sqlite3

sys.path.insert(0, "/home/ubuntu/oisha-os")
from dotenv import load_dotenv
load_dotenv("/home/ubuntu/oisha-os/.env")

from src.services.core.instagram.leadgen_router import (
    _fetch_leadgen_payload,
    flatten_field_data,
    _pick_name,
    _pick_phone,
    _pick,
    EMAIL_KEYS,
    build_telegram_message,
    _notify_telegram,
)
from src.services.core.instagram.leadgen_sheets import append_lead_to_sheet
from src.services.core.instagram.leadgen_delivery import record_delivery_status
from src.services.core.marketing.ad_name_resolver import resolve_ad_name
from src.services.core.marketing.meta_ads_client import MetaAdsClient, get_creative_url
from src.services.core.marketing.lead_cost_estimator import estimate_cost_per_lead

def main():
    token = os.getenv("META_PAGE_ACCESS_TOKEN", "").strip()
    conn = sqlite3.connect("/home/ubuntu/oisha-os/data/leadgen_delivery.db")
    rows = conn.execute(
        "SELECT rowid, leadgen_id, lead_id, destination FROM deliveries WHERE updated_at >= '2026-09-24' ORDER BY rowid ASC;"
    ).fetchall()

    print(f"Total leads to backfill: {len(rows)}")
    meta_ads = MetaAdsClient()

    for rowid, leadgen_id, lead_id, destination in rows:
        print(f"\n--- Backfilling #{rowid} | leadgen={leadgen_id} | amo_id={lead_id} | dest={destination} ---")
        payload = _fetch_leadgen_payload(str(leadgen_id), token)
        fields = flatten_field_data(payload.get("field_data") or [])
        name = _pick_name(fields) or "Mijoz"
        phone = _pick_phone(fields)
        email = _pick(fields, EMAIL_KEYS)
        ad_id = str(payload.get("ad_id") or "")
        ad_name = resolve_ad_name(ad_id)
        form_name = str(payload.get("form_name") or payload.get("form_id") or "")
        created_time = payload.get("created_time") or ""

        creative_url = None
        if ad_id:
            creative_url = meta_ads.get_ad_creative_url(str(ad_id))
        if not creative_url and ad_name:
            creative_url = get_creative_url(ad_name)

        # 1. Append to Google Sheets
        sheets_ok = append_lead_to_sheet(
            leadgen_id=str(leadgen_id),
            lead_id=int(lead_id) if lead_id else None,
            fields=fields,
            form_name=form_name,
            created_time=created_time,
            destination=destination,
            ad_name=ad_name,
            creative_url=creative_url,
        )
        print(f"  Google Sheets append: {sheets_ok}")

        # 2. Send Telegram notification
        dest_label = "🏠 Inhouse (Jon Branding)" if destination == "inhouse" else "🌐 UTC Outsource"
        cost_per_lead = estimate_cost_per_lead(str(payload.get("campaign_id") or ""))
        telegram_text = build_telegram_message(
            str(leadgen_id), int(lead_id) if lead_id else None, name, phone, email, fields,
            cost_per_lead=cost_per_lead, ad_name=ad_name,
        )
        telegram_text += f"\n\n🏢 <b>Taqsimot:</b> {dest_label}"
        buttons = []
        if creative_url:
            buttons.append({"text": f"🎬 {ad_name or 'Kreativ'}ni ko'rish", "url": creative_url})
        if lead_id:
            buttons.append({"text": "🧾 AmoCRM bitimi", "url": f"https://jonbranding.amocrm.ru/leads/detail/{lead_id}"})
        reply_markup = {"inline_keyboard": [buttons]} if buttons else None
        telegram_ok = _notify_telegram(telegram_text, reply_markup=reply_markup)
        print(f"  Telegram notify: {telegram_ok}")

        # 3. Update deliveries table
        record_delivery_status(
            str(leadgen_id), int(lead_id) if lead_id else None,
            True, bool(sheets_ok), bool(telegram_ok),
            destination=destination,
        )

    print("\nBackfill successfully finished!")

if __name__ == "__main__":
    main()
