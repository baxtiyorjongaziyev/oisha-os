# Meta Conversion API (Conversion Leads) — reja

Maqsad: Facebook Lead Ads'dan kelgan lidning keyingi taqdirini (sifatli / sotildi)
Meta'ga qaytarish, shunda reklama sifatli lidga optimizatsiya qilinadi.
Namuna: yuboraman.uz → `/dashboard/capi`.

## Hozir bor
- `schedulers/meta_leadgen_scheduler.py` — Lead Ads polling
- `services/core/instagram/leadgen_router.py` — lid → AmoCRM + Telegram (`_notify_telegram` reply_markup qo'llaydi)
- `services/core/instagram/leadgen_delivery.py` — `leadgen_id ↔ amo lead_id` (`save_crm_checkpoint` / `get_crm_checkpoint`)
- `settings.py` — `META_PAGE_ACCESS_TOKEN`, `META_AD_ACCOUNT_ID` (pixel/dataset yo'q)

## Qo'shiladigan
1. **Settings** (coordinator-owned — AGENTS.md orqali): `META_CAPI_DATASET_ID`,
   `META_CAPI_ACCESS_TOKEN` (SecretStr), `META_CAPI_ENABLED` (default False),
   `META_CAPI_TEST_EVENT_CODE` (ixtiyoriy).
2. **`services/core/marketing/meta_capi.py`**
   - `send_crm_event(leadgen_id, event_name, amo_lead_id=None, value=None)` →
     `POST graph.facebook.com/v21.0/{dataset_id}/events`
   - payload: `action_source="system_generated"`, `custom_data.event_source="crm"`,
     `lead_event_source="Oisha-OS"`, `user_data.lead_id=<leadgen_id>` (+ sha256 ph/em agar bor)
   - idempotency: `capi_events(leadgen_id, event_name, sent_at, status, error)` jadvali,
     unique(leadgen_id, event_name); DB yozuvi `database_pool.py` orqali
   - `ToolResult` qaytaradi; retry 3x backoff
3. **Mapping** AmoCRM status → Meta event (config dict):
   - yangi lid → `Lead` (ixtiyoriy, Meta o'zi biladi)
   - "Qualified"/uchrashuv → `QualifiedLead`
   - "Muvaffaqiyatli" (142) → `Purchase` (value = budget, currency UZS)
   - "Yopildi/yo'q" (143) → `Disqualified` (ixtiyoriy)
4. **Trigger A — AmoCRM**: mavjud CRM sync/webhook oqimida status o'zgarganda
   `get_crm_checkpoint` teskari qidiruv (amo lead_id → leadgen_id) → `send_crm_event`.
   (Teskari lookup funksiyasi `leadgen_delivery.py` ga qo'shiladi.)
5. **Trigger B — Telegram tugmalar**: `build_telegram_message` reply_markup'ga
   `⭐ Sifatli lid` (`capi:q:<leadgen_id>`) va `✅ Sotildi` (`capi:p:<leadgen_id>`);
   callback handler `handlers/` da, faqat WHITELIST/OWNER; bosilgach xabar edit qilinadi.
6. **Guardrails**: `META_CAPI_ENABLED=False` default; quiet-hours ta'sir qilmaydi
   (tashqi mijozga xabar emas), lekin audit log yoziladi.
7. **Testlar** `tests/test_meta_capi.py`: payload shakli, hash, idempotency,
   status mapping, callback ruxsati. HTTP mock, `SKIP_LIVE` bilan live test.
8. **Ops**: Events Manager'da dataset yaratish + CRM integratsiyani "Conversion Leads"
   sifatida belgilash; Ads Manager'da optimizatsiya maqsadi "Conversion leads".

## Gate
`SKIP_LIVE=1 python -m pytest -q` + `bandit -r src/ -ll`. Branch `feat/meta-capi`.
