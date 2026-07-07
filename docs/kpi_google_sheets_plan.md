# Google Sheets KPI Integration Plan

## Scope

This document defines the implementation plan for connecting the RNP Google Sheet to Oisha-OS as a marketing and sales KPI data source.

Source sheet:

- Spreadsheet ID: `1YKpHx5ld9QLMmcKpRXfD9pGhdwdqNgc-w4X8iF-wGUo`
- Default tab/gid: `gid=0`
- Working name: `РНП`

## Goals

1. Read KPI values from Google Sheets safely and repeatably.
2. Normalize lead, call, sales, revenue, conversion, and pacing values into typed application models.
3. Remove fragile formula behavior such as `#DIV/0!` from downstream consumers.
4. Expose KPI summaries through Telegram commands and FastAPI endpoints.
5. Store optional daily snapshots for reporting, trend analysis, and alerting.

## Non-goals for the first implementation

- Editing the production spreadsheet from Oisha-OS.
- Replacing the spreadsheet as the source of truth.
- Building a full frontend dashboard before the read-only API and bot reports are stable.
- Touching legacy, autonomous agent, or external debug folders.

## Recommended delivery sequence

### Phase 1: Documentation and mapping

Create the canonical sheet mapping and integration plan. This phase is intentionally code-free and should be used to confirm column names, row labels, tab names, and formula expectations before implementation.

Deliverables:

- `docs/kpi_google_sheets_plan.md`
- `docs/kpi_sheet_mapping.md`

### Phase 2: Google Sheets reader

Add a small integration layer that reads configured ranges from Google Sheets.

Recommended module names:

- `src/services/core/google_sheets_client.py`
- `src/services/core/kpi_sheet_service.py`

The reader should support a service account first. A public CSV export can be kept as an optional development fallback only if the sheet is intentionally public.

Required environment variables:

```env
GOOGLE_SHEETS_ENABLED=true
GOOGLE_SHEETS_CREDENTIALS_JSON=/etc/oisha-os/google-service-account.json
RNP_SHEET_ID=1YKpHx5ld9QLMmcKpRXfD9pGhdwdqNgc-w4X8iF-wGUo
RNP_SHEET_RANGE=РНП!A1:Z200
```

### Phase 3: KPI normalization and calculations

Convert raw sheet values into stable Python structures.

Core helpers:

- `parse_number(value)`
- `parse_money(value)`
- `parse_percent(value)`
- `safe_div(numerator, denominator, default=0.0)`

Recommended metrics:

- total leads
- total calls
- sales count
- sales amount
- lead-to-call conversion
- call-to-sale conversion
- lead-to-sale conversion
- average check
- month progress percentage
- daily average revenue
- month-end revenue forecast

### Phase 4: Telegram MVP

Add admin-only Telegram commands for the first usable reporting surface.

Commands:

- `/kpi` — current summary
- `/kpi_channels` — source/channel breakdown
- `/kpi_forecast` — month-end pacing forecast
- `/kpi_refresh` — read the sheet and refresh cached values or create a snapshot

### Phase 5: API and snapshots

Add FastAPI endpoints and optional database persistence.

Recommended endpoints:

- `GET /api/kpi/health`
- `GET /api/kpi/rnp/live`
- `POST /api/kpi/rnp/snapshot`
- `GET /api/kpi/rnp/latest`
- `GET /api/kpi/rnp/summary`

Recommended tables:

- `kpi_snapshots`
- `kpi_channel_snapshots`

### Phase 6: Scheduler and alerts

Add scheduled reports after live reads and snapshots are stable.

Recommended jobs:

- morning KPI report
- evening KPI report
- daily snapshot
- weekly summary

Recommended alerts:

- sheet read failure
- zero leads during active business hours
- zero sales by evening
- conversion below threshold
- revenue pacing below target

## Security requirements

- Do not commit Google service account JSON files.
- Do not log private keys, access tokens, or raw credential JSON.
- Store credential paths and sheet IDs in environment variables or existing configuration mechanisms.
- Restrict write access to the spreadsheet unless a future phase explicitly requires it.
- Protect KPI API endpoints with the existing API secret/auth pattern.
- Restrict Telegram KPI commands to configured admin user IDs.

## Formula hardening guidance

Spreadsheet formulas that divide by another cell should avoid user-visible errors. Prefer one of the following patterns:

```gsheet
=IFERROR(A1/B1, 0)
```

or:

```gsheet
=IF(B1=0, 0, A1/B1)
```

For optional visual-only cells, an empty string is acceptable:

```gsheet
=IFERROR(A1/B1, "")
```

Backend code should still treat empty strings, dashes, and spreadsheet error strings as missing values instead of assuming the sheet is always clean.

## Testing checklist

Before each pull request that changes implementation code, run the repository-required checks:

```bash
SKIP_LIVE=1 python -m pytest -q --tb=short
bandit -r src/ -ll
```

Additional tests for KPI implementation phases:

- parsing integers, decimals, spaces, currency strings, and percentages
- `safe_div` with zero, empty, and invalid denominators
- raw sheet rows to KPI channel objects
- live reader disabled by config
- Google Sheets client errors converted to safe application errors
- admin-only Telegram command access
- API endpoint auth behavior

## Acceptance criteria for the full feature

- Oisha-OS can read the configured RNP sheet without manual intervention.
- Bot admins can request current KPI summaries from Telegram.
- API consumers can fetch live and latest KPI summaries.
- Daily snapshots can be stored and queried.
- Sheet formula errors do not crash the backend.
- Missing credentials produce a clear disabled/unavailable response instead of a crash.
- Required tests and Bandit checks pass before PR.
