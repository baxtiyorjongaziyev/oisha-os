# Oisha Admin Dashboard

**A modern ERP-style mini app replacing button-based Telegram interface**

## Overview

Instead of clicking buttons in Telegram, all admin functions are now available in a unified web dashboard. This shift provides:

- **Real-time metrics** (ROI, KPI, team efficiency) updated every 30 seconds
- **Project deadline tracking** with status filtering and direct Airtable links
- **One-click CRM operations** (exports, syncs, lead generation)
- **Automation configuration** (briefing times, job schedules)
- **Clean, modern UI** with live status indicators

## Sections

### 1. Dashboard (`/admin`)

**Overview of operational health in real-time.**

**Metrics:**
- **ROI & Revenue** → Today's sales, transaction count
- **Team Performance** → Manager count, new deals
- **Team Efficiency** → Detailed per-manager stats from EnterpriseReporter

**Actions:**
- 📊 Send Briefing → Push ROI/KPI/Deadline to owner immediately
- 📋 Export to Sheets → Tez Natija members → Google Sheets
- 💼 Export to AmoCRM → Tez Natija members → AmoCRM leads

### 2. Deadlines (`/admin/deadlines`)

**Airtable project deadline tracking with automatic status classification.**

**Filters:**
- All / Overdue / At Risk / On Track

**Display:**
- Project name (clickable link to Airtable record)
- Due date
- Days until due (negative = overdue)
- Status badge with color (🔴 red, 🟡 amber, 🟢 green)
- Responsible manager
- Notes (hover tooltip)

**Status Rules:**
- **Overdue** → due_date < today
- **At Risk** → 0 ≤ days_until_due ≤ 3
- **On Track** → days_until_due > 3

### 3. CRM (`/admin/crm`)

**Lead management and AmoCRM operations.**

**Available Actions:**
1. **Export Tez Natija to Google Sheets**
   - Headers: Telegram ID, Name, Username, Phone, Source, Added, Status, Manager
   - Auto-refreshes existing sheet

2. **Export Tez Natija to AmoCRM**
   - Creates leads in Hunter pipeline
   - Status: "Янgi so'rov" (New Request)
   - Tag: "Tez Natija"
   - Deduplication: skips already-imported members
   - Rate limit: 0.4s/lead (AmoCRM compliance)

### 4. Reports (`/admin/reports`)

**Automation and report configuration.**

**Automated Reports:**
- ✓ Daily Briefing (09:00 UTC+5) → ROI, KPI, team efficiency
- ✓ Deadline Monitoring (every 5 min) → alerts on overdue/at-risk
- ✓ CRM Sync (every 15 min) → tez_natija membership updates

**Configuration:**
- Set briefing time (default: 09:00)
- Specify owner Telegram ID for push notifications
- View real-time automation status

## Backend Integration

### API Endpoints

All endpoints prefixed with `/api/v1/admin/`:

```
GET  /admin/dashboard/stats
     → Returns ROI metrics, KPI, team efficiency

GET  /admin/deadlines
     → Returns projects, status, due dates, manager info

POST /admin/actions/{action_type}
     ├─ export_tez_natija_sheets
     ├─ export_tez_natija_amocrm
     └─ send_briefing
```

### Data Sources

- **Database** → today_stats(), team efficiency via EnterpriseReporter
- **Airtable** → Project table with deadline, manager, status fields
- **AmoCRM** → Lead creation, tagging, pipeline management

## Environment Setup

### Web App (.env)

```env
NEXT_PUBLIC_API_URL=http://localhost:8000
```

Adjust to your backend URL (e.g., Cloud Run, local dev server).

### Backend (src/settings.py)

Required for Airtable deadlines:
```python
AIRTABLE_API_KEY or AIRTABLE_OAUTH_* (OAuth preferred)
AIRTABLE_BASE_ID
```

Optional:
```python
OWNER_ID  # Telegram user ID for push notifications
```

## Usage Flow

1. **Morning briefing** → Visit `/admin` → See yesterday's ROI and today's outlook
2. **Deadline management** → `/admin/deadlines` → Filter by status → Click links to edit in Airtable
3. **CRM operations** → `/admin/crm` → Execute exports as needed
4. **Configure automation** → `/admin/reports` → Set briefing time, owner ID

## Migration from Button UI

**Old approach:**
- Click `/dashboard` button in Telegram → receive text message

**New approach:**
- Visit `https://your-domain.com/admin` → see live dashboard
- All actions available instantly, no message round-trips

**Automation still works:**
- 09:00 daily push is automatic (Telegram still receives it)
- Deadline alerts are pushed on changes
- But manual browsing happens in web app now

## Performance

- Dashboard stats: 30-second refresh (WebSocket upgrade possible)
- Deadlines: 60-second refresh
- Actions: immediate execution
- No polling delays; all real-time

## Future Enhancements

- [ ] WebSocket for live metrics updates
- [ ] Export to PDF/CSV
- [ ] Deadline edit UI (update status in Airtable)
- [ ] Lead search and quick-view
- [ ] Team member profiles
- [ ] Bulk CRM actions

## Troubleshooting

**Deadlines not loading?**
- Check AIRTABLE_API_KEY / AIRTABLE_OAUTH_* in .env
- Verify AIRTABLE_BASE_ID matches your base
- Check API fallback: returns empty list on auth error (doesn't crash)

**Exports failing?**
- Verify Google Sheets credentials (GSHEET_ID)
- Check AmoCRM token (AMOCRM_CLIENT_ID / CLIENT_SECRET)
- Review logs: `docker logs oisha` or `journalctl -u oisha`

**Metrics not updating?**
- Ensure database is accessible (TURSO_DATABASE_URL or bot_database.db)
- Check `/admin/dashboard/stats` API directly: `curl http://localhost:8000/api/v1/admin/dashboard/stats`
