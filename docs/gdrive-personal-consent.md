# Oisha-OS — personal Google Drive 5 TB automatic onboarding

Owner: baxtiyorjongaziyev@gmail.com

Target folder: Jon Branding — amoCRM fayllari (Oisha-OS)

Folder URL: https://drive.google.com/drive/folders/1C388jvMUp4sAgki6l6xVdqc0yOy7L_--

Folder ID: 1C388jvMUp4sAgki6l6xVdqc0yOy7L_--

The folder was created under the connected personal Google account and verified.
This does NOT give the independent Hetzner prod server (`2.29.198.0`) OAuth access.

## Google owner action (cannot be done by an assistant)

1. In a Google Cloud project, enable the Google Drive API.
2. Configure the Google Auth Platform OAuth consent screen and create an
   OAuth 2.0 Web application client.
3. Add EXACT authorized redirect URI:
   https://oisha.jonbranding.uz/api/integrations/gdrive/callback
4. Add baxtiyorjongaziyev@gmail.com as a test user if the project is in
   External/Testing mode. For a durable integration, review Google's rules
   for restricted Drive scopes and short-lived testing refresh tokens.
5. Save OAuth client ID and client secret as GitHub Actions repository
   secrets GDRIVE_OAUTH_CLIENT_ID and GDRIVE_OAUTH_CLIENT_SECRET.
   Do NOT put secrets in commits, issue comments, or chats.
6. After successful deployment, in a PRIVATE chat with the Oisha Telegram
   bot (as the configured OWNER_ID), send: /gdrive_connect
7. Open the one-time link within 10 minutes, sign in with the requested
   personal Gmail, and approve Google Drive authorization.

The code never extracts or imports Google tokens from the ChatGPT connector.

## After the owner gives Google consent

- Callback verifies the exact email address, 5 TB quota (>= 4.5e12 bytes),
  and destination folder write permissions.
- Credentials are atomically saved as a mode-0600 file at:
  `<OISHA_DIR>/data/gdrive_oauth_token.json` (masalan, `/home/ubuntu/oisha-os/data/gdrive_oauth_token.json`)
- The auto-auth mode switches to user OAuth when the token exists.
- CRM Drive systemd services have an ExecCondition to skip all work until
  that file exists.
- Every 5 minutes, recent 100 CRM leads are synchronized.
- At 03:30 Asia/Tashkent, all paginated existing leads are reconciled,
  copies verified, and a Telegram report delivered.
- Original amoCRM file notes are never deleted automatically.
  The owner may explicitly review verified copies through
  /crm_drive_review <lead_id> in a private Telegram chat.

## Verification and operational commands

On the Hetzner prod VPS (`2.29.198.0`), inside `<OISHA_DIR>` (sobiq Contabo yo'li: `/home/ubuntu/oisha-os`):

    cd <OISHA_DIR>
    ./venv/bin/python scripts/safe_crm_drive_sync.py --preflight
    ./venv/bin/python scripts/safe_crm_drive_sync.py --all-existing --stage-existing --dry-run --telegram-report
    systemctl status oisha-crm-drive-poll.timer
    systemctl status oisha-crm-drive-daily.timer
    journalctl -u oisha-crm-drive-poll.service -n 50 --no-pager

## Safety

- Wrong email or storage quota smaller than expected: reject authorization.
- Wrong folder or absent write permissions: reject.
- No refresh token: reject.
- Expired/reused Telegram ticket or Google state: reject.
- Missing stored token: automatically skip scheduled CRM/Drive work.
- Missing OAuth client configuration: Telegram refuses to issue a link.
- Migration failures preserve the original amoCRM data.

Google consent and live production CRM/Drive testing cannot be completed from
GitHub source access alone. Verify all relevant amoCRM file storage types and
vendor quota behavior before ever approving deletion of originals.
