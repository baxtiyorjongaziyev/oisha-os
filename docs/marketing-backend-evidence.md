# JonBranding marketing backend evidence contract

2026-10-12. Local implementation; production activation is not verified.

`GET /api/marketing/performance` uses the synchronized Meta and amoCRM caches.
Dates use Asia/Tashkent defaults. Invalid or reversed periods return HTTP 422.
The report is a lead-created cohort: revenue is the current known outcome of
leads created during the selected dates, not revenue from all deals closed then.
Only tracked Meta Lead Ads leads are covered; website/call sources are not yet
part of this report. `status=partial` explicitly avoids claiming complete data.

Unknown source values and undefined ratios are JSON null. Meta spend currency
comes from `account_currency` in Insights and is stored with each daily row.
Legacy rows keep unknown currency until refreshed. Mixed or missing currencies
prevent combining total spend. No implicit FX conversion is performed.

Set the non-secret `OISHA_REVENUE_CURRENCY` only after verifying the amoCRM
account currency. With no configured CRM currency, ROAS is null. ROAS is also
null when Meta and CRM currencies differ. A frontend must handle null values
as unavailable, never convert them to zero.

Purchase CAPI events require a finite positive amount. A send is confirmed
only when Meta returns `events_received=1`; HTTP 200 alone is insufficient.
No live event was sent while implementing this change.

Still open: source freshness/coverage verification, website attribution
integration, a unified daily marketing digest, and live Meta/CRM reconciliation.
`marketing-os/backend/main.py` is a separate mock dashboard and must not be
used as an operational source. This change does not deploy or activate services.
