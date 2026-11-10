# Oisha CRM ↔ Google Drive — existing deals and safe automation

**Status:** Draft PR only. NOT deployed. No production CRM files modified.

## Account / quota check

The connected user's Drive currently lists **zero visible Shared Drives**.
That does NOT prove the service account can or cannot access a particular folder,
nor does it verify the user's claimed 5 TB subscription. The app uses a service
account by default; that principal does not inherit the user's Google One quota.
For storage in the personal 5 TB account, use an explicit OAuth grant for **that**
account (not the ChatGPT connector's authorization).

Option A — **personal Drive 5 TB via OAuth**:
1. In Google Cloud enable Drive API and create an OAuth Desktop client.
2. On a trusted personal computer, run:
   `python scripts/authorize_gdrive_oauth.py --client-secrets CLIENT.json --output gdrive_oauth_token.json`
3. Authorize the intended Drive owner and verify the email.
4. Securely copy the resulting token JSON to the Contabo server with owner-only
   permissions (mode 0600). Never commit OAuth secrets, credentials or tokens.
5. Add to server `.env`:
   `GDRIVE_AUTH_MODE=oauth`
   `GDRIVE_OAUTH_TOKEN_FILE=/home/ubuntu/oisha-os/data/gdrive_oauth_token.json`
   `GDRIVE_OFFLOAD_FOLDER_ID=<existing-folder-id>`
   5 TB user storage needs to be checked against the API `storageQuota.limit`.
   New Google OAuth test-mode applications may issue short-lived grants.
6. Verify using `--preflight --probe-write`.

Option B — **service account / Shared Drive**:
1. Give the service-account email write access to an actual Shared Drive folder.
2. Use `GDRIVE_AUTH_MODE=service_account` and the existing `GSHEET_CREDS_FILE`.
3. Set `GDRIVE_OFFLOAD_FOLDER_ID` to its folder ID.
4. Check with `--preflight --probe-write`. A regular user's Drive quota is
   not transferable merely by sharing a My Drive folder.

## 1. Existing bitimlar / backfill (without deleting originals)

Review all accessible paginated leads first:
```bash
python scripts/safe_crm_drive_sync.py --all-existing --stage-existing --dry-run --telegram-report
```
This dry-run only counts discovered notes and does not write Drive or amoCRM.

For one designated test lead ID:
```bash
python scripts/safe_crm_drive_sync.py --preflight --probe-write
python scripts/safe_crm_drive_sync.py --lead-id 12345 --stage-existing --telegram-report
```
Verify the Drive folder, matching CRM note, checksum and team access. Replace
12345 with a dedicated safe test lead rather than a customer record.

After review, stage all existing deals in pages (including won/lost):
```bash
python scripts/safe_crm_drive_sync.py --all-existing --stage-existing --telegram-report
```
To stage only open deals, additionally use `--active-only`. Reruns reuse folder
IDs and copy receipts, allowing safe restart after partial failure. API failures
are reported as failures, not silently treated as zero leads. Backfill is not
scheduled by this PR unless the operator explicitly installs the systemd timers.

## 2. Telegram owner approval

After a verified file receipt exists, configured `OWNER_ID` sends in the
bot's *private* chat:
`/crm_drive_review 12345`

The bot displays up to five eligible files with ✅/❌ buttons. The request is
durably stored in Turso and expires in 12 hours; a callback is accepted only
from the configured owner, private chat and once per request. On approval the
code checks the receipt, Drive file size and *full SHA256 bytes* before deleting
only the corresponding original CRM file note. Rejection never deletes. The
system records status (pending/rejected/processing/deleted/failed) in Turso.

**Warning:** CRM may have file attachments that are not represented by file
notes; confirm amoCRM Files API coverage and CRM quota decrease in a dedicated
test before bulk offload. Deleting a CRM note might not reduce quota if the
backing file is retained by the vendor; verify vendor behavior first.

## 3. Scheduling (opt-in on existing Contabo server)

Two systemd unit/timer pairs have been added, but not installed/enabled:
- `oisha-crm-drive-poll.timer`: every 5 minutes, latest 100 deals, stage files
- `oisha-crm-drive-daily.timer`: daily 03:30 Asia/Tashkent, full backfill + report

After passing live test and approval:
```bash
sudo cp deploy/systemd/oisha-crm-drive-{poll,daily}.{service,timer} /etc/systemd/system/
sudo systemctl daemon-reload
sudo systemctl enable --now oisha-crm-drive-poll.timer oisha-crm-drive-daily.timer
sudo systemctl list-timers 'oisha-crm-drive*'
```
Review actual service-account OAuth quota, 5 TB permissions, network bandwidth,
API rate limits, free server memory, and Telegram bot permissions first.

## 4. Test gates and safety
```bash
pytest -q tests/test_safe_crm_drive_automation.py tests/test_crm_drive_backfill_and_approval.py
python -m compileall -q src/services/core/crm scripts/safe_crm_drive_sync.py
```
Also require PR CI, security scan, an end-to-end test lead and explicit deployment
authorization. These tests are mock-based, **not** a live 5 TB account check.

Legacy `CRMFileOffloader.run(dry_run=False)` is prohibited in background tasks.
No production automation runs merely by merging this PR: the systemd timers must
be installed and production OAuth credentials must be explicitly configured.

### Limitations
- One verified receipt per `note_id` is reused. Very large files currently pass
  through memory; stream very large archives in a follow-up hardening change.
- The daily scan processes leads in pages. If a live CRM API failure occurs,
  the run stops with a nonzero exit and the Telegram report indicates errors.
- Only file-type CRM notes are migrated in this iteration; coverage requires
  an inventory of other amoCRM storage-bearing objects.
- No real customer files are deleted by migrations or timer runs.
