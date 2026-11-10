# Oisha amoCRM → Google Drive automation (draft)

This feature is **not enabled in production by this PR**. It requires credentials,
Drive permissions, a scheduled runner, and staged verification.

## Scope
1. Reuse/create stable per-lead folder `amoCRM_Lead_<id>` under the configured root.
2. Add a CRM note containing the Drive folder URL and CRM lead URL (idempotent).
3. Optionally copy existing CRM file notes, upload and verify size + MD5; write
   a receipt back to the lead. Original CRM files remain untouched.
4. A separate `delete_approved_original` API exists, but **is not wired to any
   scheduler or Telegram callback**. Any caller must first validate authorized
   owner approval out-of-band, then pass a matching approval token. It rechecks
   the remote bytes with SHA256. No automatic deletion is available.
5. Optional Telegram summary using existing `BOT_TOKEN` and `CRM_GROUP_ID`.

## Configure
- `GDRIVE_OFFLOAD_FOLDER_ID`: existing Drive parent folder that the Oisha
  service account can actually write to. Do not rely on a personal 5 TB quota:
  service-account storage rules and Shared Drive membership must be verified.
- `GSHEET_CREDS_FILE`: service-account JSON file with access to that folder.
  Never commit credentials to Git.
- amoCRM OAuth credentials as already configured for Oisha.
- `BOT_TOKEN` and `CRM_GROUP_ID` for Telegram report.

## Manual smoke test (non-destructive)

```bash
python scripts/safe_crm_drive_sync.py --lead-id 123
python scripts/safe_crm_drive_sync.py --lead-id 123 --stage-existing --telegram-report
pytest -q tests/test_safe_crm_drive_automation.py
```

Check the created folder, CRM note, and checksum receipt using a sandbox/test
lead before touching production leads.

## Optional scheduling
Run on the **existing Oisha server**, not a separate paid automation service.
For example, once a smoke test passes:
- Poll recent leads every 5 minutes:
  `python scripts/safe_crm_drive_sync.py --recent 100`
- Daily copy/report (only if approved):
  `python scripts/safe_crm_drive_sync.py --recent 100 --stage-existing --telegram-report`

The `--recent` scan is limited to 250 leads per run; it is **not** a complete
historical migration. A full migration needs pagination/checkpoints and a
separate rollout. A server-side scheduler and production credentials have
**not** been configured by this change. The daily report is sent only when
the runner actually executes with `--telegram-report`.

## Limitations / deployment blockers
- Live amoCRM file API behavior and Drive permissions are unverified.
- No native webhook or real-time lead listener is attached: periodic polling
  gives eventual folder creation, not instant delivery.
- Large files download to memory; implement streaming for very large attachments.
- No UI approval callback is connected to the deletion method.
- Ensure access permissions are restricted to the intended team.
- Do not turn the legacy `CRMFileOffloader.run(dry_run=False)` back on: it
  lacks a safe approval gate. Proactive worker now uses dry-run only.
