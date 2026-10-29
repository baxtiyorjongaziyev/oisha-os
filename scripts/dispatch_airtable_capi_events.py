import json
import os
import sys
import time
import requests

sys.path.insert(0, ".")
os.environ["AMOCRM_TOKEN_DB_PERSIST"] = "0"
sys.stdout.reconfigure(encoding="utf-8")

def dispatch_capi(dataset_id: str, access_token: str, test_event_code: str = ""):
    if not os.path.exists("data/airtable_amocrm_enriched_capi.json"):
        print("Xatolik: data/airtable_amocrm_enriched_capi.json topilmadi!")
        return

    with open("data/airtable_amocrm_enriched_capi.json", "r", encoding="utf-8") as f:
        data = json.load(f)

    events = data.get("capi_events", [])
    if not events:
        print("Hech qanday CAPI eventlari mavjud emas.")
        return

    # Filter only events that have valid user_data (Meta requires at least one identifier)
    valid_events = []
    skipped_count = 0
    for e in events:
        ud = e.get("user_data", {})
        if ud.get("ph") or ud.get("em") or ud.get("lead_id"):
            valid_events.append(e)
        else:
            skipped_count += 1

    print(f"Jami eventlar: {len(events)} ta")
    print(f"Meta CAPI ga yuboriladigan to'liq identifikatorli (telefon/email) eventlar: {len(valid_events)} ta")
    print(f"Identifikatori bo'lmagani uchun o'tkazib yuborilgan: {skipped_count} ta\n")
    print(f"Meta Graph API ga jami {len(valid_events)} ta Purchase eventi yuborilmoqda...")
    print(f"Dataset / Pixel ID: {dataset_id}")
    url = f"https://graph.facebook.com/v21.0/{dataset_id}/events"

    # Meta Graph API accepts up to 1000 events per call, we batch by 50 for safety
    batch_size = 50
    total_received = 0
    errors = []

    for i in range(0, len(valid_events), batch_size):
        chunk = valid_events[i:i + batch_size]
        body = {
            "data": chunk,
            "access_token": access_token
        }
        if test_event_code:
            body["test_event_code"] = test_event_code

        try:
            r = requests.post(url, json=body, timeout=30)
            res_data = r.json()
            if r.status_code == 200:
                rec = res_data.get("events_received", len(chunk))
                total_received += rec
                print(f"   [CAPI OK] Batch {i//batch_size + 1}: {rec} ta event qabul qilindi (events_received: {rec})")
            else:
                errors.append(res_data)
                print(f"   [CAPI ERROR] Batch {i//batch_size + 1}: Status {r.status_code} | {res_data.get('error', {}).get('message')}")
        except Exception as e:
            errors.append({"exception": str(e)})
            print(f"   [CAPI EXCEPTION]: {e}")
        time.sleep(0.5)

    print("\n==================================================")
    print("META CAPI NATIJASI:")
    print(f"Muvaffaqiyatli qabul qilingan eventlar: {total_received} ta")
    if errors:
        print(f"Xatoliklar soni: {len(errors)} ta")
    else:
        print("Barcha to'lovlar Meta Events Manager ga to'liq va muvaffaqiyatli yetkazildi!")
    print("==================================================")

if __name__ == "__main__":
    ds_id = sys.argv[1] if len(sys.argv) > 1 else os.getenv("META_CAPI_DATASET_ID")
    token = sys.argv[2] if len(sys.argv) > 2 else os.getenv("META_CAPI_ACCESS_TOKEN")
    test_code = sys.argv[3] if len(sys.argv) > 3 else os.getenv("META_CAPI_TEST_EVENT_CODE", "")

    if not ds_id or not token:
        print("Iltimos, Dataset ID va Access Token ni argument sifatida bering:")
        print("python scripts/dispatch_airtable_capi_events.py <DATASET_ID> <ACCESS_TOKEN> [TEST_CODE]")
    else:
        dispatch_capi(ds_id, token, test_code)
