# Fix Bot: Airtable Field Mapping + Duplicate Messages + Report Quality

## Context
Bot reports show all zeros because Airtable field names in code don't match actual field names. Messages are duplicated and sent every minute (25+ times) due to broken error handling and dedup. Real data EXISTS in Airtable (active projects, April income of 9.4M UZS) but bot can't read it. Night shift sends messages at 01:00-04:00 when nobody reads them.

## Priority Order (most urgent first)

---

### Step 1: Fix Per-Minute Spam Bug (CRITICAL)
**File: `src/main.py` lines 174-217**

**Problem:** `background_monitor_task()` exception handler sleeps only 60s (line 217), so when any function throws an error, the loop retries every minute. Combined with `now.hour == 18` window (entire hour), it fires `send_daily_report()` 25+ times.

**Fix 1a:** Change error sleep from 60 to 600:
- Line 217: `await asyncio.sleep(60)` → `await asyncio.sleep(600)`

**Fix 1b:** Remove duplicate functions from background_monitor_task that overlap with admin_bot.run_scheduler():
- Remove `distribute_team_tasks()` (line 198) — duplicates admin_bot's `trigger_daily_missions()` at 10:00/14:00
- Remove `send_morning_briefing()` (lines 210-212) — admin_bot handles morning missions
- Remove `send_overdue_nudges()` (lines 206-208) — overlaps with `check_airtable_deadlines()`
- Keep: `check_amocrm_stagnation()`, `check_airtable_deadlines()`, `send_daily_report()` at 18:00

**Fix 1c:** Narrow the time window for daily report:
- Line 203: `if now.hour == 18 and now.minute < 10` → `if now.hour == 18 and 0 <= now.minute < 10`
- This is already fine but add a dedup guard by calling `is_job_run` before the send

---

### Step 2: Complete `airtable_sync.py` Field Name Mapping
**File: `src/services/airtable_sync.py`**

FIELD_MAP, DONE_STAGES, and `_get_field()` are already added (lines 9-33). Now update methods to use them:

**2a: `get_overdue_projects()` (lines 64-84)**
- Line 72: `fields.get("Deadline") or fields.get("Muddati")` → `self._get_field(fields, "deadline")`
- Line 73: `fields.get("Stage") or fields.get("Status") or fields.get("Holati")` → `self._get_field(fields, "stage")`
- Line 76: `stage not in ["Done", "Completed", "Topshirildi", "Yakunlandi", "Arxiv"]` → `stage not in self.DONE_STAGES`

**2b: `get_projects_by_stage()` (line 86-89)**
- Line 89: `p.get("fields", {}).get("Stage")` → `self._get_field(p.get("fields", {}), "stage")`

**2c: `get_finance_records()` (lines 91-103)**
- Currently reads from nonexistent `Finance` table
- Rewrite to read from both `Kirim` and `Chiqim` tables:
```python
def get_finance_records(self):
    """Kirim va Chiqim jadvallaridan barcha tranzaksiyalarni olish."""
    records = []
    for table_name, record_type in [("Kirim", "income"), ("Chiqim", "expense")]:
        original_table = self.table_name
        self.table_name = table_name
        self.endpoint = f"https://api.airtable.com/v0/{self.base_id}/{self.table_name}"
        try:
            table_records = self.get_projects()
            for r in table_records:
                r["_record_type"] = record_type
            records.extend(table_records)
        finally:
            self.table_name = original_table
            self.endpoint = f"https://api.airtable.com/v0/{self.base_id}/{self.table_name}"
    return records
```

**2d: `get_upcoming_deadlines()` (lines 131-154)**
- Line 143: `fields.get("Deadline")` → `self._get_field(fields, "deadline")`
- Line 144: `fields.get("Stage")` → `self._get_field(fields, "stage")`
- Line 145: `stage not in ["Done", "Completed", "Topshirildi"]` → `stage not in self.DONE_STAGES`

**2e: `update_project_stage()` (line 116-118)**
- Line 118: `{"Stage": next_stage}` → Try actual field name: `{"Loyiha bosqichi": next_stage}`

**2f: `update_project_stage_by_name()` (lines 120-129)**
- Line 125: `fields.get("Project Name") == project_name or fields.get("Name") == project_name` → `self._get_field(fields, "project_name") == project_name`

---

### Step 3: Fix `enterprise_reporter.py` — Real Data
**File: `src/services/enterprise_reporter.py`**

**3a: Project section (lines 139-162)**
- Line 141: `fields.get('Created') or fields.get('Start Date')` → `AirtableSync._get_field(fields, "start_date")`
- Line 142: `fields.get('Stage', '')` → `AirtableSync._get_field(fields, "stage") or ""`
- Line 144: `stage.lower() in ["done", "yakunlandi", "arxiv"]` → `stage in AirtableSync.DONE_STAGES`
- Line 160: `fields.get('Project Name', 'Nomsiz')` → `AirtableSync._get_field(fields, "project_name") or "Nomsiz"`

**3b: Finance section (lines 171-193)**
Replace the entire finance block. Instead of reading from `Finance` table with `Sana`/`Summa`/`Turi` fields:
- Read from `get_finance_records()` which now returns Kirim+Chiqim with `_record_type`
- For Kirim records: date = `f.get("To'lov sanasi")`, amount = `f.get("To'lov miqdori") or 0`
- For Chiqim records: date = `f.get("Chiqim sanasi")`, amount = `f.get("Chiqim miqdori") or 0`
- Use `_record_type` to determine income vs expense (no `Turi` field needed)

**3c: Remove fake PREMIUM INSIGHT (lines 198-199)**
- Replace the hardcoded lie with a simple summary line based on actual data

---

### Step 4: Fix Night-time Messages
**File: `src/services/night_shift.py`**

**4a: `sync_and_cleanup()` (lines 125-146)**
- Line 141: `f.get('Project Name')` → `AirtableSync._get_field(f, "project_name") or "Nomsiz"`
- Line 141: `f.get('Deadline')` → `AirtableSync._get_field(f, "deadline") or "N/A"`
- Lines 136-142: Wrap Telegram send in hour check — only send overdue alerts between 09:00-19:00, otherwise just log

**4b: `generate_daily_reflection()` (lines 97-123)**
- This sends at 04:00 which is fine (it prepares battlecards for the morning)
- No change needed

**4c: `run_overnight_cycle()` main loop (lines 36-67)**
- No message timing change needed — individual functions handle their own sends

---

### Step 5: Fix `admin_bot.py`
**File: `src/services/admin_bot.py`**

**5a: `trigger_daily_missions()` (lines 592-596)**
- When no missions found, send actionable alert instead of passive "topilmadi":
```
"⚠️ **Pipeline bo'sh!** Aktiv lidlar yo'q.\n🎯 Yangi lidlar izlash kerak! @Oydin_JonBranding"
```

**5b: Add `reject_draft` handler in `callback_handler()` (after line 697)**
- Currently only `send_draft:` exists. Add:
```python
elif data.startswith("reject_draft:"):
    draft_id = data.split(":")[1]
    if draft_id in self.pending_drafts:
        del self.pending_drafts[draft_id]
    await event.edit("❌ Draft bekor qilindi.")
```

---

### Step 6: Fix HTML Parse Mode
**File: `src/services/proactive_worker.py` line 396**

- The fallback `parse_mode=None` sends raw HTML tags. Instead, strip HTML tags before sending:
```python
import re
clean_text = re.sub(r'<[^>]+>', '', report_msg)
await bot.send_message(chat_id=group_id, text=clean_text, parse_mode=None, message_thread_id=thread_id)
```
- Same fix for line 406 (owner fallback)

---

### Step 7: Fix `conversion_checker.py` Field Names
**File: `src/services/conversion_checker.py`**

- Lines 58-65: `airtable_fields` dict uses English field names that don't exist in Airtable:
  - `"Project Name"` → `"Loyihani nomi?"`
  - `"Status"` → `"Loyiha bosqichi"`
  - `"Start Date"` → `"Start sana"`
  - Keep `"Budget"`, `"Client Phone"`, `"Source"` — these may be custom fields

---

## Files to Modify (in order)
1. `src/main.py` — fix spam (60→600 sleep, remove duplicates)
2. `src/services/airtable_sync.py` — complete field name mapping in all methods
3. `src/services/enterprise_reporter.py` — fix field names, Kirim/Chiqim, remove fake insight
4. `src/services/night_shift.py` — fix field names, add hour guard for alerts
5. `src/services/admin_bot.py` — actionable "pipeline bo'sh" + reject_draft
6. `src/services/proactive_worker.py` — strip HTML in fallback
7. `src/services/conversion_checker.py` — fix Airtable field names

## Verification
1. `python -m py_compile src/main.py` (and all modified files)
2. `pytest tests/ -v` if tests exist
3. Deploy to GCP → check that report shows real project count and income
4. Monitor: no duplicate messages, no 2AM alerts, real data in Enterprise Audit
